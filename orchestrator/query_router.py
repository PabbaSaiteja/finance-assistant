import os
import pandas as pd
import yfinance as yf
import requests
from dotenv import load_dotenv
from rapidfuzz import process

# Load environment variables
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json"
}



csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "tickers.csv")
df = pd.read_csv(os.path.abspath(csv_path))
 
df = df.dropna(subset=["Name", "Ticker"])
stock_name_to_ticker = {
    name.lower(): ticker for name, ticker in zip(df["Name"], df["Ticker"])
    if isinstance(name, str) and isinstance(ticker, str)
}

# Predefined tickers
PREDEFINED_TICKERS = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "google": "GOOGL",
    "meta": "META",
    "tesla": "TSLA"
}


def fuzzy_match_ticker(query):
    query = query.lower()

    # 1. Predefined fast match
    match, score, _ = process.extractOne(query, PREDEFINED_TICKERS.keys())
    if score > 85:
        return PREDEFINED_TICKERS[match]

    # 2. CSV fallback
    match, score, _ = process.extractOne(query, stock_name_to_ticker.keys())
    if score > 70:
        ticker = stock_name_to_ticker[match]
        print(f"[DEBUG] Matched '{query}' → '{match}' → '{ticker}' (score: {score})")
        return ticker

    return None


def get_stock_info(ticker):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period='1d')
        if not data.empty:
            return {
                "ticker": ticker,
                "price": round(data['Close'].iloc[-1], 2),
                "previous_close": round(data['Close'].iloc[0], 2)
            }
    except Exception as e:
        print(f"[ERROR] Failed to fetch {ticker}: {e}")
    return None


def generate_llm_response(prompt):
    payload = {
        "model": "mistralai/devstral-small:free",
        "messages": [
            {"role": "system", "content": "You are a helpful financial assistant."},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        response = requests.post(OPENROUTER_API_URL, headers=HEADERS, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f" LLM Error: {e}"


def handle_market_brief_query(query: str) -> str:
    ticker = fuzzy_match_ticker(query)
    if not ticker:
        return " Could not find a relevant stock ticker from your query."

    stock_info = get_stock_info(ticker)
    if not stock_info:
        return f"Couldn't retrieve real-time stock data for `{ticker}`."

    prompt = (
    f"You are a professional financial assistant analyzing the stock '{ticker}'.\n\n"
    f"Here is the most recent real-time market data:\n"
    f"- Ticker Symbol: {ticker}\n"
    f"- Current Price: ${stock_info['price']}\n"
    f"- Previous Close Price: ${stock_info['previous_close']}\n\n"
    f"Using this data, provide a clear and insightful market brief covering the following points:\n"
    f"1. **Price Movement** — Describe how the price has changed since the previous close. Mention any noticeable short-term trend or volatility.\n"
    f"2. **Investor Sentiment** — Indicate if the sentiment appears bullish, bearish, or neutral, and explain why.\n"
    f"3. **Risk Assessment** — Highlight any potential short-term risks, macroeconomic pressures, or concerns investors should be aware of.\n"
    f"4. **Outlook** — Offer both short-term (1–2 weeks) and long-term (3–6 months) expectations, including key factors or events to watch.\n"
    f"5. **Investment Recommendation** — Based on the above, suggest whether a general investor should **Buy**, **Hold**, or **Sell** this stock right now. Justify your recommendation briefly, assuming a moderate risk tolerance.\n\n"
    f"Be specific, avoid financial jargon, and write in a professional yet beginner-friendly tone. Avoid generic or vague statements."
)


    response = generate_llm_response(prompt)
    return response.strip()[:280]
