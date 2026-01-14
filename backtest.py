"""
Backtest script for Indicator Diff strategy

Strategy:
- BUY: Indicator_Diff > 1
- HOLD: Indicator_Diff in [-1, 0, 1]
- SELL: Indicator_Diff < -1

Tests on: RATU.JK, IMPC.JK, BKSL.JK
Timeframes: 1d, 1h, 15m
"""

import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime

def calculate_indicators(df):
    """Calculate all indicators and return dataframe with Indicator_Diff"""
    if df.empty:
        return None

    # Flatten Multi-Index Columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Price
    df['Price'] = df['Close']

    # Moving Averages
    df['MA_5'] = ta.sma(df['Close'], length=5)
    df['MA_10'] = ta.sma(df['Close'], length=10)

    # RSI
    df['RSI_Score'] = ta.rsi(df['Close'], length=14)

    # SuperTrend
    st_data = ta.supertrend(df['High'], df['Low'], df['Close'], length=10, multiplier=3)
    if st_data is not None and not st_data.empty:
        st_dir_col = st_data.columns[1]
        df['SuperTrend_Direction'] = st_data[st_dir_col]
    else:
        df['SuperTrend_Direction'] = 0

    # Volume Oscillator
    vol_short = ta.sma(df['Volume'], length=5)
    vol_long = ta.sma(df['Volume'], length=10)
    df['Vol_Osc'] = ((vol_short - vol_long) / vol_long) * 100

    # Calculate scores
    df['Score_MA5'] = df.apply(lambda r: 1 if r['Price'] > r['MA_5'] else (-1 if r['Price'] < r['MA_5'] else 0) if pd.notna(r['MA_5']) else 0, axis=1)
    df['Score_MA10'] = df.apply(lambda r: 1 if r['Price'] > r['MA_10'] else (-1 if r['Price'] < r['MA_10'] else 0) if pd.notna(r['MA_10']) else 0, axis=1)

    def score_rsi(rsi):
        if pd.isna(rsi):
            return 0
        if rsi > 75 or rsi <= 30:
            return -1
        elif 50 <= rsi <= 75:
            return 1
        return 0

    df['Score_RSI'] = df['RSI_Score'].apply(score_rsi)
    df['Score_SuperTrend'] = df['SuperTrend_Direction'].apply(lambda x: 1 if x == 1 else (-1 if x == -1 else 0))

    def score_vol_osc(row):
        if pd.isna(row['Vol_Osc']) or pd.isna(row['MA_5']) or pd.isna(row['MA_10']):
            return 0
        price_above = row['Price'] > row['MA_5'] and row['Price'] > row['MA_10']
        price_below = row['Price'] < row['MA_5'] and row['Price'] < row['MA_10']
        vol = row['Vol_Osc']

        if (price_above and vol >= 20) or (price_below and vol >= 20) or vol > 0:
            return 1
        elif (price_above and vol <= -15) or (price_below and vol <= -15) or vol <= 0:
            return -1
        return 0

    df['Score_VolOsc'] = df.apply(score_vol_osc, axis=1)

    # Total Indicator
    df['Indicator'] = df['Score_MA5'] + df['Score_MA10'] + df['Score_RSI'] + df['Score_SuperTrend'] + df['Score_VolOsc']

    # Indicator Diff
    df['Indicator_Diff'] = df['Indicator'].diff().fillna(0).astype(int)

    return df.dropna()


def backtest_strategy(df, initial_capital=10000000):
    """
    Backtest the strategy:
    - BUY: Indicator_Diff > 1
    - HOLD: Indicator_Diff in [-1, 0, 1]
    - SELL: Indicator_Diff < -1

    Returns dict with performance metrics
    """
    if df is None or len(df) < 20:
        return None

    capital = initial_capital
    shares = 0
    position = None  # 'long' or None
    trades = []
    buy_price = 0

    for i, row in df.iterrows():
        price = row['Price']
        diff = row['Indicator_Diff']

        # BUY signal
        if diff > 1 and position is None:
            shares = capital // price
            if shares > 0:
                buy_price = price
                capital -= shares * price
                position = 'long'
                trades.append({
                    'date': i,
                    'action': 'BUY',
                    'price': price,
                    'shares': shares,
                    'diff': diff
                })

        # SELL signal
        elif diff < -1 and position == 'long':
            capital += shares * price
            pnl = (price - buy_price) * shares
            pnl_pct = ((price - buy_price) / buy_price) * 100
            trades.append({
                'date': i,
                'action': 'SELL',
                'price': price,
                'shares': shares,
                'diff': diff,
                'pnl': pnl,
                'pnl_pct': pnl_pct
            })
            shares = 0
            position = None

    # Close any open position at end
    if position == 'long' and len(df) > 0:
        final_price = df.iloc[-1]['Price']
        capital += shares * final_price
        pnl = (final_price - buy_price) * shares
        pnl_pct = ((final_price - buy_price) / buy_price) * 100
        trades.append({
            'date': df.index[-1],
            'action': 'SELL (Close)',
            'price': final_price,
            'shares': shares,
            'diff': df.iloc[-1]['Indicator_Diff'],
            'pnl': pnl,
            'pnl_pct': pnl_pct
        })

    # Calculate metrics
    final_value = capital
    total_return = ((final_value - initial_capital) / initial_capital) * 100

    # Buy and hold comparison
    if len(df) > 0:
        bh_shares = initial_capital // df.iloc[0]['Price']
        bh_final = bh_shares * df.iloc[-1]['Price'] + (initial_capital - bh_shares * df.iloc[0]['Price'])
        bh_return = ((bh_final - initial_capital) / initial_capital) * 100
    else:
        bh_return = 0

    # Win rate
    sell_trades = [t for t in trades if 'pnl' in t]
    wins = len([t for t in sell_trades if t['pnl'] > 0])
    losses = len([t for t in sell_trades if t['pnl'] <= 0])
    win_rate = (wins / len(sell_trades) * 100) if sell_trades else 0

    return {
        'initial_capital': initial_capital,
        'final_value': final_value,
        'total_return_pct': total_return,
        'buy_hold_return_pct': bh_return,
        'outperformance': total_return - bh_return,
        'num_trades': len(sell_trades),
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'trades': trades
    }


def run_backtest(ticker, interval, period):
    """Run backtest for a single ticker/interval combination"""
    print(f"\n  Fetching {ticker} ({interval})...")

    try:
        # Handle 4h interval
        yf_interval = '60m' if interval == '4h' else interval
        df = yf.download(ticker, period=period, interval=yf_interval, progress=False)

        if interval == '4h' and not df.empty:
            df = df.resample('4h').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()

        if df.empty:
            print(f"    No data for {ticker}")
            return None

        df = calculate_indicators(df)
        if df is None:
            return None

        result = backtest_strategy(df)
        return result

    except Exception as e:
        print(f"    Error: {e}")
        return None


def main():
    print("=" * 70)
    print("INDICATOR DIFF STRATEGY BACKTEST")
    print("=" * 70)
    print("\nStrategy Rules:")
    print("  - BUY:  Indicator_Diff > 1")
    print("  - HOLD: Indicator_Diff in [-1, 0, 1]")
    print("  - SELL: Indicator_Diff < -1")
    print("\nInitial Capital: Rp 10,000,000")

    tickers = ["RATU.JK", "IMPC.JK", "BKSL.JK"]

    # Timeframes with appropriate periods
    timeframes = [
        ('1d', '1y', 'Daily (1 Year)'),
        ('1h', '60d', 'Hourly (60 Days)'),
        ('15m', '30d', '15-Min (30 Days)'),
    ]

    results_summary = []

    for interval, period, label in timeframes:
        print(f"\n{'=' * 70}")
        print(f"TIMEFRAME: {label}")
        print("=" * 70)

        for ticker in tickers:
            result = run_backtest(ticker, interval, period)

            if result:
                print(f"\n  {ticker}:")
                print(f"    Strategy Return: {result['total_return_pct']:+.2f}%")
                print(f"    Buy & Hold:      {result['buy_hold_return_pct']:+.2f}%")
                print(f"    Outperformance:  {result['outperformance']:+.2f}%")
                print(f"    Trades: {result['num_trades']} | Win Rate: {result['win_rate']:.1f}%")
                print(f"    Final Value: Rp {result['final_value']:,.0f}")

                results_summary.append({
                    'ticker': ticker,
                    'timeframe': label,
                    'strategy_return': result['total_return_pct'],
                    'bh_return': result['buy_hold_return_pct'],
                    'outperformance': result['outperformance'],
                    'trades': result['num_trades'],
                    'win_rate': result['win_rate']
                })

    # Summary table
    print("\n" + "=" * 70)
    print("SUMMARY TABLE")
    print("=" * 70)
    print(f"\n{'Ticker':<12} {'Timeframe':<20} {'Strategy':>10} {'B&H':>10} {'Outperf':>10} {'Trades':>8} {'Win%':>8}")
    print("-" * 78)

    for r in results_summary:
        print(f"{r['ticker']:<12} {r['timeframe']:<20} {r['strategy_return']:>+9.2f}% {r['bh_return']:>+9.2f}% {r['outperformance']:>+9.2f}% {r['trades']:>8} {r['win_rate']:>7.1f}%")

    # Overall statistics
    if results_summary:
        avg_strategy = sum(r['strategy_return'] for r in results_summary) / len(results_summary)
        avg_bh = sum(r['bh_return'] for r in results_summary) / len(results_summary)
        avg_outperf = sum(r['outperformance'] for r in results_summary) / len(results_summary)
        avg_winrate = sum(r['win_rate'] for r in results_summary) / len(results_summary)

        print("-" * 78)
        print(f"{'AVERAGE':<12} {'':<20} {avg_strategy:>+9.2f}% {avg_bh:>+9.2f}% {avg_outperf:>+9.2f}% {'':<8} {avg_winrate:>7.1f}%")

    print("\n" + "=" * 70)
    print("BACKTEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
