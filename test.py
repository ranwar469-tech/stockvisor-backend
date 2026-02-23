import yfinance as yf

ticker = yf.Ticker("AAPL")
current_price = ticker.fast_info['last_price']
print(f"Current Price: {current_price}")