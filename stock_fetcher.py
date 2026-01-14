import yfinance as yf
import pandas_ta as ta
import pandas as pd
from datetime import datetime

class StockDataFetcher:
    """
    Fetches and processes stock data with technical indicators.
    """

    def __init__(self):
        self.cache = {}

    # Interval to period mapping for yfinance
    # yfinance limits: 1m (7d), 2m/5m/15m/30m (60d), 60m/1h (730d), 1d+ (unlimited)
    INTERVAL_PERIODS = {
        '1m': '5d',      # 1 minute - max 7 days
        '5m': '30d',     # 5 minutes - max 60 days
        '15m': '30d',    # 15 minutes - max 60 days
        '30m': '30d',    # 30 minutes - max 60 days
        '1h': '60d',     # 1 hour - max 730 days
        '4h': '60d',     # 4 hours - max 730 days (yfinance uses 60m internally)
        '1d': '6mo',     # 1 day - unlimited
        '1wk': '2y',     # 1 week - unlimited
    }

    def get_stock_data(self, ticker, bars=30, interval='1d'):
        """
        Fetch stock data and calculate technical indicators.

        Args:
            ticker (str): Stock ticker symbol (e.g., "RATU.JK")
            bars (int): Number of bars/candles to display (default: 30)
            interval (str): Time interval - '1m', '5m', '15m', '30m', '1h', '4h', '1d', '1wk'

        Returns:
            pd.DataFrame: DataFrame with technical indicators
        """
        try:
            print(f"    Fetching {interval} data for {ticker}...")

            # Get appropriate period for the interval
            period = self.INTERVAL_PERIODS.get(interval, '6mo')

            # Handle 4h interval (yfinance doesn't support 4h directly)
            yf_interval = '60m' if interval == '4h' else interval

            # Fetch data
            df = yf.download(ticker, period=period, interval=yf_interval, progress=False)

            # For 4h interval, resample from 1h data
            if interval == '4h' and not df.empty:
                df = df.resample('4h').agg({
                    'Open': 'first',
                    'High': 'max',
                    'Low': 'min',
                    'Close': 'last',
                    'Volume': 'sum'
                }).dropna()

            if df.empty:
                print(f"    Warning: No data returned for {ticker}")
                return None

            # Flatten Multi-Index Columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Calculate Price
            df['Price'] = df['Close']

            # Moving Averages
            df['MA_5'] = ta.sma(df['Close'], length=5)
            df['MA_10'] = ta.sma(df['Close'], length=10)

            # RSI (Standard 14)
            df['RSI_Score'] = ta.rsi(df['Close'], length=14)

            # SuperTrend (Length 10, Factor 3)
            st_data = ta.supertrend(df['High'], df['Low'], df['Close'], length=10, multiplier=3)

            if st_data is not None and not st_data.empty:
                st_value_col = st_data.columns[0]  # SUPERT_10_3.0
                st_dir_col = st_data.columns[1]    # SUPERTd_10_3.0

                df['SuperTrend_Line'] = st_data[st_value_col]
                df['SuperTrend_Direction'] = st_data[st_dir_col]

                # Create readable SuperTrend column
                df['SuperTrend'] = df.apply(
                    lambda row: f"{row['SuperTrend_Line']:.0f}" if pd.notna(row['SuperTrend_Line']) else "N/A",
                    axis=1
                )
                df['SuperTrend_Color'] = df['SuperTrend_Direction'].apply(
                    lambda x: 'GREEN' if x == 1 else 'RED' if x == -1 else 'NEUTRAL'
                )
            else:
                df['SuperTrend'] = "N/A"
                df['SuperTrend_Color'] = "NEUTRAL"

            # Volume Oscillator (Short 5, Long 10)
            vol_short = ta.sma(df['Volume'], length=5)
            vol_long = ta.sma(df['Volume'], length=10)
            df['Vol_Osc'] = ((vol_short - vol_long) / vol_long) * 100

            # Vol Osc Result based on Price vs MA and Vol Osc criteria:
            # - Price > MA5 & MA10; Osc +20% -> STRONG
            # - Price > MA5 & MA10; Osc -15% -> BEARISH INDICATOR
            # - Price < MA5 & MA10; Osc +20% -> ACCUM
            # - Price < MA5 & MA10; Osc -15% -> CONFIRM BEARISH
            def determine_vol_osc_result(row):
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

            df['Vol_Osc_Result'] = df.apply(determine_vol_osc_result, axis=1)

            # Calculate indicator scores for each column
            # MA5: Green (+1) if Price > MA5, Red (-1) if Price < MA5, Yellow (0) if equal
            def score_ma5(row):
                if pd.isna(row['MA_5']):
                    return 0
                if row['Price'] > row['MA_5']:
                    return 1
                elif row['Price'] < row['MA_5']:
                    return -1
                return 0

            # MA10: Green (+1) if Price > MA10, Red (-1) if Price < MA10, Yellow (0) if equal
            def score_ma10(row):
                if pd.isna(row['MA_10']):
                    return 0
                if row['Price'] > row['MA_10']:
                    return 1
                elif row['Price'] < row['MA_10']:
                    return -1
                return 0

            # RSI Scoring Rules:
            # Red (-1): RSI > 75 (Overbought) OR RSI <= 30 (Oversold)
            # Green (+1): RSI between 50 and 75
            # Yellow (0): RSI between 30 and 50
            def score_rsi(row):
                if pd.isna(row['RSI_Score']):
                    return 0
                rsi = row['RSI_Score']
                if rsi > 75:
                    return -1  # Overbought - Red
                elif rsi <= 30:
                    return -1  # Oversold - Red
                elif 50 <= rsi <= 75:
                    return 1   # Good momentum - Green
                else:  # 30 < rsi < 50
                    return 0   # Neutral - Yellow

            # SuperTrend: Green (+1), Red (-1)
            def score_supertrend(row):
                if row['SuperTrend_Color'] == 'GREEN':
                    return 1
                elif row['SuperTrend_Color'] == 'RED':
                    return -1
                return 0

            # Vol Osc Result: STRONG/ACCUM/UP (+1), BEARISH INDICATOR/CONFIRM BEARISH/DOWN (-1), others (0)
            def score_vol_osc(row):
                result = row['Vol_Osc_Result']
                if result in ['STRONG', 'ACCUM', 'UP']:
                    return 1
                elif result in ['BEARISH INDICATOR', 'CONFIRM BEARISH', 'DOWN']:
                    return -1
                return 0

            df['Score_MA5'] = df.apply(score_ma5, axis=1)
            df['Score_MA10'] = df.apply(score_ma10, axis=1)
            df['Score_RSI'] = df.apply(score_rsi, axis=1)
            df['Score_SuperTrend'] = df.apply(score_supertrend, axis=1)
            df['Score_VolOsc'] = df.apply(score_vol_osc, axis=1)

            # Total Indicator Score (sum of all scores)
            df['Indicator'] = df['Score_MA5'] + df['Score_MA10'] + df['Score_RSI'] + df['Score_SuperTrend'] + df['Score_VolOsc']

            # Select relevant columns and last N days
            final_cols = [
                'Price', 'MA_5', 'MA_10', 'RSI_Score',
                'SuperTrend', 'SuperTrend_Color',
                'Vol_Osc', 'Vol_Osc_Result',
                'Score_MA5', 'Score_MA10', 'Score_RSI', 'Score_SuperTrend', 'Score_VolOsc',
                'Indicator'
            ]

            result_df = df[final_cols].tail(bars).copy()

            # Add date column - format based on interval
            # Convert to Indonesian time (WIB = UTC+7)
            import pytz
            wib = pytz.timezone('Asia/Jakarta')

            if interval in ['1m', '5m', '15m', '30m', '1h', '4h']:
                # Convert index to WIB timezone and format
                result_df['Date'] = result_df.index.tz_convert(wib).strftime('%Y-%m-%d %H:%M')
            else:
                # For daily/weekly data, just show date (no timezone conversion needed)
                result_df['Date'] = result_df.index.strftime('%Y-%m-%d')

            # Round numeric columns for cleaner display
            numeric_cols = ['Price', 'MA_5', 'MA_10', 'RSI_Score', 'Vol_Osc']
            for col in numeric_cols:
                if col in result_df.columns:
                    result_df[col] = result_df[col].round(2)

            # Reorder columns with Date first
            result_df = result_df[['Date'] + final_cols]

            print(f"    ✓ Successfully fetched {len(result_df)} bars of {interval} data")
            return result_df

        except Exception as e:
            print(f"    ✗ Error fetching {ticker}: {e}")
            return None

    def get_latest_summary(self, ticker):
        """
        Get a summary of the latest indicators for a stock.

        Args:
            ticker (str): Stock ticker symbol

        Returns:
            dict: Summary of latest indicators
        """
        try:
            df = self.get_stock_data(ticker, days=1)

            if df is None or df.empty:
                return None

            latest = df.iloc[-1]

            summary = {
                'ticker': ticker,
                'date': latest['Date'],
                'price': latest['Price'],
                'ma_5': latest['MA_5'],
                'ma_10': latest['MA_10'],
                'rsi': latest['RSI_Score'],
                'supertrend': latest['SuperTrend'],
                'supertrend_color': latest['SuperTrend_Color'],
                'vol_osc': latest['Vol_Osc'],
                'vol_osc_result': latest['Vol_Osc_Result'],
                'trend': self._determine_trend(latest)
            }

            return summary

        except Exception as e:
            print(f"Error getting summary for {ticker}: {e}")
            return None

    def _determine_trend(self, row):
        """
        Determine overall trend based on indicators.

        Args:
            row: DataFrame row with indicator values

        Returns:
            str: 'BULLISH', 'BEARISH', or 'NEUTRAL'
        """
        bullish_signals = 0
        bearish_signals = 0

        # Check MA crossover
        if pd.notna(row['MA_5']) and pd.notna(row['MA_10']):
            if row['MA_5'] > row['MA_10']:
                bullish_signals += 1
            else:
                bearish_signals += 1

        # Check SuperTrend
        if row['SuperTrend_Color'] == 'GREEN':
            bullish_signals += 1
        elif row['SuperTrend_Color'] == 'RED':
            bearish_signals += 1

        # Check Volume
        if row['Vol_Osc_Result'] == 'UP':
            bullish_signals += 1
        elif row['Vol_Osc_Result'] == 'DOWN':
            bearish_signals += 1

        if bullish_signals > bearish_signals:
            return 'BULLISH'
        elif bearish_signals > bullish_signals:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
