# Finance

A Flask stock trading simulator with authentication, live stock price updates, search, watchlist, holdings, and buy/sell trade flows.

The app uses SQLite through the CS50 library, `yfinance` for market data, and Flask-SocketIO for periodic live price updates.

## Features

- Register and log in users.
- View a dashboard with cash balance, holdings, watchlist, and live stock prices.
- Search stocks by ticker or company name.
- Buy and sell shares using simulated cash.
- Stream live price updates for common symbols.

## Tech Stack

- Python
- Flask
- Flask-SocketIO
- SQLite / CS50 SQL
- yfinance

## Run Locally

```bash
python -m pip install -r requirements.txt
python app.py
```

If running through Flask instead:

```bash
flask --app app run
```

## Important Files

- `app.py` - Main Flask app, routes, stock polling, and trading logic.
- `templates/` - HTML pages for auth, dashboard, search, and trading.
- `css/` - Page-level stylesheets.
- `finance.db` - Local SQLite database.
- `requirements.txt` - Python dependencies.
