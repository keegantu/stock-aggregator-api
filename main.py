from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import os
import redis
import json
import httpx
import asyncio

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

load_dotenv()
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (for testing)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/stocks/{symbol}")
async def get_stock(symbol: str):
    cache_key = f"stock:{symbol}"
    
    # Check cache
    cached_data = r.get(cache_key)
    if cached_data:
        return json.loads(cached_data)
    
  #  overview_url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={ALPHA_VANTAGE_KEY}"
    global_quote_url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_KEY}"
    news_url = f"https://newsapi.org/v2/everything?q={symbol} stock&apiKey={NEWS_API_KEY}&pageSize=5&language=en"

    async with httpx.AsyncClient() as client:
    #    overview_response = await client.get(overview_url)
        global_quote_response = await client.get(global_quote_url)
        news_response = await client.get(news_url)
        
   # overview_data = overview_response.json()
    global_quote_data = global_quote_response.json()

    if "Global Quote" in global_quote_data and "05. price" in global_quote_data["Global Quote"]:
        news_data = news_response.json()

        print("Global Quote Response:", global_quote_data)
        
        news_list = []

        for article in news_data["articles"][:5]:
            news_list_article = {'title': article["title"], 'description': article["description"], 'url': article["url"], 'published_at': article["publishedAt"], 'source': article["source"]["name"]}
            news_list.append(news_list_article)

        result = {
            "symbol": symbol,
            "quote": {
                "price": global_quote_data["Global Quote"]["05. price"],
                "open": global_quote_data["Global Quote"]["02. open"],
                "high": global_quote_data["Global Quote"]["03. high"],
                "low": global_quote_data["Global Quote"]["04. low"],
                "volume": global_quote_data["Global Quote"]["06. volume"],
                "previous_close": global_quote_data["Global Quote"]["08. previous close"],
                "change": global_quote_data["Global Quote"]["09. change"],
                "change_percent": global_quote_data["Global Quote"]["10. change percent"]
            },

            "news": news_list,
            
        #  "overview": {
        #      "name": overview_data["Name"],
        #     "description": overview_data["Description"]
        #   }
        }
        
        # Store in cache (expires in 5 minutes = 300 seconds)
        r.setex(cache_key, 3000, json.dumps(result))
        return result
    else:
        
        return {"error": "Invalid stock symbol"}