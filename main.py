import os, json, time, requests

TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = 8340627885
API = f"https://api.telegram.org/bot{TOKEN}"
FILE = "channels.json"
KNOWN_FILE = "chats.json"
PRICE_URL = "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd"

MAIN_KB = {"keyboard": [[{"text": "🛠 پنل ادمین"}]], "resize_keyboard": True}
PANEL_KB = {"inline_keyboard": [
    [{"text": "📢 ارسال پیام به چنل‌ها", "callback_data": "send"}],
    [{"text": "🔐 دسترسی‌های ربات", "callback_data": "perms"}],
    [{"text": "⏱ تنظیم زمان ارسال", "callback_data": "timers"}],
    [{"text": "➕ اضافه کردن چنل", "callback_data": "add"}],
    [{"text": "➖ حذف چنل", "callback_data": "remove"}],
    [{"text": "📋 لیست چنل‌ها", "callback_data": "list"}],
]}

PERMS = [
    ("can_manage_chat", "مدیریت چت"),
    ("can_post_messages", "ارسال پیام"),
    ("can_edit_messages", "ویرایش پیام‌ها"),
    ("can_delete_messages", "حذف پیام‌ها"),
    ("can_invite_users", "دعوت کاربران و لینک"),
    ("can_change_info", "تغییر اطلاعات"),
    ("can_pin_messages", "پین کردن"),
    ("can_restrict_members", "بن کردن اعضا"),
    ("can_promote_members", "افزودن ادمین"),
    ("can_manage_video_chats", "مدیریت ویدیوچت"),
    ("can_manage_topics", "مدیریت تاپیک‌ها"),
    ("can_post_stories", "استوری"),
    ("is_anonymous", "ادمین ناشناس"),
]

STATUS_FA = {
    "creator": "👑 مالک",
    "administrator": "👮 ادمین",
    "member": "✅ عضو",
    "restricted": "⚠️ محدود شده",
    "left": "🚪 ترک کرده / عضو نیست",
    "kicked": "🚫 بن شده",
}

def tg(method, **data):
    try:
        return requests.post(f"{API}/{method}", json=data, timeout=40).json()
    except Exception as e:
        print("خطا:", e)
        return {"ok": False}

def load():
    try:
        with open(FILE) as f:
            d = json.load(f)
        if isinstance(d, list):
            return {c: 1.0 for c in d}
        return {k: float(v) for k, v in d.items()}
    except Exception:
        return {"@TONWHIR": 1.0}

def save(chs):
    with open(FILE, "w") as f:
        json.dump(chs, f)

def load_known():
    try:
        with open(KNOWN_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_known():
    with open(KNOWN_FILE, "w") as f:
        json.dump(known, f)

def say(chat, text, kb=None):
    d = {"chat_id": chat, "text": text}
    if kb:
        d["reply_markup"] = kb
    tg("sendMessage", **d)

def get_price():
    return requests.get(PRICE_URL, timeout=10).json()["the-open-network"]["usd"]

BOT_ID = tg("getMe")["result"]["id"]
channels = load()
known = load_known()
last_sent = {}
state = None
target_ch = None
target_cid = None
pending = None
offset = 0
next_try = 0
price_cache = (None, 0)

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
    channels[ch] = 1.0
    save(channels)
    state = None
    say(chat, f"✅ اضافه شد: {info['result'].get('title', ch)} (هر 1 دقیقه)", PANEL_KB)

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

def show_timers(chat):
    if not channels:
        say(chat, "چنلی اضافه نشده.", PANEL_KB)
        return
    rows = [[{"text": f"📍 {c} — هر {m:g} دقیقه", "callback_data": "tset:" + c}] for c, m in channels.items()]
    rows.append([{"text": "↩️ برگشت", "callback_data": "panel"}])
    say(chat, "زمان کدوم چنل رو تغییر بدم؟", {"inline_keyboard": rows})

def show_presets(chat, c):
    def b(m):
        return {"text": f"{m} دقیقه", "callback_data": f"tv:{m}:{c}"}
    rows = [
        [b(1), b(2), b(5)],
        [b(10), b(15), b(30)],
        [b(60), b(180)],
        [{"text": "✏️ عدد دلخواه", "callback_data": "tc:" + c}],
        [{"text": "↩️ برگشت", "callback_data": "timers"}],
    ]
    say(chat, f"هر چند دقیقه برای {c} قیمت بفرستم؟", {"inline_keyboard": rows})

def get_price_cached():
    global price_cache
    p, t = price_cache
    if p is None or time.time() - t > 20:
        p = get_price()
        price_cache = (p, time.time())
    return p

def known_list():
    items = dict(known)
    for c in channels:
        info = tg("getChat", chat_id=c)
        if info.get("ok"):
            items[str(info["result"]["id"])] = info["result"].get("title", c)
    return items

def show_perms_list(chat):
    items = known_list()
    if not items:
        say(chat, "هنوز جایی ثبت نشده که ربات توش ادمین باشه.", PANEL_KB)
        return
    rows = [[{"text": f"🔐 {t}", "callback_data": "cp:" + i}] for i, t in items.items()]
    rows.append([{"text": "↩️ برگشت", "callback_data": "panel"}])
    say(chat, "ربات تو کدوم چت؟", {"inline_keyboard": rows})

def show_chat(chat, cid):
    info = tg("getChat", chat_id=cid).get("result", {})
    title = info.get("title", str(cid))
    m = tg("getChatMember", chat_id=cid, user_id=BOT_ID).get("result", {})
    st = m.get("status")
    if st not in ("administrator", "creator"):
        say(chat, f"ربات تو «{title}» ادمین نیست.", PANEL_KB)
        return
    def can(k, default=False):
        return True if st == "creator" else bool(m.get(k, default))
    lines = [f"🔐 دسترسی‌های ربات تو «{title}»"]
    if st == "creator":
        lines.append("ربات مالک این چت است (همه دسترسی‌ها).")
    else:
        for k, n in PERMS:
            if k in m:
                lines.append(("✅ " if m[k] else "❌ ") + n)
    rows = []
    if can("can_post_messages", True):
        rows.append([{"text": "📝 ارسال پیام", "callback_data": f"tpost:{cid}"}])
    if can("can_delete_messages"):
        rows.append([{"text": "🗑 حذف پیام", "callback_data": f"tdel:{cid}"}])
    if can("can_pin_messages") or can("can_edit_messages"):
        rows.append([{"text": "📌 پین کردن پیام", "callback_data": f"tpin:{cid}"}])
    if can("can_invite_users"):
        rows.append([{"text": "🔗 ساخت لینک دعوت", "callback_data": f"tinv:{cid}"}])
    if can("can_change_info"):
        rows.append([{"text": "✏️ تغییر نام", "callback_data": f"ttit:{cid}"},
                     {"text": "📄 تغییر توضیحات", "callback_data": f"tdes:{cid}"}])
    rows.append([{"text": "👥 تعداد اعضا", "callback_data": f"tcount:{cid}"},
                 {"text": "👮 ادمین‌ها", "callback_data": f"tadm:{cid}"}])
    rows.append([{"text": "🔎 چک کاربر", "callback_data": f"tchk:{cid}"}])
    if can("can_restrict_members"):
        rows.append([{"text": "🚫 بن", "callback_data": f"tban:{cid}"},
                     {"text": "✅ آنبن", "callback_data": f"tunban:{cid}"},
                     {"text": "👢 کیک", "callback_data": f"tkick:{cid}"}])
    rows.append([{"text": "↩️ برگشت", "callback_data": "perms"}])
    say(chat, "\n".join(lines), {"inline_keyboard": rows})

def show_admins(chat, cid):
    r = tg("getChatAdministrators", chat_id=cid)
    if not r.get("ok"):
        say(chat, "⚠️ نشد: " + str(r.get("description", "")), PANEL_KB)
        return
    lines = ["👮 ادمین‌ها:"]
    for a in r["result"][:50]:
        u = a["user"]
        name = u.get("first_name", "")
        un = f" @{u['username']}" if u.get("username") else ""
        crown = "👑 " if a["status"] == "creator" else ""
        bot = " 🤖" if u.get("is_bot") else ""
        lines.append(f"{crown}{name}{un}{bot} — {u['id']}")
    say(chat, "\n".join(lines), PANEL_KB)

def do_action(chat, kind, text, msg):
    global state
    cid = target_cid
    if kind == "cpost":
        r = tg("copyMessage", chat_id=cid, from_chat_id=chat, message_id=msg["message_id"])
    elif kind in ("cdel", "cpin"):
        try:
            mid = int(text.rstrip("/").split("/")[-1])
        except ValueError:
            say(chat, "آیدی عددی پیام یا لینکش رو بفرست (یا «لغو»).")
            return
        r = tg("deleteMessage" if kind == "cdel" else "pinChatMessage", chat_id=cid, message_id=mid)
    elif kind == "ctit":
        r = tg("setChatTitle", chat_id=cid, title=text)
    elif kind == "cdes":
        r = tg("setChatDescription", chat_id=cid, description=text)
    else:
        t = text.strip()
        if not t.isdigit():
            say(chat, "آیدی عددی کاربر رو بفرست (یا «لغو»). یوزرنیم جواب نمی‌ده.")
            return
        uid = int(t)
        if uid in (OWNER_ID, BOT_ID):
            state = None
            say(chat, "این کار روی این کاربر مجاز نیست.", PANEL_KB)
            return
        if kind == "ccheck":
            r = tg("getChatMember", chat_id=cid, user_id=uid)
            state = None
            if r.get("ok"):
                m = r["result"]
                u = m["user"]
                un = f" @{u['username']}" if u.get("username") else ""
                say(chat, f"🔎 {u.get('first_name', '')}{un}\nآیدی: {u['id']}\nوضعیت: {STATUS_FA.get(m['status'], m['status'])}", PANEL_KB)
            else:
                say(chat, "⚠️ نشد: " + str(r.get("description", "")), PANEL_KB)
            return
        elif kind == "cban":
            r = tg("banChatMember", chat_id=cid, user_id=uid)
        elif kind == "cunban":
            r = tg("unbanChatMember", chat_id=cid, user_id=uid, only_if_banned=True)
        else:
            r = tg("banChatMember", chat_id=cid, user_id=uid)
            if r.get("ok"):
                r = tg("unbanChatMember", chat_id=cid, user_id=uid, only_if_banned=True)
    state = None
    say(chat, "✅ انجام شد." if r.get("ok") else "⚠️ نشد: " + str(r.get("description", "")), PANEL_KB)

def handle_my_chat_member(m):
    chat = m["chat"]
    if chat["type"] == "private":
        return
    st = m["new_chat_member"]["status"]
    key = str(chat["id"])
    title = chat.get("title", key)
    if st == "administrator":
        was = key in known
        known[key] = title
        save_known()
        txt = f"🔄 دسترسی‌های ربات تو «{title}» تغییر کرد." if was else f"🔔 ربات تو «{title}» ادمین شد."
        say(OWNER_ID, txt, {"inline_keyboard": [[{"text": "🔐 مشاهده دسترسی‌ها", "callback_data": "cp:" + key}]]})
    elif key in known:
        del known[key]
        save_known()
        say(OWNER_ID, f"⚠️ ربات دیگه تو «{title}» ادمین نیست.")

ACTIONS = ("cpost", "cdel", "cpin", "ctit", "cdes", "ccheck", "cban", "cunban", "ckick")

def ask_user(chat, what):
    say(chat, f"آیدی عددی کاربر رو بفرست تا {what} بشه.\nبرای انصراف بنویس: لغو")

while True:
    r = tg("getUpdates", offset=offset, timeout=5,
           allowed_updates=["message", "callback_query", "my_chat_member"])
    if not r.get("ok"):
        time.sleep(2)
    for u in r.get("result", []):
        offset = u["update_id"] + 1
        if "my_chat_member" in u:
            handle_my_chat_member(u["my_chat_member"])
            continue
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
            elif state in ACTIONS:
                do_action(chat, state, text, msg)
            elif state == "interval":
                try:
                    v = float(text.replace(",", "."))
                except ValueError:
                    say(chat, "فقط عدد بفرست، مثلاً 5 یا 0.5 (یا «لغو»).")
                    continue
                if v < 0.5 or v > 1440:
                    say(chat, "عدد باید بین 0.5 تا 1440 دقیقه باشه.")
                    continue
                if target_ch in channels:
                    channels[target_ch] = v
                    save(channels)
                state = None
                say(chat, f"✅ {target_ch}: هر {v:g} دقیقه", PANEL_KB)
        else:
            chat, data = cb["message"]["chat"]["id"], cb["data"]
            tg("answerCallbackQuery", callback_query_id=cb["id"])
            if data == "panel":
                say(chat, "پنل ادمین:", PANEL_KB)
            elif data == "add":
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
            elif data == "perms":
                show_perms_list(chat)
            elif data.startswith("cp:"):
                show_chat(chat, data[3:])
            elif data.startswith("tpost:"):
                target_cid = data[6:]
                state = "cpost"
                say(chat, "پیامت رو بفرست تا تو اون چت منتشر بشه.\nبرای انصراف بنویس: لغو")
            elif data.startswith("tdel:"):
                target_cid = data[5:]
                state = "cdel"
                say(chat, "آیدی عددی پیام یا لینکش رو بفرست تا حذف بشه.\nبرای انصراف بنویس: لغو")
            elif data.startswith("tpin:"):
                target_cid = data[5:]
                state = "cpin"
                say(chat, "آیدی عددی پیام یا لینکش رو بفرست تا پین بشه.\nبرای انصراف بنویس: لغو")
            elif data.startswith("tinv:"):
                res = tg("createChatInviteLink", chat_id=data[5:])
                if res.get("ok"):
                    say(chat, "🔗 " + res["result"]["invite_link"], PANEL_KB)
                else:
                    say(chat, "⚠️ نشد: " + str(res.get("description", "")), PANEL_KB)
            elif data.startswith("ttit:"):
                target_cid = data[5:]
                state = "ctit"
                say(chat, "اسم جدید رو بفرست.\nبرای انصراف بنویس: لغو")
            elif data.startswith("tdes:"):
                target_cid = data[5:]
                state = "cdes"
                say(chat, "توضیحات جدید رو بفرست.\nبرای انصراف بنویس: لغو")
            elif data.startswith("tcount:"):
                res = tg("getChatMemberCount", chat_id=data[7:])
                if res.get("ok"):
                    say(chat, f"👥 تعداد اعضا: {res['result']}", PANEL_KB)
                else:
                    say(chat, "⚠️ نشد: " + str(res.get("description", "")), PANEL_KB)
            elif data.startswith("tadm:"):
                show_admins(chat, data[5:])
            elif data.startswith("tchk:"):
                target_cid = data[5:]
                state = "ccheck"
                ask_user(chat, "چک")
            elif data.startswith("tban:"):
                target_cid = data[5:]
                state = "cban"
                ask_user(chat, "بن")
            elif data.startswith("tunban:"):
                target_cid = data[7:]
                state = "cunban"
                ask_user(chat, "آنبن")
            elif data.startswith("tkick:"):
                target_cid = data[6:]
                state = "ckick"
                ask_user(chat, "کیک")
            elif data == "timers":
                show_timers(chat)
            elif data.startswith("tset:"):
                show_presets(chat, data[5:])
            elif data.startswith("tv:"):
                _, m, c = data.split(":", 2)
                if c in channels:
                    channels[c] = float(m)
                    save(channels)
                say(chat, f"✅ {c}: هر {float(m):g} دقیقه", PANEL_KB)
            elif data.startswith("tc:"):
                target_ch = data[3:]
                state = "interval"
                say(chat, "هر چند دقیقه؟ یه عدد بفرست (مثلاً 5 یا 0.5 برای ۳۰ ثانیه).\nبرای انصراف بنویس: لغو")
            elif data == "list":
                lines = [f"{c} — هر {m:g} دقیقه" for c, m in channels.items()]
                say(chat, "چنل‌های فعال:\n" + ("\n".join(lines) or "هیچی"), PANEL_KB)
            elif data == "remove":
                if not channels:
                    say(chat, "چنلی نیست.", PANEL_KB)
                else:
                    kb = {"inline_keyboard": [[{"text": f"❌ {c}", "callback_data": "del:" + c}] for c in channels]}
                    say(chat, "کدوم رو حذف کنم؟", kb)
            elif data.startswith("del:"):
                c = data[4:]
                if c in channels:
                    del channels[c]
                    last_sent.pop(c, None)
                    save(channels)
                say(chat, f"🗑 حذف شد: {c}", PANEL_KB)
    now = time.time()
    due = [c for c, m in channels.items() if now - last_sent.get(c, 0) >= m * 60]
    if due and now >= next_try:
        try:
            text = f"${get_price_cached()}"
            for c in due:
                last_sent[c] = now
                res = tg("sendMessage", chat_id=c, text=text)
                if not res.get("ok"):
                    print(c, res)
        except Exception as e:
            print("خطا:", e)
            next_try = now + 15
