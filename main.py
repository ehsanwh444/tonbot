import os, json, time, requests

TOKEN = os.environ["9179606432:AAH9xq4mpPr62ns1dMQlFGZhQUJa0n3bnhk"]
OWNER_ID = 8340627885
API = f"https://api.telegram.org/bot{TOKEN}"
FILE = "channels.json"
PRICE_URL = ("https://api.coingecko.com/api/v3/simple/price"
PANEL_KB = {"inline_keyboard": [
    [{"text": "➕ اضافه کردن چنل", "callback_data": "add"}],
    [{"text": "➖ حذف چنل", "callback_data": "remove"}],
    [{"text": "📋 لیست چنل‌ها", "callback_data": "list"}],
]}

def tg(method, **data):
    try:
        return requests.post(f"{API}/{method}", json=data, timeout=40).json()
    except Exception as e:
        print("خطا:", e)
        return {"ok": False}

def load():
    try:
        with open(FILE) as f:
            return json.load(f)
    except Exception:
        return ["@TONWHIR"]

def save(chs):
    with open(FILE, "w") as f:
        json.dump(chs, f)

def say(chat, text, kb=None):
    d = {"chat_id": chat, "text": text}
    if kb:
        d["reply_markup"] = kb
    tg("sendMessage", **d)

def get_price():
    return requests.get(PRICE_URL, timeout=10).json()["the-open-network"]["usd"]

BOT_ID = tg("getMe")["result"]["id"]
channels = load()
waiting = False
offset = 0

def add_channel(chat, ch):
    global waiting
    if ch in channels:
        waiting = False
        say(chat, "این چنل قبلاً اضافه شده.", PANEL_KB)
        return
    info = tg("getChat", chat_id=ch)
    if not info.get("ok"):
        say(chat, "چنل پیدا نشد. آیدی رو درست بفرست (مثل @mychannel) یا «لغو» بزن.")
        return
    m = tg("getChatMember", chat_id=ch, user_id=BOT_ID)
    if m.get("result", {}).get("status") not in ("administrator", "creator"):
        say(chat, "ربات تو این چنل ادمین نیست. اول ادمینش کن و دوباره آیدی رو بفرست.")
    save(channels)
    say(chat, f"✅ اضافه شد: {info['result'].get('title', ch)}", PANEL_KB)
while True:
    r = tg("getUpdates", offset=offset, timeout=5)
        time.sleep(2)
    for u in r.get("result", []):
        offset = u["update_id"] + 1
        msg, cb = u.get("message"), u.get("callback_query")
        if not src or src["from"]["id"] != OWNER_ID:
            chat, text = msg["chat"]["id"], msg.get("text", "").strip()
            if text == "لغو":
                waiting = False
            elif waiting:
        else:
                if not channels:
                    kb = {"inline_keyboard": [[{"text": f"❌ {c}", "callback_data": "del:" + c}] for c in channels]}
                c = data[4:]
                    save(channels)
                say(chat, f"🗑 حذف شد: {c}", PANEL_KB)
    if time.time() - last >= 30:
                res = tg("sendMessage", chat_id=c, text=text)
                if not res.get("ok"):
        except Exception as e:
            print("خطا:", e)
