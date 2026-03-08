import yfinance as yf

tech=yf.Ticker("JPM").get_info().get("sector")

ticker=yf.Ticker("AAPL")
press_releases = ticker.get_news(10,"news")
print(press_releases)

