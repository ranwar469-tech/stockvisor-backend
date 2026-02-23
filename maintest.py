from fastapi import FastAPI
import yfinance as yf

app = FastAPI()

ticker = yf.Ticker("AAPL")
current_price = ticker.fast_info['last_price']

@app.get("/")
def read_root():
    return {"current price": current_price}

