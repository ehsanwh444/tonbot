import os, requests, time

TOKEN = os.environ["9179606432:AAH9xq4mpPr62ns1dMQlFGZhQUJa0n3bnhk"]
CHANNEL = "@TONWHIR"

PRICE_URL = ("https://api.coingecko.com/api/v3/simple/price"
             "?ids=the-open-network&vs_currencies=usd")
API = f"https://api.telegram.org/bot{TOKEN}"

def get_price():
    data = requests.get(PRICE_URL, timeout=10).json()
    return data["the-open-network"]["usd"]

while True:
    try:
        requests.post(f"{API}/sendMessage",
                      data={"chat_id": CHANNEL, "text": f"${get_price()}"})
    except Exception as e:
        print("خطا:", e)
    time.sleep(30)
