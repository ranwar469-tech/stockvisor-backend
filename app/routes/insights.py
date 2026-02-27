"""Insights routes — placeholder endpoints for future insights APIs."""

from typing import List

from fastapi import APIRouter
import yfinance as yf
from huggingface_hub import InferenceClient
from app.core.config import settings
from app.schemas.insights import SentimentItem

router = APIRouter(prefix="/insights", tags=["insights"])

client = InferenceClient(
    provider="hf-inference",
    api_key=settings.HF_TOKEN,
)

#  result = client.text_classification(
#     "I like you. I love you",
#     model="mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis",
# )

#result output= [[{"label":"positive","score":0.8930202722549438},{"label":"neutral","score":0.08915447443723679},{"label":"negative","score":0.017825251445174217}]]

@router.get("/technology", response_model=List[SentimentItem])
def get_technology_insight():
    tech=yf.Tickers("AAPL MSFT GOOG").news()
    technews=""
    for i in range(3):
        technews += "\n\nAAPL news "+str(i+1)+": "+tech['AAPL'][i]['content']['summary']
    result = client.text_classification(
        technews,
        model="mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis",
    )

    return result


@router.get("/energy", response_model=List[SentimentItem])
def get_energy_insight():
    energy=yf.Tickers("XOM CVX COP").news()
    energynews=""
    for i in range(3):
        energynews += "\n\nXOM news "+str(i+1)+": "+energy['XOM'][i]['content']['summary']
    result = client.text_classification(
        energynews,
        model="mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis",
    )
    return result


@router.get("/healthcare", response_model=List[SentimentItem])
def get_healthcare_insight():
    healthcare=yf.Tickers("JNJ MRN").news()
    healthcarenews=""
    for i in range(3):
        healthcarenews += "\n\nJNJ news "+str(i+1)+": "+healthcare['JNJ'][i]['content']['summary']
    result = client.text_classification(
        healthcarenews,
        model="mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis",
    )
    return result


@router.get("/financial", response_model=List[SentimentItem])
def get_financial_insight():
    financial=yf.Tickers("JPM BAC GS").news()
    fianncialnews=""
    for i in range(3):
        fianncialnews += "\n\nJPM news "+str(i+1)+": "+financial['JPM'][i]['content']['summary']
    result = client.text_classification(
        fianncialnews,
        model="mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis",
    )
    return result
