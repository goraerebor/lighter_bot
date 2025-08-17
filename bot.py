"""Simple trading bot for Lighter using Bollinger Bands strategy.

This example adapts the strategy from the Habr article to work with
lighter-python SDK. It uses REST candlesticks for signals and submits
market orders via SignerClient. The code is simplified and provided
for educational purposes.
"""

import asyncio
import os
import time
from collections import deque

import pandas as pd
import requests
import lighter

from indicators import (
    compute_rsi,
    compute_bollinger,
    get_csi,
    compute_csc,
    check_signal_row,
)

BASE_URL = os.getenv("LIGHTER_BASE_URL", "https://mainnet.zklighter.elliot.ai")
MARKET_ID = int(os.getenv("LIGHTER_MARKET_ID", "0"))
RESOLUTION = os.getenv("LIGHTER_RESOLUTION", "1m")
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "0.004"))
EXIT_AFTER_BARS = int(os.getenv("EXIT_AFTER_BARS", "3"))
TRADE_SIZE = float(os.getenv("TRADE_SIZE", "1"))

API_KEY_PRIVATE_KEY = os.getenv("API_KEY_PRIVATE_KEY")
ACCOUNT_INDEX = int(os.getenv("ACCOUNT_INDEX", "0"))
API_KEY_INDEX = int(os.getenv("API_KEY_INDEX", "2"))

client = lighter.SignerClient(
    url=BASE_URL,
    private_key=API_KEY_PRIVATE_KEY,
    account_index=ACCOUNT_INDEX,
    api_key_index=API_KEY_INDEX,
)
transaction_api = lighter.TransactionApi(client)


def fetch_candles(count_back: int = 1000) -> pd.DataFrame:
    """Fetch recent candles for the configured market."""
    end = int(time.time() * 1000)
    params = {
        "market_id": MARKET_ID,
        "resolution": RESOLUTION,
        "end_timestamp": end,
        "count_back": count_back,
        "start_timestamp": 0,
    }
    resp = requests.get(f"{BASE_URL}/api/v1/candlesticks", params=params)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data).rename(
        columns={"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
    )
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    return df.sort_values('timestamp').reset_index(drop=True)


def place_market_order(side: str, base_amount: int, price: int, nonce: int, reduce_only: bool = False):
    """Sign and send a market order."""
    is_ask = side == 'sell'
    order, err = client.sign_create_order(
        market_index=MARKET_ID,
        client_order_index=int(time.time()),
        is_ask=is_ask,
        base_amount=base_amount,
        price=price,
        order_type=lighter.ORDER_TYPE_MARKET,
        time_in_force=lighter.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
        nonce=nonce,
        reduce_only=reduce_only,
    )
    if err:
        raise RuntimeError(f"Sign error: {err}")
    resp = transaction_api.send_tx(
        tx_type=lighter.TX_TYPE_CREATE_ORDER,
        tx_info=order,
    )
    return resp


async def main_loop():
    df = fetch_candles(60000)
    df = compute_rsi(df)
    df = compute_bollinger(df)
    df = get_csi(df)
    df = compute_csc(df)

    entry_history = deque(maxlen=100)
    open_pos = None

    while True:
        new_df = fetch_candles(200)
        df = pd.concat([df, new_df]).drop_duplicates('timestamp').reset_index(drop=True)
        df = compute_rsi(df)
        df = compute_bollinger(df)
        df = get_csi(df)
        df = compute_csc(df)

        signal = check_signal_row(df.iloc[-2], df.iloc[-3])
        now = time.time()
        if open_pos is None and signal in ['buy', 'sell']:
            side = 'buy' if signal == 'buy' else 'sell'
            nonce = transaction_api.next_nonce(ACCOUNT_INDEX, API_KEY_INDEX)['nonce']
            base_amount = int(TRADE_SIZE * 10)
            price = int(df.iloc[-2]['close'] * 10)
            place_market_order(side, base_amount, price, nonce)
            stop_price = (
                df.iloc[-2]['close'] * (1 - STOP_LOSS_PCT)
                if side == 'buy'
                else df.iloc[-2]['close'] * (1 + STOP_LOSS_PCT)
            )
            open_pos = {
                'side': side,
                'entry_price': df.iloc[-2]['close'],
                'stop_price': stop_price,
                'opened_at': now,
            }
            entry_history.append((now, side))
        elif open_pos is not None:
            curr_price = df.iloc[-2]['close']
            bars_open = int((time.time() - open_pos['opened_at']) / (5 * 60))
            hit_stop = (
                curr_price <= open_pos['stop_price']
                if open_pos['side'] == 'buy'
                else curr_price >= open_pos['stop_price']
            )
            if hit_stop or bars_open >= EXIT_AFTER_BARS:
                nonce = transaction_api.next_nonce(ACCOUNT_INDEX, API_KEY_INDEX)['nonce']
                base_amount = int(TRADE_SIZE * 10)
                price = int(curr_price * 10)
                place_market_order(
                    'sell' if open_pos['side'] == 'buy' else 'buy',
                    base_amount,
                    price,
                    nonce,
                    reduce_only=True,
                )
                open_pos = None
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main_loop())
