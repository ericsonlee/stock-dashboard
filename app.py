from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import threading
import time
import os
from datetime import datetime
import pytz
from stock_fetcher import StockDataFetcher

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Access code for login (set via environment variable)
ACCESS_CODE = os.environ.get('ACCESS_CODE', 'saham123')

# Global storage for stock data
stock_data_cache = {}
last_update_time = None
current_interval = '1h'  # Default interval (1h works better on Railway)

# Live Monitor cache (to reduce API calls)
live_monitor_cache = {
    'data': None,
    'last_update': None,
    'cache_duration': 120  # Cache for 2 minutes
}

# Indonesian timezone (WIB = UTC+7)
WIB = pytz.timezone('Asia/Jakarta')

def get_wib_time():
    """Get current time in Indonesian timezone (WIB)"""
    return datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S')

def is_trading_hours():
    """Check if current time is within Indonesian trading hours (9:00-16:00 WIB, Mon-Fri)"""
    now = datetime.now(WIB)
    day = now.weekday()  # 0=Monday, 6=Sunday
    hour = now.hour

    # Check if weekday (Mon-Fri = 0-4)
    if day > 4:  # Saturday or Sunday
        return False

    # Check if within 9:00-16:00 WIB
    return 9 <= hour < 16

# Configuration
TICKERS = ["RATU.JK", "IMPC.JK", "BKSL.JK"]
UPDATE_INTERVAL = 300  # Update every 5 minutes
DEFAULT_BARS = 50  # Number of bars to show

# Available intervals
INTERVALS = {
    '5m': '5 Minutes',
    '1h': '1 Hour',
    '1d': '1 Day'
}

# Initialize stock fetcher
fetcher = StockDataFetcher()

def fetch_all_stocks(interval='1d', bars=DEFAULT_BARS):
    """Fetch data for all tickers with specified interval"""
    global stock_data_cache, last_update_time, current_interval

    current_interval = interval

    for ticker in TICKERS:
        try:
            data = fetcher.get_stock_data(ticker, bars=bars, interval=interval)
            if data is not None:
                stock_data_cache[ticker] = {
                    'data': data.to_dict('records'),
                    'ticker': ticker,
                    'interval': interval,
                    'last_update': get_wib_time()
                }
                print(f"  ✓ Updated {ticker} ({interval})")
            else:
                print(f"  ✗ Failed to fetch {ticker}")
        except Exception as e:
            print(f"  ✗ Error fetching {ticker}: {e}")

    last_update_time = get_wib_time()

def update_stock_data():
    """Background thread to update stock data periodically (only during trading hours)"""
    global stock_data_cache, last_update_time, current_interval

    while True:
        if is_trading_hours():
            try:
                print(f"[{get_wib_time()}] Updating stock data ({current_interval})...")
                fetch_all_stocks(interval=current_interval, bars=DEFAULT_BARS)
                print(f"[{last_update_time}] Stock data update complete\n")
            except Exception as e:
                print(f"Error in update thread: {e}")
        else:
            print(f"[{get_wib_time()}] Outside trading hours, skipping background update")

        time.sleep(UPDATE_INTERVAL)

def check_auth():
    """Check if user is authenticated"""
    return session.get('authenticated', False)

@app.route('/')
def index():
    """Main dashboard page"""
    if not check_auth():
        return redirect(url_for('login'))
    return render_template('dashboard.html',
                          tickers=TICKERS,
                          intervals=INTERVALS,
                          current_interval=current_interval,
                          update_interval=UPDATE_INTERVAL)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page with access code"""
    error = None
    if request.method == 'POST':
        code = request.form.get('code', '')
        if code == ACCESS_CODE:
            session['authenticated'] = True
            return redirect(url_for('index'))
        else:
            error = 'Invalid access code'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/stocks')
def get_stocks():
    """API endpoint to get all stock data"""
    if not check_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({
        'stocks': stock_data_cache,
        'last_update': last_update_time,
        'tickers': TICKERS,
        'current_interval': current_interval
    })

@app.route('/api/stock/<ticker>')
def get_stock(ticker):
    """API endpoint to get specific stock data"""
    if not check_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    if ticker in stock_data_cache:
        return jsonify(stock_data_cache[ticker])
    else:
        return jsonify({'error': 'Stock not found'}), 404

@app.route('/api/refresh')
def refresh_data():
    """Force refresh all stock data with optional interval parameter"""
    if not check_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    global stock_data_cache, last_update_time, current_interval

    interval = request.args.get('interval', current_interval)
    bars = int(request.args.get('bars', DEFAULT_BARS))

    try:
        print(f"[{get_wib_time()}] Manual refresh ({interval})...")
        fetch_all_stocks(interval=interval, bars=bars)
        return jsonify({
            'success': True,
            'last_update': last_update_time,
            'interval': interval
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/set_interval/<interval>')
def set_interval(interval):
    """Change the current interval and refresh data"""
    if not check_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    global current_interval

    if interval not in INTERVALS:
        return jsonify({'error': f'Invalid interval. Choose from: {list(INTERVALS.keys())}'}), 400

    try:
        print(f"[{get_wib_time()}] Changing interval to {interval}...")
        fetch_all_stocks(interval=interval, bars=DEFAULT_BARS)
        return jsonify({
            'success': True,
            'last_update': last_update_time,
            'interval': interval
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/add_stock/<ticker>')
def add_stock(ticker):
    """Add a new stock ticker"""
    if not check_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    global stock_data_cache

    # Normalize ticker (uppercase)
    ticker = ticker.upper()

    # Check if already exists
    if ticker in TICKERS:
        return jsonify({'success': False, 'error': f'{ticker} already exists'}), 400

    try:
        print(f"[{get_wib_time()}] Adding stock {ticker}...")
        data = fetcher.get_stock_data(ticker, bars=DEFAULT_BARS, interval=current_interval)

        if data is None or data.empty:
            return jsonify({'success': False, 'error': f'No data found for {ticker}. Check if the ticker is valid.'}), 404

        # Add to tickers list and cache
        TICKERS.append(ticker)
        stock_data_cache[ticker] = {
            'data': data.to_dict('records'),
            'ticker': ticker,
            'interval': current_interval,
            'last_update': get_wib_time()
        }

        print(f"  ✓ Added {ticker}")
        return jsonify({
            'success': True,
            'ticker': ticker,
            'tickers': TICKERS
        })
    except Exception as e:
        print(f"  ✗ Error adding {ticker}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/remove_stock/<ticker>')
def remove_stock(ticker):
    """Remove a stock ticker"""
    if not check_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    global stock_data_cache

    # Normalize ticker (uppercase)
    ticker = ticker.upper()

    if ticker not in TICKERS:
        return jsonify({'success': False, 'error': f'{ticker} not found'}), 404

    # Don't allow removing all stocks
    if len(TICKERS) <= 1:
        return jsonify({'success': False, 'error': 'Cannot remove the last stock'}), 400

    try:
        TICKERS.remove(ticker)
        if ticker in stock_data_cache:
            del stock_data_cache[ticker]

        print(f"[{get_wib_time()}] Removed {ticker}")
        return jsonify({
            'success': True,
            'ticker': ticker,
            'tickers': TICKERS
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/live_monitor')
def get_live_monitor_data():
    """API endpoint for Live Monitor - returns 1D signals + 5M live data (cached for 2 min)"""
    if not check_auth():
        return jsonify({'error': 'Unauthorized'}), 401

    global live_monitor_cache

    # Check if cache is still valid
    now = datetime.now(WIB)
    if (live_monitor_cache['data'] is not None and
        live_monitor_cache['last_update'] is not None):
        cache_age = (now - live_monitor_cache['last_update']).total_seconds()
        if cache_age < live_monitor_cache['cache_duration']:
            print(f"[{get_wib_time()}] Returning cached Live Monitor data (age: {cache_age:.0f}s)")
            return jsonify(live_monitor_cache['data'])

    print(f"[{get_wib_time()}] Fetching fresh Live Monitor data...")

    daily_signals = {}
    live_data = {}

    for ticker in TICKERS:
        try:
            # Fetch 1D data for signals (just need latest row)
            daily_df = fetcher.get_stock_data(ticker, bars=5, interval='1d')
            if daily_df is not None and not daily_df.empty:
                latest_daily = daily_df.iloc[-1].to_dict()
                daily_signals[ticker] = {
                    'indicator': latest_daily.get('Indicator', 0),
                    'indicator_diff': latest_daily.get('Indicator_Diff', 0),
                    'price': latest_daily.get('Price', 0),
                    'date': latest_daily.get('Date', 'N/A')
                }
            else:
                daily_signals[ticker] = {
                    'indicator': 0,
                    'indicator_diff': 0,
                    'price': 0,
                    'date': 'N/A',
                    'error': 'No daily data'
                }

            # Fetch 5M data for live monitoring
            live_df = fetcher.get_stock_data(ticker, bars=30, interval='5m')
            if live_df is not None and not live_df.empty:
                live_data[ticker] = {
                    'data': live_df.to_dict('records'),
                    'ticker': ticker,
                    'interval': '5m',
                    'last_update': get_wib_time()
                }
            else:
                live_data[ticker] = {
                    'data': [],
                    'ticker': ticker,
                    'interval': '5m',
                    'last_update': get_wib_time(),
                    'error': 'No 5M data'
                }

            print(f"  ✓ Live Monitor: {ticker}")
        except Exception as e:
            print(f"  ✗ Live Monitor error {ticker}: {e}")
            daily_signals[ticker] = {'indicator': 0, 'indicator_diff': 0, 'price': 0, 'date': 'N/A', 'error': str(e)}
            live_data[ticker] = {'data': [], 'ticker': ticker, 'interval': '5m', 'error': str(e)}

    response_data = {
        'daily_signals': daily_signals,
        'live_data': live_data,
        'tickers': TICKERS,
        'last_update': get_wib_time()
    }

    # Update cache
    live_monitor_cache['data'] = response_data
    live_monitor_cache['last_update'] = now

    return jsonify(response_data)

# Initialize on startup (works with both direct run and gunicorn)
def init_app():
    print("Performing initial data fetch...")
    fetch_all_stocks(interval=current_interval, bars=DEFAULT_BARS)

    # Start background update thread
    update_thread = threading.Thread(target=update_stock_data, daemon=True)
    update_thread.start()
    print(f"Background updater started (interval: {UPDATE_INTERVAL}s)")

# Run initialization
init_app()

if __name__ == '__main__':
    # Start Flask app (local development)
    print("\nStarting Flask server...")
    print("Dashboard available at: http://127.0.0.1:5000")
    print("Press CTRL+C to stop\n")

    app.run(debug=True, use_reloader=False)
