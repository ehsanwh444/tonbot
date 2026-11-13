import os, json, time, requests

TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = 8340627885
API = f"https://api.telegram.org/bot{TOKEN}"
FILE = "channels.json"
PRICE_URL = "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd"
INTERVAL = 60

MAIN_KB = {"keyboard": [[{"text": "🛠 پنل ادمین"}]], "resize_keyboard": True}
PANEL_KB = {"inline_keyboard": [
    [{"text": "📢 ارسال پیام به چنل‌ها", "callback_data": "send"}],
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
state = None
pending = None
offset = 0
last = 0

def add_channel(chat, ch):
    global state
    if ch in channels:
        state = None
        say(chat, "این چنل قبلاً اضافه شده.", PANEL_KB)
        return
    info = tg("getChat", chat_id=ch)
    if not info.get("ok"):
        say(chat, "چنل پیدا نشد. آیدی رو درست بفرست (مثل @mychannel) یا «لغو» بزن.")
        return
    m = tg("getChatMember", chat_id=ch, user_id=BOT_ID)
    if m.get("result", {}).get("status") not in ("administrator", "creator"):
        say(chat, "ربات تو این چنل ادمین نیست. اول ادمینش کن و دوباره آیدی رو بفرست.")
        return
    channels.append(ch)
    save(channels)
    state = None
    say(chat, f"✅ اضافه شد: {info['result'].get('title', ch)}", PANEL_KB)

def ask_target(chat):
    if not channels:
        say(chat, "چنلی اضافه نشده.", PANEL_KB)
        return
    rows = [[{"text": "📢 همه چنل‌ها", "callback_data": "sendall"}]]
    rows += [[{"text": f"📍 {c}", "callback_data": "sendto:" + c}] for c in channels]
    rows.append([{"text": "❌ لغو", "callback_data": "cancel"}])
    say(chat, "به کدوم چنل بفرستم؟", {"inline_keyboard": rows})

def deliver(chat, targets):
    global pending
    if not pending:
        say(chat, "پیامی برای ارسال نیست.", PANEL_KB)
        return
    ok = 0
    bad = []
    for c in targets:
        r = tg("copyMessage", chat_id=c, from_chat_id=pending[0], message_id=pending[1])
        if r.get("ok"):
            ok += 1
        else:
            bad.append(c)
    pending = None
    text = f"✅ ارسال شد به {ok} چنل."
    if bad:
        text += "\n⚠️ ناموفق: " + ", ".join(bad)
    say(chat, text, PANEL_KB)

while True:
    r = tg("getUpdates", offset=offset, timeout=5)
    if not r.get("ok"):
        time.sleep(2)
    for u in r.get("result", []):
        offset = u["update_id"] + 1
        msg, cb = u.get("message"), u.get("callback_query")
        src = msg or cb
        if not src or src["from"]["id"] != OWNER_ID:
            continue
        if msg:
            if msg["chat"]["type"] != "private":
                continue
            chat, text = msg["chat"]["id"], msg.get("text", "").strip()
            if text == "لغو":
                state = None
                pending = None
                say(chat, "لغو شد.", PANEL_KB)
            elif text == "/start":
                say(chat, "سلام! برای مدیریت چنل‌ها دکمه پایین رو بزن.", MAIN_KB)
            elif text == "🛠 پنل ادمین":
                state = None
                say(chat, "پنل ادمین:", PANEL_KB)
            elif state == "add":
                add_channel(chat, text)
            elif state == "send":
                pending = (chat, msg["message_id"])
                state = None
                ask_target(chat)
        else:
            chat, data = cb["message"]["chat"]["id"], cb["data"]
            tg("answerCallbackQuery", callback_query_id=cb["id"])
            if data == "add":
                state = "add"
                say(chat, "آیدی چنل رو بفرست (مثل @mychannel).\nبرای انصراف بنویس: لغو")
            elif data == "send":
                state = "send"
                say(chat, "پیامت رو بفرست (متن، عکس، ویدیو، هر چی).\nبرای انصراف بنویس: لغو")
            elif data == "sendall":
                deliver(chat, list(channels))
            elif data.startswith("sendto:"):
                deliver(chat, [data[7:]])
            elif data == "cancel":
                state = None
                pending = None
                say(chat, "لغو شد.", PANEL_KB)
            elif data == "list":
                say(chat, "چنل‌های فعال:\n" + ("\n".join(channels) or "هیچی"), PANEL_KB)
            elif data == "remove":
                if not channels:
                    say(chat, "چنلی نیست.", PANEL_KB)
                else:
                    kb = {"inline_keyboard": [[{"text": f"❌ {c}", "callback_data": "del:" + c}] for c in channels]}
                    say(chat, "کدوم رو حذف کنم؟", kb)
            elif data.startswith("del:"):
                c = data[4:]
                if c in channels:
                    channels.remove(c)
                    save(channels)
                say(chat, f"🗑 حذف شد: {c}", PANEL_KB)
    if time.time() - last >= INTERVAL:
        last = time.time()
        try:
            text = f"${get_price()}"
            for c in channels:
                res = tg("sendMessage", chat_id=c, text=text)
                if not res.get("ok"):
                    print(c, res)
        except Exception as e:
            print("خطا:", e)
