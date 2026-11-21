import os, io, re, json, time, requests
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = 8340627885
API = f"https://api.telegram.org/bot{TOKEN}"
FILE = "channels.json"
KNOWN_FILE = "chats.json"
BTN_FILE = "buttons.json"
CHART_FILE = "charts.json"
STATS_FILE = "stats.json"
TZ_OFFSET = 3.5
PRICE_URL = "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd"
HIST_URL = "https://api.coingecko.com/api/v3/coins/the-open-network/market_chart?vs_currency=usd&days=1"
MAIN_KB = {"keyboard": [[{"text": "🛠 پنل ادمین"}]], "resize_keyboard": True}
PANEL_KB = {"inline_keyboard": [
    [{"text": "📢 ارسال پیام به چنل‌ها", "callback_data": "send"}],
    [{"text": "🔘 دکمه زیر پیام", "callback_data": "btns"}],
    [{"text": "📈 نمودار قیمت", "callback_data": "charts"}],
    [{"text": "📊 گزارش رشد", "callback_data": "growth"}],
    [{"text": "💾 بکاپ و بازیابی", "callback_data": "bkp"}],
    [{"text": "🔐 دسترسی‌های ربات", "callback_data": "perms"}],
    [{"text": "⏱ تنظیم زمان ارسال", "callback_data": "timers"}],
    [{"text": "➕ اضافه کردن چنل", "callback_data": "add"}],
    [{"text": "➖ حذف چنل", "callback_data": "remove"}],
    [{"text": "📋 لیست چنل‌ها", "callback_data": "list"}],
]}
PUBLIC_HELLO = "سلام! 👋\nمقدار رو بفرست تا تبدیل کنم:\n• 100 TON\n• 50 دلار\n• 5000000 تومان"
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
FIRST_RUN = not os.path.exists(FILE)
dirty = False
last_backup = 0
alerts = {}
pending_restore = None

def tg(method, **data):
    try:
        return requests.post(f"{API}/{method}", json=data, timeout=40).json()
    except Exception as e:
        print("خطا:", e)
        return {"ok": False}

def say(chat, text, kb=None):
    d = {"chat_id": chat, "text": text}
    if kb:
        d["reply_markup"] = kb
    tg("sendMessage", **d)

def say_reply(chat, text, reply_to=None):
    if reply_to:
        tg("sendMessage", chat_id=chat, text=text, reply_to_message_id=reply_to,
           allow_sending_without_reply=True)
    else:
        say(chat, text)

def alert(kind, text, cooldown=1800):
    now = time.time()
    if now - alerts.get(kind, 0) >= cooldown:
        alerts[kind] = now
        say(OWNER_ID, text)

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
    global dirty
    with open(FILE, "w") as f:
        json.dump(chs, f)
    dirty = True

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}

def save_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f)

def save_known():
    global dirty
    save_json(KNOWN_FILE, known)
    dirty = True

def save_buttons():
    global dirty
    save_json(BTN_FILE, buttons)
    dirty = True

def save_charts():
    global dirty
    save_json(CHART_FILE, charts)
    dirty = True

def save_stats():
    save_json(STATS_FILE, stats)

def get_price():
    return requests.get(PRICE_URL, timeout=10).json()["the-open-network"]["usd"]

def rate_nobitex():
    r = requests.post("https://api.nobitex.ir/market/stats",
                      json={"srcCurrency": "usdt", "dstCurrency": "rls"}, timeout=10).json()
    latest = next(iter(r["stats"].values()))["latest"]
    return float(latest) / 10

def rate_wallex():
    r = requests.get("https://api.wallex.ir/v1/markets", timeout=10).json()
    return float(r["result"]["symbols"]["USDTTMN"]["stats"]["lastPrice"])

def get_rate():
    for fn in (rate_nobitex, rate_wallex):
        try:
            v = fn()
            if v > 1000:
                return v
        except Exception as e:
            print("نرخ تتر:", fn.__name__, e)
    return None

BOT_ID = tg("getMe")["result"]["id"]
channels = load()
known = load_json(KNOWN_FILE)
buttons = load_json(BTN_FILE)
charts = load_json(CHART_FILE)
stats = load_json(STATS_FILE)
stats.setdefault("_last_report", time.time())
last_sent = {}
last_price = {}
last_dot = {}
last_chart = {}
last_calc = {}
bot_admin_cache = {}
state = None
target_ch = None
target_cid = None
target_btn = None
pending = None
offset = 0
next_try = 0
price_cache = (None, 0)
rate_cache = (None, 0)
hist_cache = (None, 0)

def get_price_cached():
    global price_cache
    p, t = price_cache
    if p is None or time.time() - t > 20:
        p = get_price()
        price_cache = (p, time.time())
    return p

def get_rate_cached():
    global rate_cache
    v, t = rate_cache
    if time.time() - t > 60:
        new = get_rate()
        if new is None:
            alert("rate", "⚠️ نرخ تتر (تومان) از نوبیتکس و والکس نیومد. تا وقتی درست بشه، اگه نرخ قبلی هست ازش استفاده می‌شه، وگرنه فقط قیمت دلار ارسال می‌شه.", 3600)
        v = new or v
        rate_cache = (v, time.time())
    return v

def get_history_cached():
    global hist_cache
    h, t = hist_cache
    if h is None or time.time() - t > 300:
        h = requests.get(HIST_URL, timeout=20).json()["prices"]
        hist_cache = (h, time.time())
    return h

def fnt(n):
    try:
        return ImageFont.load_default(size=n)
    except Exception:
        return ImageFont.load_default()

def make_chart(prices):
    pts = [(p[0] / 1000.0, float(p[1])) for p in prices]
    if len(pts) < 2:
        raise ValueError("داده‌ی نمودار کمه")
    W, H = 1000, 560
    L, R, T, B = 120, 50, 120, 70
    img = Image.new("RGB", (W, H), (10, 16, 36))
    d = ImageDraw.Draw(img)
    f_title, f_sub, f_lab = fnt(40), fnt(26), fnt(22)
    vals = [p for _, p in pts]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.12 or hi * 0.002
    ymin, ymax = lo - pad, hi + pad
    t0, t1 = pts[0][0], pts[-1][0]
    def X(t):
        return L + (t - t0) / (t1 - t0) * (W - L - R)
    def Y(v):
        return T + (ymax - v) / (ymax - ymin) * (H - T - B)
    for i in range(5):
        v = ymin + (ymax - ymin) * i / 4
        y = Y(v)
        d.line([(L, y), (W - R, y)], fill=(30, 42, 76), width=2)
        s = f"{v:.4f}"
        d.text((L - 12 - d.textlength(s, font=f_lab), y - 11), s, font=f_lab, fill=(130, 150, 190))
    for i in range(5):
        t = t0 + (t1 - t0) * i / 4
        s = time.strftime("%H:%M", time.gmtime(t + TZ_OFFSET * 3600))
        w = d.textlength(s, font=f_lab)
        x = min(max(X(t) - w / 2, L - 10), W - R - w + 10)
        d.text((x, H - B + 18), s, font=f_lab, fill=(130, 150, 190))
    line = [(X(t), Y(v)) for t, v in pts]
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(ov).polygon([(line[0][0], H - B)] + line + [(line[-1][0], H - B)], fill=(40, 140, 255, 70))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(img)
    d.line(line, fill=(100, 210, 255), width=4, joint="curve")
    for target, color in ((hi, (80, 220, 140)), (lo, (255, 100, 100))):
        x, y = line[vals.index(target)]
        d.ellipse((x - 8, y - 8, x + 8, y + 8), fill=color, outline=(255, 255, 255), width=2)
    x, y = line[-1]
    d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=(255, 255, 255))
    chg = (vals[-1] - vals[0]) / vals[0] * 100
    d.text((L, 28), "TON / USD", font=f_title, fill=(255, 255, 255))
    d.text((L, 78), "last 24 hours", font=f_sub, fill=(130, 150, 190))
    cs = f"{chg:+.2f}%"
    col = (80, 220, 140) if chg >= 0 else (255, 100, 100)
    d.text((W - R - d.textlength(cs, font=f_title), 28), cs, font=f_title, fill=col)
    ps = f"{vals[-1]:.4f}$"
    d.text((W - R - d.textlength(ps, font=f_sub), 78), ps, font=f_sub, fill=(200, 220, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue(), hi, lo, chg

def btn_markup(c):
    b = buttons.get(c)
    if b and b.get("text") and b.get("url"):
        return {"inline_keyboard": [[{"text": b["text"], "url": b["url"]}]]}
    return None

def post_chart(c):
    if Image is None:
        alert("pil", "⚠️ کتابخانه‌ی pillow نصب نیست. تو فایل requirements.txt یه خط جدید با کلمه‌ی pillow اضافه کن.", 86400)
        return False
    try:
        png, hi, lo, chg = make_chart(get_history_cached())
    except Exception as e:
        alert("chart", f"⚠️ ساخت نمودار نشد: {e}", 1800)
        return False
    cap = f"📈 نمودار ۲۴ ساعته TON\n🔼 بالاترین: {hi:.4f}$\n🔽 پایین‌ترین: {lo:.4f}$\n📊 تغییر: {chg:+.2f}%"
    data = {"chat_id": c, "caption": cap}
    kb = btn_markup(c)
    if kb:
        data["reply_markup"] = json.dumps(kb)
    try:
        r = requests.post(f"{API}/sendPhoto", data=data, files={"photo": ("chart.png", png)}, timeout=60).json()
    except Exception as e:
        alert("chartsend:" + c, f"⚠️ ارسال نمودار به {c} نشد: {e}", 1800)
        return False
    if not r.get("ok"):
        alert("chartsend:" + c, f"⚠️ ارسال نمودار به {c} نشد: {r.get('description', '')}", 1800)
        return False
    return True

def show_chart_list(chat):
    if not channels:
        say(chat, "چنلی اضافه نشده.", PANEL_KB)
        return
    rows = []
    for c in channels:
        h = charts.get(c)
        label = f"هر {h:g} ساعت" if h else "خاموش"
        rows.append([{"text": f"📍 {c} — {label}", "callback_data": "cset:" + c}])
    rows.append([{"text": "↩️ برگشت", "callback_data": "panel"}])
    say(chat, "نمودار کدوم چنل؟", {"inline_keyboard": rows})

def show_chart_menu(chat, c):
    def b(h):
        return {"text": f"هر {h} ساعت", "callback_data": f"cv:{h}:{c}"}
    rows = [
        [b(3), b(6)],
        [b(12), b(24)],
        [{"text": "⛔ خاموش", "callback_data": f"cv:0:{c}"}],
        [{"text": "📤 ارسال الان", "callback_data": "cnow:" + c}],
        [{"text": "↩️ برگشت", "callback_data": "charts"}],
    ]
    say(chat, f"هر چند ساعت نمودار برای {c} فرستاده بشه؟", {"inline_keyboard": rows})

def record_stats():
    today = time.strftime("%Y-%m-%d", time.gmtime(time.time() + TZ_OFFSET * 3600))
    if stats.get("_last_day") == today:
        return
    for c in list(channels):
        r = tg("getChatMemberCount", chat_id=c)
        if r.get("ok"):
            days = stats.setdefault(c, {})
            days[today] = r["result"]
            for old in sorted(days)[:-120]:
                del days[old]
    stats["_last_day"] = today
    save_stats()

def growth_text():
    parts = []
    for c in channels:
        days = sorted(stats.get(c, {}).items())
        if not days:
            parts.append(f"📍 {c}\nهنوز داده‌ای ثبت نشده (از فردا ثبت می‌شه).")
            continue
        cur = days[-1][1]
        if len(days) < 2:
            parts.append(f"📍 {c}\n👥 الان: {cur:,}\n(برای مقایسه حداقل ۲ روز داده لازمه)")
            continue
        win = days[-8:]
        diffs = [(win[i][0], win[i][1] - win[i - 1][1]) for i in range(1, len(win))]
        best = max(diffs, key=lambda x: x[1])
        worst = min(diffs, key=lambda x: x[1])
        total = win[-1][1] - win[0][1]
        avg = total / len(diffs)
        parts.append(f"📍 {c}\n👥 الان: {cur:,}\n📈 تغییر {len(diffs)} روز اخیر: {total:+,}\n🏆 بهترین روز: {best[0]} ({best[1]:+,})\n📉 ضعیف‌ترین روز: {worst[0]} ({worst[1]:+,})\n➗ میانگین روزانه: {avg:+.1f}")
    return "\n\n".join(parts) or "چنلی اضافه نشده."
# END-1
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
GROUP_RE = re.compile(r"(?:\$\s*\d[\d,.]*|\d[\d,.]*\s*(?:ton|تون|دلار|\$|usd|dollar|تومان|تومن|toman))")

def parse_calc(text):
    t = text.strip().lower().translate(DIGITS)
    t = t.replace(",", "").replace("٬", "").replace("٫", ".")
    m = re.search(r"\d+(?:\.\d+)?", t)
    if not m:
        return None
    value = float(m.group())
    if value <= 0 or value > 1e12:
        return None
    if any(k in t for k in ("تومان", "تومن", "toman", "irt")):
        unit = "irt"
    elif any(k in t for k in ("دلار", "$", "usd", "dollar")):
        unit = "usd"
    else:
        unit = "ton"
    return value, unit

def fmt_ton(x):
    return f"{x:,.4f}".rstrip("0").rstrip(".")

def cooldown_ok(key, secs):
    now = time.time()
    if now - last_calc.get(key, 0) < secs:
        return False
    last_calc[key] = now
    return True

def calc_reply(chat, text, reply_to=None, key=None, cooldown=1):
    if not cooldown_ok(key or chat, cooldown):
        return
    parsed = parse_calc(text)
    if not parsed:
        say_reply(chat, PUBLIC_HELLO, reply_to)
        return
    value, unit = parsed
    try:
        p = get_price_cached()
    except Exception:
        say_reply(chat, "قیمت فعلاً در دسترس نیست. کمی بعد دوباره امتحان کن.", reply_to)
        return
    rate = get_rate_cached()
    if unit == "irt" and not rate:
        say_reply(chat, "نرخ تومان فعلاً در دسترس نیست. کمی بعد دوباره امتحان کن.", reply_to)
        return
    if unit == "ton":
        ton = value
    elif unit == "usd":
        ton = value / p
    else:
        ton = value / (p * rate)
    usd = ton * p
    lines = ["🧮 ماشین‌حساب TON", "", f"💎 {fmt_ton(ton)} TON", f"💵 {usd:,.2f}$"]
    if rate:
        lines.append(f"🇮🇷 {usd * rate:,.0f} تومان")
    lines += ["", f"📊 قیمت هر TON: {p:.4f}$"]
    say_reply(chat, "\n".join(lines), reply_to)

def price_reply(chat, reply_to, key):
    if not cooldown_ok(key, 5):
        return
    try:
        p = get_price_cached()
    except Exception:
        say_reply(chat, "قیمت فعلاً در دسترس نیست.", reply_to)
        return
    rate = get_rate_cached()
    text = f"💎 TON: {p:.4f}$"
    if rate:
        text += f" | {p * rate:,.0f} تومان 🇮🇷"
    say_reply(chat, text, reply_to)

def bot_is_admin(chat):
    ok, t = bot_admin_cache.get(chat, (False, 0))
    if time.time() - t > 600:
        m = tg("getChatMember", chat_id=chat, user_id=BOT_ID).get("result", {})
        ok = m.get("status") in ("administrator", "creator")
        bot_admin_cache[chat] = (ok, time.time())
    return ok

def group_calc(msg):
    text = (msg.get("text") or "").strip()
    frm = msg.get("from") or {}
    if not text or frm.get("is_bot"):
        return
    chat = msg["chat"]["id"]
    is_price = False
    if text.startswith("/"):
        cmd, _, rest = text.partition(" ")
        cmd = cmd.split("@")[0].lower()
        if cmd == "/price":
            is_price = True
        elif cmd == "/calc" and rest.strip():
            text = rest.strip()
        else:
            return
    elif not GROUP_RE.fullmatch(text.translate(DIGITS).lower().strip()):
        return
    if not bot_is_admin(chat):
        return
    key = (chat, frm.get("id"))
    if is_price:
        price_reply(chat, msg["message_id"], key)
    else:
        calc_reply(chat, text, msg["message_id"], key, 5)

def send_backup(caption="💾 بکاپ ربات — برای بازیابی همین فایل رو برای ربات بفرست."):
    data = json.dumps({"version": 2, "channels": channels, "buttons": buttons, "known": known,
                       "charts": charts, "stats": stats}, ensure_ascii=False, indent=1).encode("utf-8")
    try:
        r = requests.post(f"{API}/sendDocument",
                          data={"chat_id": OWNER_ID, "caption": caption},
                          files={"document": ("backup_tonbot.json", data)}, timeout=40).json()
        return bool(r.get("ok"))
    except Exception as e:
        print("بکاپ:", e)
        return False

def handle_backup_file(chat, file_id):
    global pending_restore
    r = tg("getFile", file_id=file_id)
    if not r.get("ok"):
        say(chat, "⚠️ فایل رو نتونستم بگیرم.", PANEL_KB)
        return
    try:
        url = f"https://api.telegram.org/file/bot{TOKEN}/{r['result']['file_path']}"
        d = requests.get(url, timeout=30).json()
        if not isinstance(d, dict) or not isinstance(d.get("channels"), dict):
            raise ValueError("bad")
    except Exception:
        say(chat, "⚠️ این فایل بکاپ معتبر ربات نیست.", PANEL_KB)
        return
    pending_restore = d
    kb = {"inline_keyboard": [[{"text": "📥 بازیابی", "callback_data": "dorestore"}],
                              [{"text": "❌ لغو", "callback_data": "cancel"}]]}
    say(chat, f"📦 بکاپ پیدا شد.\nچنل‌ها: {len(d['channels'])}\nدکمه‌ها: {len(d.get('buttons', {}))}\nبا بازیابی، اطلاعات فعلی جایگزین می‌شه.", kb)

def do_restore(chat):
    global pending_restore, dirty
    d = pending_restore
    if not d:
        say(chat, "بکاپی برای بازیابی نیست. فایل بکاپ رو دوباره بفرست.", PANEL_KB)
        return
    channels.clear()
    channels.update({k: float(v) for k, v in d["channels"].items()})
    buttons.clear()
    buttons.update(d.get("buttons", {}))
    known.clear()
    known.update(d.get("known", {}))
    charts.clear()
    charts.update(d.get("charts", {}))
    stats.clear()
    stats.update(d.get("stats", {}))
    stats.setdefault("_last_report", time.time())
    save(channels)
    save_buttons()
    save_known()
    save_charts()
    save_stats()
    last_sent.clear()
    last_chart.clear()
    pending_restore = None
    dirty = False
    say(chat, f"✅ بازیابی شد. چنل‌ها: {len(channels)}", PANEL_KB)

def show_bkp(chat):
    kb = {"inline_keyboard": [[{"text": "📤 دریافت بکاپ الان", "callback_data": "bkpnow"}],
                              [{"text": "↩️ برگشت", "callback_data": "panel"}]]}
    say(chat, "💾 بکاپ و بازیابی\n\nبعد از هر تغییر، ربات خودش فایل بکاپ رو برات می‌فرسته.\nبرای بازیابی، فایل backup_tonbot.json رو همین‌جا برای ربات بفرست (یا فوروارد کن) تا دکمه‌ی «بازیابی» بیاد.", kb)

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

def norm_url(t):
    t = t.strip()
    if t.startswith("@"):
        return "https://t.me/" + t[1:]
    if t.startswith("t.me/"):
        return "https://" + t
    if t.startswith(("http://", "https://", "tg://")):
        return t
    return None

def show_btns(chat):
    if not channels:
        say(chat, "چنلی اضافه نشده.", PANEL_KB)
        return
    rows = []
    for c in channels:
        b = buttons.get(c)
        label = f"«{b['text']}»" if b and b.get("text") and b.get("url") else "بدون دکمه"
        rows.append([{"text": f"📍 {c} — {label}", "callback_data": "bset:" + c}])
    rows.append([{"text": "↩️ برگشت", "callback_data": "panel"}])
    say(chat, "دکمه‌ی زیر پیام کدوم چنل؟", {"inline_keyboard": rows})

def show_btn_menu(chat, c):
    b = buttons.get(c, {})
    txt = f"🔘 دکمه‌ی {c}\nمتن: {b.get('text', '—')}\nلینک: {b.get('url', '—')}"
    if not (b.get("text") and b.get("url")):
        txt += "\n(دکمه وقتی نمایش داده می‌شه که هم متن و هم لینک تنظیم شده باشه)"
    rows = [
        [{"text": "✏️ تغییر متن", "callback_data": "btxt:" + c},
         {"text": "🔗 تغییر لینک", "callback_data": "burl:" + c}],
        [{"text": "🗑 حذف دکمه", "callback_data": "bdel:" + c}],
        [{"text": "↩️ برگشت", "callback_data": "btns"}],
    ]
    say(chat, txt, {"inline_keyboard": rows})

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
    bot_admin_cache[chat["id"]] = (st in ("administrator", "creator"), time.time())
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

if FIRST_RUN:
    say(OWNER_ID, "🟢 ربات روشن شد.\n⚠️ فایل ذخیره‌شده‌ای پیدا نشد (اولین اجرا یا پاک شدن فایل‌ها). اگه بکاپ داری، فایل backup_tonbot.json رو برای ربات بفرست تا با یه دکمه برگرده.")
else:
    say(OWNER_ID, "🟢 ربات روشن شد.")
# END-2
def step():
    global offset, state, target_ch, target_cid, target_btn, pending, next_try, dirty, last_backup
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
        if not src:
            continue
        if msg and msg["chat"]["type"] in ("group", "supergroup"):
            group_calc(msg)
            continue
        if src["from"]["id"] != OWNER_ID:
            if msg and msg["chat"]["type"] == "private" and msg.get("text"):
                t = msg["text"].strip()
                if t.startswith("/start"):
                    say(msg["chat"]["id"], PUBLIC_HELLO)
                else:
                    calc_reply(msg["chat"]["id"], t)
            continue
        if msg:
            if msg["chat"]["type"] != "private":
                continue
            chat, text = msg["chat"]["id"], msg.get("text", "").strip()
            doc = msg.get("document")
            if doc and state is None and doc.get("file_name", "").startswith("backup"):
                handle_backup_file(chat, doc["file_id"])
                continue
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
            elif state == "btext":
                if target_btn in channels and text:
                    buttons.setdefault(target_btn, {})["text"] = text[:60]
                    save_buttons()
                state = None
                show_btn_menu(chat, target_btn)
            elif state == "burl":
                link = norm_url(text)
                if not link:
                    say(chat, "لینک معتبر نیست. با https:// یا @ شروع کن (یا «لغو»).")
                    continue
                if target_btn in channels:
                    buttons.setdefault(target_btn, {})["url"] = link
                    save_buttons()
                state = None
                show_btn_menu(chat, target_btn)
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
            elif state is None and text:
                calc_reply(chat, text)
        else:
            chat, data = cb["message"]["chat"]["id"], cb["data"]
            tg("answerCallbackQuery", callback_query_id=cb["id"])
            if data == "panel":
                say(chat, "پنل ادمین:", PANEL_KB)
            elif data == "bkp":
                show_bkp(chat)
            elif data == "bkpnow":
                if not send_backup("💾 بکاپ دستی"):
                    say(chat, "⚠️ بکاپ فرستاده نشد.", PANEL_KB)
            elif data == "dorestore":
                do_restore(chat)
            elif data == "charts":
                show_chart_list(chat)
            elif data.startswith("cset:"):
                show_chart_menu(chat, data[5:])
            elif data.startswith("cv:"):
                _, h, c = data.split(":", 2)
                if float(h) > 0:
                    charts[c] = float(h)
                    last_chart[c] = time.time()
                    save_charts()
                    say(chat, f"✅ {c}: نمودار هر {float(h):g} ساعت", PANEL_KB)
                else:
                    charts.pop(c, None)
                    save_charts()
                    say(chat, f"⛔ نمودار {c} خاموش شد.", PANEL_KB)
            elif data.startswith("cnow:"):
                ok = post_chart(data[5:])
                say(chat, "✅ نمودار فرستاده شد." if ok else "⚠️ نمودار فرستاده نشد (دلیلش جدا برات گزارش می‌شه).", PANEL_KB)
            elif data == "growth":
                say(chat, "📊 گزارش رشد چنل‌ها\n\n" + growth_text(), PANEL_KB)
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
            elif data == "btns":
                show_btns(chat)
            elif data.startswith("bset:"):
                show_btn_menu(chat, data[5:])
            elif data.startswith("btxt:"):
                target_btn = data[5:]
                state = "btext"
                say(chat, "متن دکمه رو بفرست (مثلاً: 🧮 ماشین‌حساب).\nبرای انصراف بنویس: لغو")
            elif data.startswith("burl:"):
                target_btn = data[5:]
                state = "burl"
                say(chat, "لینک دکمه رو بفرست (https://... یا @username).\nبرای انصراف بنویس: لغو")
            elif data.startswith("bdel:"):
                buttons.pop(data[5:], None)
                save_buttons()
                say(chat, "🗑 دکمه حذف شد.", PANEL_KB)
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
                    last_price.pop(c, None)
                    last_dot.pop(c, None)
                    last_chart.pop(c, None)
                    buttons.pop(c, None)
                    charts.pop(c, None)
                    stats.pop(c, None)
                    save(channels)
                    save_buttons()
                    save_charts()
                    save_stats()
                say(chat, f"🗑 حذف شد: {c}", PANEL_KB)
    now = time.time()
    due = [c for c, m in channels.items() if now - last_sent.get(c, 0) >= m * 60]
    if due and now >= next_try:
        try:
            p = get_price_cached()
            rate = get_rate_cached()
            for c in due:
                last_sent[c] = now
                prev = last_price.get(c)
                if prev is None or p > prev:
                    dot = "🟢"
                elif p < prev:
                    dot = "🔴"
                else:
                    dot = last_dot.get(c, "🟢")
                text = f"{dot} {p:.4f}$"
                if rate:
                    text += f" | {p * rate:,.0f} تومان 🇮🇷"
                last_price[c] = p
                last_dot[c] = dot
                kb = btn_markup(c)
                if kb:
                    res = tg("sendMessage", chat_id=c, text=text, reply_markup=kb)
                    if not res.get("ok"):
                        print(c, res)
                        res = tg("sendMessage", chat_id=c, text=text)
                else:
                    res = tg("sendMessage", chat_id=c, text=text)
                if not res.get("ok"):
                    print(c, res)
                    alert("send:" + c, f"⚠️ ارسال قیمت به {c} نشد: {res.get('description', '')}", 1800)
        except Exception as e:
            print("خطا:", e)
            alert("price", f"⚠️ گرفتن قیمت از CoinGecko خطا داد: {e}", 900)
            next_try = now + 15
    for c, h in list(charts.items()):
        if c not in channels or h <= 0:
            continue
        if c not in last_chart:
            last_chart[c] = now
            continue
        if now - last_chart[c] >= h * 3600:
            last_chart[c] = now
            if not post_chart(c):
                last_chart[c] = now - h * 3600 + 600
    record_stats()
    if now - stats.get("_last_report", now) >= 7 * 86400:
        stats["_last_report"] = now
        save_stats()
        say(OWNER_ID, "📊 گزارش هفتگی رشد چنل‌ها\n\n" + growth_text())
    if dirty and now - last_backup >= 30:
        dirty = False
        last_backup = now
        send_backup("💾 بکاپ خودکار بعد از تغییر")

while True:
    try:
        step()
    except Exception as e:
        print("خطای اصلی:", e)
        alert("crash", f"⚠️ ربات یه خطای غیرمنتظره خورد و ادامه می‌ده: {e}", 600)
        time.sleep(5)
# END
