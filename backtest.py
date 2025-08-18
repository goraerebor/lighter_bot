import requests
import pandas as pd


def fetch_candles(url: str) -> pd.DataFrame:
    """Fetch candlestick data from the given URL and return a DataFrame."""
    resp = requests.get(url)
    data = resp.json()
    if not isinstance(data, list):
        print(f"Unexpected response type: {type(data).__name__}")
        print(f"Status: {resp.status_code}, Body: {resp.text}")
        if isinstance(data, dict):
            data = data.get("candlesticks", [])
    # Guard clause to ensure data validity
    expected_fields = {"open", "high", "low", "close", "timestamp"}
    if not data or any(field not in data[0] for field in expected_fields):
        raise ValueError("Invalid or empty candlestick data received")
    return pd.DataFrame(data)


if __name__ == "__main__":
    # Example usage (won't run without a real API endpoint)
    pass
