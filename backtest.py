import time
import requests
import pandas as pd

from indicators import (
    compute_rsi,
    compute_bollinger,
    get_csi,
    compute_csc,
    check_signal_row,
)

BASE_URL = "https://mainnet.zklighter.elliot.ai"


def fetch_candles(market_id: int, resolution: str, count_back: int) -> pd.DataFrame:
    """Fetch candlesticks from Lighter REST API."""
    end = int(time.time() * 1000)
    params = {
        "market_id": market_id,
        "resolution": resolution,
        "end_timestamp": end,
        "count_back": count_back,
        "start_timestamp": 0,
    }
    resp = requests.get(f"{BASE_URL}/api/v1/candlesticks", params=params)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data)
    df = df.rename(columns={"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    df = df.sort_values('timestamp').reset_index(drop=True)
    return df


def run_backtest(df: pd.DataFrame, stop_loss_pct: float = 0.004, exit_after_bars: int = 15) -> pd.DataFrame:
    """Run backtest on prepared dataframe."""
    df = compute_rsi(df)
    df = compute_bollinger(df)
    df = get_csi(df)
    df = compute_csc(df)

    signals = [None]
    for i in range(1, len(df)):
        signals.append(check_signal_row(df.iloc[i], df.iloc[i - 1]))
    df['signal'] = signals

    in_position = False
    entry_price = 0.0
    entry_index = 0
    position_type = ''

    trades = []

    for i in range(1, len(df)):
        row = df.iloc[i]
        signal = row['signal']
        if not in_position and signal in ['buy', 'sell']:
            in_position = True
            entry_index = i
            entry_price = row['close']
            position_type = 'long' if signal == 'buy' else 'short'
            stop_price = (
                entry_price * (1 - stop_loss_pct)
                if position_type == 'long'
                else entry_price * (1 + stop_loss_pct)
            )
        elif in_position:
            exit_index = entry_index + exit_after_bars
            exit_row = df.iloc[i]
            low, high = exit_row['low'], exit_row['high']
            hit_stop = (
                low <= stop_price if position_type == 'long' else high >= stop_price
            )
            if hit_stop or i >= exit_index:
                exit_price = stop_price if hit_stop else exit_row['close']
                pnl = (
                    (exit_price - entry_price) / entry_price * 100
                    if position_type == 'long'
                    else (entry_price - exit_price) / entry_price * 100
                )
                trades.append(
                    {
                        'entry_time': df.iloc[entry_index]['timestamp'],
                        'exit_time': df.iloc[i]['timestamp'],
                        'position_type': position_type,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_%': pnl,
                        'reason': 'stop_loss' if hit_stop else 'time_exit',
                    }
                )
                in_position = False

    trades_df = pd.DataFrame(trades)
    return trades_df


if __name__ == "__main__":
    candles = fetch_candles(market_id=0, resolution="1m", count_back=100000)
    trades_df = run_backtest(candles)
    trades_df.to_csv('trades_complete.csv', sep=';', index=False)
    print(trades_df.tail(10))
    total_pnl = trades_df['pnl_%'].sum()
    print(f"Total PnL: {total_pnl:.2f}%")
