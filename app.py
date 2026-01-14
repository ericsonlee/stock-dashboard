from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import threading
import time
import os
from datetime import datetime
from stock_fetcher import StockDataFetcher

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Access code for login (set via environment variable)
ACCESS_CODE = os.environ.get('ACCESS_CODE', 'saham123')

# Global storage for stock data
stock_data_cache = {}
last_update_time = None
current_interval = '1d'  # Default interval

# Configuration
TICKERS = ["RATU.JK", "IMPC.JK", "BKSL.JK"]
UPDATE_INTERVAL = 300  # Update every 5 minutes
DEFAULT_BARS = 50  # Number of bars to show

# Available intervals
INTERVALS = {
    '5m': '5 Minutes',
    '15m': '15 Minutes',
    '30m': '30 Minutes',
    '1h': '1 Hour',
    '4h': '4 Hours',
    '1d': '1 Day',
    '1wk': '1 Week'
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
                    'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                print(f"  ✓ Updated {ticker} ({interval})")
            else:
                print(f"  ✗ Failed to fetch {ticker}")
        except Exception as e:
            print(f"  ✗ Error fetching {ticker}: {e}")

    last_update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def update_stock_data():
    """Background thread to update stock data periodically"""
    global stock_data_cache, last_update_time, current_interval

    while True:
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Updating stock data ({current_interval})...")
            fetch_all_stocks(interval=current_interval, bars=DEFAULT_BARS)
            print(f"[{last_update_time}] Stock data update complete\n")
        except Exception as e:
            print(f"Error in update thread: {e}")

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
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Manual refresh ({interval})...")
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
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Changing interval to {interval}...")
        fetch_all_stocks(interval=interval, bars=DEFAULT_BARS)
        return jsonify({
            'success': True,
            'last_update': last_update_time,
            'interval': interval
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
