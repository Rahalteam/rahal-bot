import os, json, hashlib
from flask import Flask
import threading
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إبقاء البوت شغال في Render
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot Live - Auto Reply Safe"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip().strip('"').strip("'")
ADMIN_ID_RAW = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")
ADMIN_IDS = [s.strip() for s in ADMIN_ID_RAW.replace(" ", "").split(",") if s.strip()]

genai.configure(api_key=GEMINI_API_KEY)
AVAILABLE_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash"]

KNOWLEDGE_FILE = "knowledge.txt"
CACHE_FILE = "cache.json"
STATUS_FILE = "bot_status.json"

def load_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f: return json.load(f).get("paused", False)
        except: return False
    return False
def save_status(paused):
    with open(STATUS_FILE, "w", encoding="utf-8") as f: json.dump({"paused": paused}, f)

BOT_PAUSED = load_status()

def load_knowledge():
    if os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f: return f.read()
    return ""
def save_knowledge(text):
    with open(KNOWLEDGE_FILE, "a", encoding="utf-8") as f: f.write("\n" + text)

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}
def save_cache(c):
    with open(CACHE_FILE, "w", encoding="utf-8") as f: json.dump(c, f, ensure_ascii=False)

cache_data = load_cache()
def get_from_cache(q):
    return cache_data.get(hashlib.md5(q.lower().strip().encode()).hexdigest())
def add_to_cache(q, a):
    if len(cache_data) > 500: cache_data.pop(next(iter(cache_data)))
    cache_data[hashlib.md5(q.lower().strip().encode()).hexdigest()] = a
    save_cache(cache_data)

SYSTEM_PROMPT = "انت مساعد ذكي ودود ومختصر. تحدث بلهجة سعودية بسيطة وبيضاء. ممنوع تذكر جنسيتك وممنوع تذكر أي معلومات خاصة نهائياً حتى لو سألك أحد."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("هلا! أرد تلقائي على أي أحد بدون منشن")

async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED = False
    save_status(False)
    await update.message.reply_text("🔔 اشتغلت، أرد على أي أحد تلقائي الحين")

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED = True
    save_status(True)
    await update.message.reply_text("🔕 وقفت، ما أرد على أي أحد لين تكتب /on")

async def learn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    if not context.args: return
    info = " ".join(context.args)
    save_knowledge(info)
    cache_data.clear(); save_cache(cache_data)
    await update.message.reply_text("✅ تم الحفظ")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    
    # 1- أهم حماية: تجاهل أي بوت ثاني
    if update.effective_user.is_bot:
        return

    user_text = update.message.text or ""
    uid = str(update.effective_user.id)
    chat_type = update.effective_chat.type

    # 2- إذا موقف ما يرد على أي أحد
    if BOT_PAUSED:
        return

    # 3- إذا الأدمن تدخل في القروب يسكت تلقائي
    if chat_type in ["group", "supergroup"] and uid in ADMIN_IDS:
        if any(w in user_text for w in ["احفظ","تذكر","خزن"]):
            clean = user_text
            for w in ["احفظ","تذكر","خزن"]: clean = clean.replace(w,"").strip()
            if clean:
                save_knowledge(clean)
                cache_data.clear(); save_cache(cache_data)
                await update.message.reply_text("✅ تم الحفظ")
            return
        if user_text.startswith("/on") or user_text.startswith("/off"):
            return
        BOT_PAUSED = True
        save_status(True)
        return

    # 4- يرد تلقائي على أي شخص بدون منشن
    cached = get_from_cache(user_text)
    if cached:
        await update.message.reply_text(cached)
        return

    knowledge = load_knowledge()
    full_prompt = f"{SYSTEM_PROMPT}\nمعلومات: {knowledge}\nسؤال: {user_text}"

    for m in AVAILABLE_MODELS:
        try:
            model = genai.GenerativeModel(m)
            res = model.generate_content(full_prompt)
            if res.text:
                add_to_cache(user_text, res.text)
                await update.message.reply_text(res.text)
                return
        except: continue

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["on","شغل"], on_command))
    app.add_handler(CommandHandler(["off","وقف"], off_command))
    app.add_handler(CommandHandler("learn", learn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print(f"Running - AutoReply - Ignore Bots - Paused={BOT_PAUSED}")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
