# Indonesian Stock Dashboard

A real-time web dashboard for monitoring Indonesian stocks with technical analysis indicators.

## Features

- **Live Data Scraping**: Fetches real-time stock data using yfinance
- **Technical Indicators**:
  - Price and Moving Averages (MA 5, MA 10)
  - RSI (Relative Strength Index)
  - SuperTrend indicator
  - Volume Oscillator
- **Auto-Refresh**: Background updates every 5 minutes
- **Beautiful UI**: Color-coded indicators for easy visualization
- **Multi-Stock Support**: Monitor multiple stocks simultaneously

## Currently Tracked Stocks

- RATU.JK (Ratu Prabu Energi)
- IMPC.JK (Impack Pratama Industri)

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup Steps

1. **Navigate to the dashboard directory**:
   ```bash
   cd "c:\Users\erics\Documents\Saham Indo\stock-dashboard"
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - Mac/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Dashboard

1. **Start the server**:
   ```bash
   python app.py
   ```

2. **Open your browser** and navigate to:
   ```
   http://127.0.0.1:5000
   ```

3. **Stop the server**: Press `CTRL+C` in the terminal

## Configuration

### Adding More Stocks

Edit [app.py](app.py:14) and modify the `TICKERS` list:

```python
TICKERS = ["RATU.JK", "IMPC.JK", "BBCA.JK", "TLKM.JK"]
```

### Changing Update Interval

Edit [app.py](app.py:15) and modify the `UPDATE_INTERVAL` (in seconds):

```python
UPDATE_INTERVAL = 300  # 5 minutes
```

### Adjusting Number of Days Displayed

Edit [app.py](app.py:32) and change the `days` parameter:

```python
data = fetcher.get_stock_data(ticker, days=60)  # Show 60 days
```

## Color Coding

### SuperTrend
- 🟢 **Green Background**: Bullish trend (BUY signal)
- 🔴 **Red Background**: Bearish trend (SELL signal)

### Volume Oscillator Result
- 🟢 **Green Background**: Volume increasing (UP)
- 🔴 **Red Background**: Volume decreasing (DOWN)

### RSI Score
- 🟢 **Green Background**: Oversold (RSI ≤ 30) - potential buying opportunity
- 🔴 **Red Background**: Overbought (RSI ≥ 70) - potential selling opportunity
- ⚪ **White Background**: Neutral (RSI between 30-70)

## API Endpoints

The dashboard provides the following API endpoints:

- `GET /` - Main dashboard page
- `GET /api/stocks` - Get all stock data in JSON format
- `GET /api/stock/<ticker>` - Get specific stock data
- `GET /api/refresh` - Force refresh all stock data

## Project Structure

```
stock-dashboard/
├── app.py                  # Main Flask application
├── stock_fetcher.py        # Stock data fetching and processing
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── templates/
│   └── dashboard.html     # Main dashboard HTML template
└── static/                # (Optional) Static assets
```

## Troubleshooting

### Port Already in Use

If port 5000 is already in use, modify [app.py](app.py:118) at the bottom:

```python
app.run(debug=True, use_reloader=False, port=5001)
```

### Data Not Loading

1. Check your internet connection
2. Verify the stock tickers are correct (must include `.JK` for Jakarta stocks)
3. Check the terminal for error messages

### Import Errors

Make sure you've activated the virtual environment and installed all dependencies:

```bash
pip install -r requirements.txt
```

## Dependencies

- **Flask**: Web framework for the dashboard
- **yfinance**: Yahoo Finance API wrapper for stock data
- **pandas-ta**: Technical analysis library
- **pandas**: Data manipulation and analysis

## Notes

- Data is fetched from Yahoo Finance, which may have delays or limitations
- The dashboard runs locally and doesn't require a database
- Background updates happen every 5 minutes by default
- Browser auto-refreshes the display every minute for real-time feel

## Future Enhancements

Potential improvements:
- Add more technical indicators (MACD, Bollinger Bands, etc.)
- Export data to CSV/Excel
- Price alerts and notifications
- Historical chart visualization
- Compare multiple stocks side-by-side
- Mobile-responsive design improvements

## License

This project is for personal use. Use at your own risk.

## Disclaimer

This dashboard is for informational purposes only and should not be considered financial advice. Always do your own research before making investment decisions.
