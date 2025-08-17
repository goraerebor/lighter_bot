import numpy as np
import pandas as pd
from scipy.stats import zscore

def compute_rsi(df: pd.DataFrame, period: int = 450) -> pd.DataFrame:
    """Calculate RSI indicator."""
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period, min_periods=1).mean()
    avg_loss = loss.rolling(period, min_periods=1).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    df['RSI'] = df['RSI'].fillna(method='bfill')
    return df

def compute_bollinger(df: pd.DataFrame, period: int = 40, std: int = 1) -> pd.DataFrame:
    """Calculate Bollinger Bands."""
    df['ma'] = df['close'].rolling(period).mean()
    df['std'] = df['close'].rolling(period).std()
    df['upper'] = df['ma'] + std * df['std']
    df['lower'] = df['ma'] - std * df['std']
    return df

def get_csi(df: pd.DataFrame) -> pd.DataFrame:
    """Compute CSI indicator."""
    body = (df['close'] - df['open']).abs()
    rng = (df['high'] - df['low']).replace(0, np.nan)
    body_ratio = body / rng
    direction = np.where(df['close'] > df['open'], 1, -1)
    vol_score = df['volume'] / df['volume'].rolling(50).max()
    range_z = zscore(df['high'] - df['low']).clip(-3, 3)

    tr = pd.DataFrame({
        'hl': df['high'] - df['low'],
        'hc': (df['high'] - df['close'].shift(1)).abs(),
        'lc': (df['low'] - df['close'].shift(1)).abs()
    }).max(axis=1)
    atr = tr.rolling(14).mean().bfill()

    df['CSI'] = direction * (0.5 * body_ratio + 0.3 * vol_score + 0.2 * range_z) / atr
    return df

def compute_csc(df: pd.DataFrame, min_cluster: int = 3, bull_quant: float = 0.75,
                bear_quant: float = 0.25) -> pd.DataFrame:
    """Compute cluster sentiment confirmation (CSC)."""
    sub = df.tail(min(50000, len(df)))
    bull_thr = sub['CSI'].quantile(bull_quant)
    bear_thr = sub['CSI'].quantile(bear_quant)
    df['sentiment'] = np.where(df['CSI'] >= bull_thr, 'bull',
                        np.where(df['CSI'] <= bear_thr, 'bear', 'neutral'))
    df['cluster_id'] = pd.Series(dtype='object')
    curr_type, curr_start, length = None, None, 0
    for i, s in df['sentiment'].items():
        if s == curr_type and s in ['bull', 'bear']:
            length += 1
        else:
            if curr_type in ['bull', 'bear'] and length >= min_cluster:
                df.loc[curr_start:i-1, 'cluster_id'] = f"{curr_type}_{curr_start}"
            if s in ['bull', 'bear']:
                curr_type, curr_start, length = s, i, 1
            else:
                curr_type, length = None, 0
    if curr_type in ['bull', 'bear'] and length >= min_cluster:
        df.loc[curr_start:df.index[-1], 'cluster_id'] = f"{curr_type}_{curr_start}"
    return df

def check_signal_row(row: pd.Series, prev_row: pd.Series, rsi_threshold: int = 60):
    """Generate trading signals based on indicators."""
    if np.isnan(row['lower']) or np.isnan(prev_row['CSI']) or np.isnan(row['CSI']):
        return None
    cluster = row['cluster_id']
    if not isinstance(cluster, str):
        return None
    long_cond = (
        row['close'] < row['lower'] and
        row['CSI'] > 0 and row['CSI'] > prev_row['CSI'] and
        cluster.startswith('bull') and row['RSI'] < rsi_threshold
    )
    short_cond = (
        row['close'] > row['upper'] and
        row['CSI'] < 0 and row['CSI'] < prev_row['CSI'] and
        cluster.startswith('bear') and row['RSI'] > (100 - rsi_threshold)
    )
    if long_cond:
        return 'buy'
    if short_cond:
        return 'sell'
    return None
