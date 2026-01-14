"""
Backtest Script for Indicator-Based Trading Strategy

This script tests different indicator thresholds to find optimal
buy/hold/sell signals based on the composite indicator score.

Indicator Score Range: -5 to +5
- MA5: +1/-1
- MA10: +1/-1
- RSI: +1/0/-1
- SuperTrend: +1/-1
- Vol Osc Result: +1/-1
"""

import yfinance as yf
import pandas_ta as ta
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

def calculate_indicators(df):
    """Calculate all technical indicators and scores"""

    # Flatten Multi-Index Columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.copy()

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
    # MA5 Score
    df['Score_MA5'] = np.where(df['Price'] > df['MA_5'], 1,
                               np.where(df['Price'] < df['MA_5'], -1, 0))

    # MA10 Score
    df['Score_MA10'] = np.where(df['Price'] > df['MA_10'], 1,
                                np.where(df['Price'] < df['MA_10'], -1, 0))

    # RSI Score (50-75: +1, 30-50: 0, else: -1)
    df['Score_RSI'] = np.where((df['RSI_Score'] >= 50) & (df['RSI_Score'] <= 75), 1,
                               np.where((df['RSI_Score'] > 30) & (df['RSI_Score'] < 50), 0, -1))

    # SuperTrend Score
    df['Score_SuperTrend'] = np.where(df['SuperTrend_Direction'] == 1, 1,
                                      np.where(df['SuperTrend_Direction'] == -1, -1, 0))

    # Vol Osc Result
    def vol_osc_result(row):
        if pd.isna(row['Vol_Osc']) or pd.isna(row['MA_5']) or pd.isna(row['MA_10']):
            return "N/A"
        price = row['Price']
        ma5 = row['MA_5']
        ma10 = row['MA_10']
        vol_osc = row['Vol_Osc']
        price_above_ma = price > ma5 and price > ma10
        price_below_ma = price < ma5 and price < ma10

        if price_above_ma and vol_osc >= 20:
            return "STRONG"
        elif price_above_ma and vol_osc <= -15:
            return "BEARISH INDICATOR"
        elif price_below_ma and vol_osc >= 20:
            return "ACCUM"
        elif price_below_ma and vol_osc <= -15:
            return "CONFIRM BEARISH"
        elif vol_osc > 0:
            return "UP"
        else:
            return "DOWN"

    df['Vol_Osc_Result'] = df.apply(vol_osc_result, axis=1)

    # Vol Osc Score
    df['Score_VolOsc'] = df['Vol_Osc_Result'].map({
        'STRONG': 1, 'ACCUM': 1, 'UP': 1,
        'BEARISH INDICATOR': -1, 'CONFIRM BEARISH': -1, 'DOWN': -1,
        'N/A': 0
    }).fillna(0).astype(int)

    # Total Indicator
    df['Indicator'] = (df['Score_MA5'] + df['Score_MA10'] + df['Score_RSI'] +
                       df['Score_SuperTrend'] + df['Score_VolOsc'])

    return df


def backtest_strategy(df, buy_threshold, sell_threshold, initial_capital=10000000):
    """
    Backtest the indicator strategy

    Parameters:
    - buy_threshold: Buy when Indicator >= this value
    - sell_threshold: Sell when Indicator <= this value
    - initial_capital: Starting capital in IDR

    Returns:
    - Dictionary with performance metrics
    """
    df = df.copy()
    df = df.dropna()

    if len(df) < 30:
        return None

    capital = initial_capital
    shares = 0
    position = 'CASH'  # CASH or HOLDING
    trades = []
    buy_price = 0

    for i in range(len(df)):
        row = df.iloc[i]
        indicator = row['Indicator']
        price = row['Price']
        date = df.index[i]

        # Buy Signal
        if position == 'CASH' and indicator >= buy_threshold:
            shares = capital // price
            if shares > 0:
                capital -= shares * price
                position = 'HOLDING'
                buy_price = price
                trades.append({
                    'date': date,
                    'action': 'BUY',
                    'price': price,
                    'shares': shares,
                    'indicator': indicator
                })

        # Sell Signal
        elif position == 'HOLDING' and indicator <= sell_threshold:
            capital += shares * price
            pnl_pct = ((price - buy_price) / buy_price) * 100
            trades.append({
                'date': date,
                'action': 'SELL',
                'price': price,
                'shares': shares,
                'indicator': indicator,
                'pnl_pct': pnl_pct
            })
            shares = 0
            position = 'CASH'
            buy_price = 0

    # Final valuation
    final_price = df.iloc[-1]['Price']
    final_value = capital + (shares * final_price)
    total_return = ((final_value - initial_capital) / initial_capital) * 100

    # Buy and hold comparison
    buy_hold_shares = initial_capital // df.iloc[0]['Price']
    buy_hold_value = buy_hold_shares * final_price
    buy_hold_return = ((buy_hold_value - initial_capital) / initial_capital) * 100

    # Calculate win rate
    sell_trades = [t for t in trades if t['action'] == 'SELL']
    if sell_trades:
        winning_trades = [t for t in sell_trades if t.get('pnl_pct', 0) > 0]
        win_rate = (len(winning_trades) / len(sell_trades)) * 100
        avg_win = np.mean([t['pnl_pct'] for t in winning_trades]) if winning_trades else 0
        losing_trades = [t for t in sell_trades if t.get('pnl_pct', 0) <= 0]
        avg_loss = np.mean([t['pnl_pct'] for t in losing_trades]) if losing_trades else 0
    else:
        win_rate = 0
        avg_win = 0
        avg_loss = 0

    return {
        'buy_threshold': buy_threshold,
        'sell_threshold': sell_threshold,
        'initial_capital': initial_capital,
        'final_value': final_value,
        'total_return_pct': total_return,
        'buy_hold_return_pct': buy_hold_return,
        'outperformance': total_return - buy_hold_return,
        'num_trades': len(trades),
        'num_sells': len(sell_trades),
        'win_rate': win_rate,
        'avg_win_pct': avg_win,
        'avg_loss_pct': avg_loss,
        'final_position': position,
        'trades': trades
    }


def run_backtest_grid(ticker, period='2y'):
    """
    Run backtest with multiple threshold combinations

    Parameters:
    - ticker: Stock ticker (e.g., "RATU.JK")
    - period: Data period (e.g., "1y", "2y", "5y")
    """
    print(f"\n{'='*70}")
    print(f"BACKTESTING: {ticker}")
    print(f"Period: {period}")
    print(f"{'='*70}\n")

    # Fetch data
    print("Fetching data...")
    df = yf.download(ticker, period=period, interval='1d', progress=False)

    if df.empty:
        print(f"Error: No data returned for {ticker}")
        return None

    print(f"Data points: {len(df)} days")
    print(f"Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")

    # Calculate indicators
    print("Calculating indicators...")
    df = calculate_indicators(df)

    # Drop rows with NaN
    df = df.dropna()
    print(f"Valid data points: {len(df)} days\n")

    # Indicator distribution
    print("Indicator Distribution:")
    print(df['Indicator'].value_counts().sort_index())
    print()

    # Test different threshold combinations
    results = []

    # Buy thresholds: 0 to 5
    # Sell thresholds: -5 to 0
    for buy_thresh in range(-2, 6):  # -2 to 5
        for sell_thresh in range(-5, buy_thresh):  # Must be less than buy threshold
            result = backtest_strategy(df, buy_thresh, sell_thresh)
            if result:
                results.append(result)

    if not results:
        print("No valid backtest results")
        return None

    # Convert to DataFrame
    results_df = pd.DataFrame(results)

    # Sort by total return
    results_df = results_df.sort_values('total_return_pct', ascending=False)

    return results_df, df


def print_results(results_df, top_n=10):
    """Print top backtest results"""
    print(f"\n{'='*70}")
    print(f"TOP {top_n} STRATEGIES BY TOTAL RETURN")
    print(f"{'='*70}\n")

    for i, row in results_df.head(top_n).iterrows():
        print(f"Strategy #{results_df.head(top_n).index.get_loc(i) + 1}")
        print(f"  Buy when Indicator >= {row['buy_threshold']}")
        print(f"  Sell when Indicator <= {row['sell_threshold']}")
        print(f"  Total Return: {row['total_return_pct']:.2f}%")
        print(f"  Buy & Hold Return: {row['buy_hold_return_pct']:.2f}%")
        print(f"  Outperformance: {row['outperformance']:.2f}%")
        print(f"  Number of Trades: {row['num_trades']}")
        print(f"  Win Rate: {row['win_rate']:.1f}%")
        print(f"  Avg Win: {row['avg_win_pct']:.2f}% | Avg Loss: {row['avg_loss_pct']:.2f}%")
        print()


def analyze_best_strategy(results_df, df, strategy_idx=0):
    """Detailed analysis of a specific strategy"""
    strategy = results_df.iloc[strategy_idx]

    print(f"\n{'='*70}")
    print("DETAILED ANALYSIS - BEST STRATEGY")
    print(f"{'='*70}\n")

    print(f"Buy Threshold: >= {strategy['buy_threshold']}")
    print(f"Sell Threshold: <= {strategy['sell_threshold']}")
    print(f"\nPerformance:")
    print(f"  Total Return: {strategy['total_return_pct']:.2f}%")
    print(f"  Buy & Hold: {strategy['buy_hold_return_pct']:.2f}%")
    print(f"  Outperformance: {strategy['outperformance']:.2f}%")
    print(f"\nTrading Stats:")
    print(f"  Total Trades: {strategy['num_trades']}")
    print(f"  Completed Trades (Sells): {strategy['num_sells']}")
    print(f"  Win Rate: {strategy['win_rate']:.1f}%")
    print(f"  Average Win: {strategy['avg_win_pct']:.2f}%")
    print(f"  Average Loss: {strategy['avg_loss_pct']:.2f}%")
    print(f"  Final Position: {strategy['final_position']}")

    # Print trade history
    if strategy['trades']:
        print(f"\nTrade History:")
        print("-" * 60)
        for trade in strategy['trades']:
            if trade['action'] == 'BUY':
                print(f"  {trade['date'].strftime('%Y-%m-%d')} | BUY  | Price: {trade['price']:.0f} | Indicator: {trade['indicator']}")
            else:
                print(f"  {trade['date'].strftime('%Y-%m-%d')} | SELL | Price: {trade['price']:.0f} | Indicator: {trade['indicator']} | P&L: {trade['pnl_pct']:+.2f}%")


def main():
    """Main function to run backtests"""

    # Tickers to test
    tickers = ["RATU.JK", "IMPC.JK", "BKSL.JK"]

    all_results = {}

    for ticker in tickers:
        try:
            results_df, df = run_backtest_grid(ticker, period='2y')

            if results_df is not None:
                all_results[ticker] = results_df
                print_results(results_df, top_n=5)
                analyze_best_strategy(results_df, df)

        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            continue

    # Summary across all stocks
    print(f"\n{'='*70}")
    print("SUMMARY - RECOMMENDED THRESHOLDS")
    print(f"{'='*70}\n")

    # Find common best thresholds
    best_strategies = []
    for ticker, results_df in all_results.items():
        if len(results_df) > 0:
            # Get top 3 strategies that outperform buy & hold
            outperformers = results_df[results_df['outperformance'] > 0].head(3)
            for _, row in outperformers.iterrows():
                best_strategies.append({
                    'ticker': ticker,
                    'buy_threshold': row['buy_threshold'],
                    'sell_threshold': row['sell_threshold'],
                    'outperformance': row['outperformance'],
                    'win_rate': row['win_rate']
                })

    if best_strategies:
        best_df = pd.DataFrame(best_strategies)

        # Most common buy thresholds
        print("Most Common Buy Thresholds (among profitable strategies):")
        print(best_df['buy_threshold'].value_counts().head())

        print("\nMost Common Sell Thresholds (among profitable strategies):")
        print(best_df['sell_threshold'].value_counts().head())

        # Overall recommendation
        avg_buy = best_df['buy_threshold'].mode().iloc[0] if len(best_df) > 0 else 2
        avg_sell = best_df['sell_threshold'].mode().iloc[0] if len(best_df) > 0 else -2

        print(f"\n" + "="*70)
        print("RECOMMENDED STRATEGY:")
        print(f"  BUY when Indicator >= {avg_buy}")
        print(f"  HOLD when {avg_sell} < Indicator < {avg_buy}")
        print(f"  SELL when Indicator <= {avg_sell}")
        print("="*70)


if __name__ == "__main__":
    main()
