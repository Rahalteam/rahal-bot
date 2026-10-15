import os, json, hashlib, re
from flask import Flask
import threading
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot Live"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip().strip('"').strip("'")
ADMIN_ID_RAW = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")
ADMIN_IDS = [s.strip() for s in ADMIN_ID_RAW.replace(" ", "").split(",") if s.strip()]

genai.configure(api_key=GEMINI_API_KEY)

KNOWLEDGE_FILE = "knowledge.txt"
CACHE_FILE = "cache.json"
STATUS_FILE = "bot_status.json"

def load_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f: return json.load(f).get("paused", False)
        except: return False
    return False

def save_status(p):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump({"paused": p}, f)

BOT_PAUSED = load_status()

def load_knowledge():
    return open(KNOWLEDGE_FILE, "r", encoding="utf-8").read() if os.path.exists(KNOWLEDGE_FILE) else ""

def save_knowledge(t):
    with open(KNOWLEDGE_FILE, "a", encoding="utf-8") as f:
        f.write("\n" + t + "\n---")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE, "r", encoding="utf-8"))
        except:
            return {}
    return {}

def save_cache(c):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False)

cache_data = load_cache()

def is_trivial(text):
    if not text:
        return True
    t = text.strip().lower()
    if len(t) <= 2:
        return True
    if t in ["هههه", "ههههه", "هه", "😂", "❤️", "👍"]:
        return True
    return False

def is_order_question(text):
    if not text:
        return False
    t = text.lower()
    keywords = ["طلبي", "طلبية", "طلبيتي", "رقم الطلب", "وين طلبي", "فين طلبي", "متى يوصل", "تتبع", "الشحنة", "شحنتي", "توصيل", "order"]
    return any(k in t for k in keywords)

SYSTEM_PROMPT = "انت مساعد متجر خرائط رحال، ودود بلهجة سعودية بيضاء. تتحدث بحرية عن اي شيء. معلومات متجرك: {knowledge} . مهم: اذا سألك عن طلبه الخاص لا تجاوب، سيتم تحويله للأدمن."

async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS:
        return
    BOT_PAUSED = False
    save_status(False)
    await update.message.reply_text("اشتغلت", reply_to_message_id=update.message.message_id)

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS:
        return
    BOT_PAUSED = True
    save_status(True)
    await update.message.reply_text("وقفت", reply_to_message_id=update.message.message_id)

async def arabic_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS:
        return
    txt = update.message.text.strip().replace("/", "")
    if txt == "شغل":
        BOT_PAUSED = False
        save_status(False)
        await update.message.reply_text("اشتغلت", reply_to_message_id=update.message.message_id)
    elif txt == "وقف":
        BOT_PAUSED = True
        save_status(True)
        await update.message.reply_text("وقفت", reply_to_message_id=update.message.message_id)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if update.effective_user.is_bot:
        return
    user_text = update.message.text or ""
    uid = str(update.effective_user.id)
    chat_type = update.effective_chat.type
    low_text = user_text.strip().lower()

    if chat_type == "private" and uid in ADMIN_IDS:
        if update.message.reply_to_message and "السؤال:" in (update.message.reply_to_message.text or ""):
            orig = update.message.reply_to_message.text or ""
            m = re.search(r'السؤال:\s*(.*)', orig)
            q = m.group(1) if m else orig
            save_knowledge(f"سؤال: {q}\nجواب معتمد: {user_text}")
            cache_data.clear()
            save_cache(cache_data)
            await update.message.reply_text("حفظت", reply_to_message_id=update.message.message_id)
            return
        if low_text.startswith(("احفظ", "تذكر", "خزن")):
            clean = user_text
            for w in ["احفظ", "تذكر", "خزن"]:
                clean = clean.replace(w, "").strip()
            if clean and len(clean) > 3:
                save_knowledge(clean)
                cache_data.clear()
                save_cache(cache_data)
                await update.message.reply_text("حفظت في الذاكرة", reply_to_message_id=update.message.message_id)
            return
        if is_trivial(user_text):
            return
        knowledge = load_knowledge()
        prompt = SYSTEM_PROMPT.format(knowledge=knowledge) + f"\nرسالة الأدمن: {user_text}"
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            res = model.generate_content(prompt)
            if res.text:
                await update.message.reply_text(res.text, reply_to_message_id=update.message.message_id)
        except:
            await update.message.reply_text("هلا والله", reply_to_message_id=update.message.message_id)
        return

    if chat_type in ["group", "supergroup"] and uid in ADMIN_IDS:
        if update.message.reply_to_message and not update.message.reply_to_message.from_user.is_bot and len(user_text) > 2:
            orig = update.message.reply_to_message.text or ""
            save_knowledge(f"سؤال: {orig}\nجواب معتمد: {user_text}")
            cache_data.clear()
            save_cache(cache_data)
            await update.message.reply_text("تعلمت", reply_to_message_id=update.message.message_id)
            BOT_PAUSED = True
            save_status(True)
            return
        if low_text.startswith(("احفظ", "تذكر", "خزن")) and len(user_text) > 10:
            clean = user_text
            for w in ["احفظ", "تذكر", "خزن"]:
                clean = clean.replace(w, "").strip()
            save_knowledge(clean)
            cache_data.clear()
            save_cache(cache_data)
            await update.message.reply_text("تم الحفظ", reply_to_message_id=update.message.message_id)
            return
        if not user_text.startswith("/"):
            BOT_PAUSED = True
            save_status(True)
            return

    if BOT_PAUSED:
        return
    if is_trivial(user_text):
        return

    if is_order_question(user_text):
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=int(aid), text=f"سؤال عن طلب من {update.effective_user.first_name}: {user_text}\n\nرد على هذه الرسالة بجوابك")
            except:
                pass
        await update.message.reply_text("حولت استفسارك عن الطلب للأدمن", reply_to_message_id=update.message.message_id)
        return

    knowledge = load_knowledge()
    prompt = SYSTEM_PROMPT.format(knowledge=knowledge) + f"\nرسالة العضو: {user_text}"
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        res = model.generate_content(prompt)
        if res.text:
            await update.message.reply_text(res.text, reply_to_message_id=update.message.message_id)
    except:
        pass

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.is_bot or BOT_PAUSED:
        return
    try:
        photo_file = await update.message.photo[-1].get_file()
        await photo_file.download_to_drive("temp_photo.jpg")
        img = Image.open("temp_photo.jpg")
        caption = update.message.caption or ""
        if is_order_question(caption):
            for aid in ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=int(aid), text=f"صورة لطلب: {caption}")
                except:
                    pass
            await update.message.reply_text("حولت صورتك للأدمن", reply_to_message_id=update.message.message_id)
            return
        prompt = SYSTEM_PROMPT.format(knowledge=load_knowledge()) + f" حلل الصورة: {caption}"
        model = genai.GenerativeModel("gemini-2.5-flash")
        res = model.generate_content([prompt, img])
        if res.text:
            await update.message.reply_text(res.text, reply_to_message_id=update.message.message_id)
    except:
        pass

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("on", on_command))
    app.add_handler(CommandHandler("off", off_command))
    app.add_handler(MessageHandler(filters.Regex(r'^/?(شغل|وقف)$'), arabic_commands))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Running Fixed OK")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
