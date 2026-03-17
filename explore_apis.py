import requests
import json

# Your API keys
ALPHA_VANTAGE_KEY = "BH8OHBEEATYU0WL0"
NEWS_API_KEY = "35df905de2c949f89907e8308e976eb5"


name_url = "https://www.alphavantage.co/query?function=OVERVIEW&symbol=AAPL&apikey=BH8OHBEEATYU0WL0"
response = requests.get(name_url)
print(json.dumps(response.json(), indent=2))