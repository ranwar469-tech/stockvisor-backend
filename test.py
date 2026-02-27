import yfinance as yf

tech=yf.Tickers("AAPL MSFT GOOG").news()
energy=yf.Tickers("XOM CVX COP").news()
healthcare=yf.Tickers("JNJ UNH PFE").news()
fianncial=yf.Tickers("JPM BAC GS").news()

technews=""
energynews=""
healthcarenews=""
fianncialnews=""

for i in range(3):
    technews += "\n\nAAPL news "+str(i+1)+": "+tech['AAPL'][i]['content']['summary']

for i in range(3):
    energynews += "\n\nXOM news "+str(i+1)+": "+energy['XOM'][i]['content']['summary']

for i in range(3):
    healthcarenews += "\n\nJNJ news "+str(i+1)+": "+healthcare['JNJ'][i]['content']['summary']

for i in range(3):
    fianncialnews += "\n\nJPM news "+str(i+1)+": "+fianncial['JPM'][i]['content']['summary']



print(technews)

