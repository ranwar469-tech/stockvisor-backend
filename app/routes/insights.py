"""Insights routes — placeholder endpoints for future insights APIs."""

from typing import List
import random

from fastapi import APIRouter
import yfinance as yf
from huggingface_hub import InferenceClient
from app.core.config import settings
from app.schemas.insights import AlertResponse, SentimentItem

router = APIRouter(prefix="/insights", tags=["insights"])

client = InferenceClient(
    provider="hf-inference",
    api_key=settings.HF_TOKEN,
)


def _summary_to_text(summary_output) -> str:
    summary_text = getattr(summary_output, "summary_text", None)
    if isinstance(summary_text, str):
        return summary_text

    if isinstance(summary_output, dict):
        dict_summary = summary_output.get("summary_text")
        if isinstance(dict_summary, str):
            return dict_summary

    return str(summary_output)

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


@router.get("/alerts/", response_model=AlertResponse)
def get_insight_alerts():
    ticker=yf.Ticker("AAPL")
    news = ticker.get_news(10, "news")
    newsarr=random.sample(range(10), 4)

    result1 = client.summarization(
    news[newsarr[0]]['content']['summary'],
    model="human-centered-summarization/financial-summarization-pegasus",
)
    result2 = client.summarization(
    news[newsarr[1]]['content']['summary'],
    model="human-centered-summarization/financial-summarization-pegasus",
)
    result3 = client.summarization(
    news[newsarr[2]]['content']['summary'],
    model="human-centered-summarization/financial-summarization-pegasus",
)
    result4= client.summarization(
    news[newsarr[3]]['content']['summary'],
    model="human-centered-summarization/financial-summarization-pegasus",)
    return AlertResponse(
        ai_alert_1=_summary_to_text(result1),
        ai_alert_2=_summary_to_text(result2),
        ai_alert_3=_summary_to_text(result3),
        ai_alert_4=_summary_to_text(result4),
    )
