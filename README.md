# lighter_bot

Example Bollinger Bands trading bot for the [Lighter](https://lighter.xyz) exchange.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Export environment variables with your credentials:
   ```bash
   export API_KEY_PRIVATE_KEY="<your_private_key>"
   export ACCOUNT_INDEX="<account_index>"
   export API_KEY_INDEX="<api_key_index>"
   # optional
   export LIGHTER_MARKET_ID="0"
   export TRADE_SIZE="1"  # base asset amount
   ```
3. Run a backtest on 100k 1m candles:
   ```bash
   python backtest.py
   ```
4. Start the live bot (uses REST candles, submits market orders):
   ```bash
   python bot.py
   ```

The strategy combines Bollinger Bands, RSI and CSI/CSC indicators. Code is
for educational purposes; use at your own risk.
