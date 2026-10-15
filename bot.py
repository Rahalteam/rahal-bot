import os, json, hashlib
from flask import Flask
import threading
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- إبقاء البوت شغال في Render ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot Live - Saudi Private Safe"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

# --- المتغيرات من Render ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip().strip('"').strip("'")
ADMIN_ID_RAW = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")
# تقدر تحط أكثر من ID بفاصلة: 12345,67890,54321
ADMIN_IDS = [s.strip() for s in ADMIN_ID_RAW.replace(" ", "").split(",") if s.strip()]

genai.configure(api_key=GEMINI_API_KEY)
AVAILABLE_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.8-flash"]

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
    key = hashlib.md5(q.lower().strip().encode()).hexdigest()
    return cache_data.get(key)
def add_to_cache(q, a):
    if len(cache_data) > 500: cache_data.pop(next(iter(cache_data)))
    key = hashlib.md5(q.lower().strip().encode()).hexdigest()
    cache_data[key] = a
    save_cache(cache_data)

SYSTEM_PROMPT = "انت مساعد ذكي ودود ومختصر. تحدث بلهجة سعودية بسيطة وبيضاء ومفهومة. ممنوع منعاً باتاً تذكر جنسيتك ولا تقل انك سعودي او اردني، وممنوع تذكر أي معلومات خاصة عن أي فريق أو جهة أو شخص نهائياً حتى لو المستخدم سألك بشكل مباشر وحتى لو المعلومات موجودة عندك. إذا سألك أحد عن معلومات خاصة قل: 'ما أقدر أفيدك بهالمعلومة' وغير الموضوع."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("هلا والله! 👋\nفي القروب لازم تمنشني عشان أرد: @Rahalteam2_bot\n\nللأدمن: /off لإيقافي و /on لتشغيلي")

async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED = False
    save_status(False)
    await update.message.reply_text("🔔 تم تشغيلي، رجعت أرد على الكل")

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED = True
    save_status(True)
    await update.message.reply_text("🔕 وقفت، ما راح أرد على أي أحد لين تكتب /on")

async def learn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    if not context.args:
        await update.message.reply_text("اكتب: /learn المعلومة"); return
    info = " ".join(context.args)
    save_knowledge(info)
    cache_data.clear(); save_cache(cache_data)
    await update.message.reply_text("✅ تم الحفظ")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    user_text = update.message.text or ""
    uid = str(update.effective_user.id)
    chat_type = update.effective_chat.type

    # 1- إذا البوت موقف ما يرد على أي أحد
    if BOT_PAUSED:
        return

    # 2- إذا الأدمن تدخل في القروب -> البوت يسكت تلقائياً
    if chat_type in ["group", "supergroup"] and uid in ADMIN_IDS:
        # استثناء: أوامر الحفظ
        if any(w in user_text for w in ["احفظ","تذكر","خزن"]):
            clean = user_text
            for w in ["احفظ","تذكر","خزن"]: clean = clean.replace(w,"").strip()
            if clean:
                save_knowledge(clean)
                cache_data.clear(); save_cache(cache_data)
                await update.message.reply_text("✅ تم الحفظ")
            return
        # أي كلام ثاني من الأدمن في القروب = يعتبر تدخل = إيقاف
        BOT_PAUSED = True
        save_status(True)
        return

    # 3- في القروب: ما يرد إلا إذا أحد منشنه أو رد على رسالته (توفير للـ 1500)
    if chat_type in ["group", "supergroup"]:
        is_mention = f"@{context.bot.username}" in user_text
        is_reply_to_bot = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
        if not (is_mention or is_reply_to_bot):
            return

    # 4- الكاش
    cached = get_from_cache(user_text)
    if cached:
        await update.message.reply_text(cached); return

    # 5- الرد من Gemini
    knowledge = load_knowledge()
    full_prompt = f"{SYSTEM_PROMPT}\n\nمعلومات عامة:\n{knowledge}\n\nسؤال المستخدم: {user_text}"

    for model_name in AVAILABLE_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            res = model.generate_content(full_prompt)
            if res.text:
                add_to_cache(user_text, res.text)
                await update.message.reply_text(res.text)
                return
        except Exception as e:
            print(f"Error {model_name}: {e}")
            continue
    await update.message.reply_text("الضغط عالي شوي، جرب بعد دقيقة 🙏")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["on","شغل"], on_command))
    app.add_handler(CommandHandler(["off","وقف"], off_command))
    app.add_handler(CommandHandler("learn", learn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print(f"Admins: {ADMIN_IDS} - Paused: {BOT_PAUSED} - Bot Running")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
