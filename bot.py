import os, json, re
from flask import Flask
import threading
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot Clean Private-Only"
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
    with open(STATUS_FILE, "w", encoding="utf-8") as f: json.dump({"paused": p}, f)
BOT_PAUSED = load_status()

def load_knowledge():
    if os.path.exists(KNOWLEDGE_FILE):
        try: return open(KNOWLEDGE_FILE, "r", encoding="utf-8").read()
        except: return ""
    return ""
def save_knowledge(t):
    with open(KNOWLEDGE_FILE, "a", encoding="utf-8") as f: f.write("\n" + t + "\n---")
def clear_knowledge():
    open(KNOWLEDGE_FILE, "w", encoding="utf-8").close()
    open(CACHE_FILE, "w", encoding="utf-8").close() if os.path.exists(CACHE_FILE) else None

def load_cache():
    if os.path.exists(CACHE_FILE):
        try: return json.load(open(CACHE_FILE, "r", encoding="utf-8"))
        except: return {}
    return {}
def save_cache(c):
    with open(CACHE_FILE, "w", encoding="utf-8") as f: json.dump(c, f, ensure_ascii=False)
cache_data = load_cache()

def is_trivial(text):
    if not text: return True
    t=text.strip().lower()
    if len(t)<=1: return True
    return False

def is_order_question(text):
    if not text: return False
    t = text.lower()
    keywords = ["طلبي","طلبية","طلبيتي","رقم الطلب","وين طلبي","فين طلبي","متى يوصل","تتبع","الشحنة","شحنتي","توصيل","order"]
    return any(k in t for k in keywords)

# بدون اي تعليمات - فاضي تماما - انت تعلمه
SYSTEM_PROMPT = """
انت مساعد. لا تستخدم معلومات من عندك. استخدم فقط الذاكرة التالية التي علمك بها الأدمن في الخاص:
{knowledge}

اذا الذاكرة فاضية و المستخدم قال سلام او مرحبا او هلا او كيفك او ممتاز او طيب او تصبح خير، رد بتحية مناسبة بسيطة فقط.
اذا الذاكرة فاضية وسأل عن شيء، قل: المعلومة غير موجودة حاليا، الأدمن سيضيفها قريبا.
اذا الذاكرة فيها معلومات، جاوب منها فقط بلهجة سعودية ودودة ومختصرة.
"""

MODEL_NAME = "gemini-1.5-flash"  # هذا يشتغل 100% مع 1500 رسالة باليوم

async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED=False; save_status(False)
    await update.message.reply_text("اشتغلت", reply_to_message_id=update.message.message_id)

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED=True; save_status(True)
    await update.message.reply_text("وقفت", reply_to_message_id=update.message.message_id)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    clear_knowledge()
    cache_data.clear()
    save_cache({})
    await update.message.reply_text("✅ تم مسح جميع التعليمات - البوت صار فاضي تماما\nالآن علمه من الخاص بـ: احفظ + المعلومة", reply_to_message_id=update.message.message_id)

async def arabic_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    txt = update.message.text.strip().replace("/","")
    if txt=="شغل":
        BOT_PAUSED=False; save_status(False)
        await update.message.reply_text("اشتغلت", reply_to_message_id=update.message.message_id)
    elif txt=="وقف":
        BOT_PAUSED=True; save_status(True)
        await update.message.reply_text("وقفت", reply_to_message_id=update.message.message_id)
    elif txt in ["مسح","امسح","احذف"]:
        clear_knowledge(); cache_data.clear(); save_cache({})
        await update.message.reply_text("✅ تم مسح كل شيء - البوت فاضي الآن", reply_to_message_id=update.message.message_id)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if update.effective_user.is_bot: return
    user_text=update.message.text or ""
    uid=str(update.effective_user.id)
    chat_type=update.effective_chat.type
    low_text = user_text.strip().lower()

    # === الخاص - تعليم فقط ===
    if chat_type == "private" and uid in ADMIN_IDS:
        if low_text in ["مسح","امسح","احذف","احذف جميع التعليمات","امسح كل شي"]:
            clear_knowledge(); cache_data.clear(); save_cache({})
            await update.message.reply_text("✅ تم مسح جميع التعليمات - البوت صار فاضي\nالآن ابدأ تعليمه: احفظ الشرح كذا وكذا", reply_to_message_id=update.message.message_id)
            return
        if update.message.reply_to_message and "السؤال:" in (update.message.reply_to_message.text or ""):
            orig = update.message.reply_to_message.text or ""
            m = re.search(r'السؤال:\s*(.*)', orig)
            q = m.group(1) if m else orig
            save_knowledge(f"سؤال: {q}\nجواب: {user_text}")
            cache_data.clear(); save_cache(cache_data)
            await update.message.reply_text(f"✅ حفظت الجواب", reply_to_message_id=update.message.message_id)
            return
        if low_text.startswith(("احفظ","تذكر","خزن")):
            clean = user_text
            for w in ["احفظ","تذكر","خزن"]: clean = clean.replace(w,"").strip(" :")
            if clean and len(clean) > 2:
                save_knowledge(clean)
                cache_data.clear(); save_cache(cache_data)
                await update.message.reply_text(f"✅ حفظت:\n{clean}", reply_to_message_id=update.message.message_id)
            else:
                await update.message.reply_text("اكتب بعد كلمة احفظ المعلومة كاملة", reply_to_message_id=update.message.message_id)
            return
        # اي كلام ثاني في الخاص هو اختبار للبوت بعد التعليم
        if is_trivial(user_text): return
        knowledge = load_knowledge()
        if not knowledge.strip():
            await update.message.reply_text("البوت فاضي حاليا، ابدأ تعليمه بـ:\nاحفظ المعلومة اللي تبيها", reply_to_message_id=update.message.message_id)
            return
        prompt = SYSTEM_PROMPT.format(knowledge=knowledge) + f"\nرسالة: {user_text}"
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            res = model.generate_content(prompt)
            if res.text: await update.message.reply_text(res.text, reply_to_message_id=update.message.message_id)
        except Exception as e:
            await update.message.reply_text(f"خطأ: {str(e)[:200]}", reply_to_message_id=update.message.message_id)
        return

    # === القروب - ادمن يوقف فقط ===
    if chat_type in ["group","supergroup"] and uid in ADMIN_IDS:
        if not user_text.startswith("/") and not low_text.startswith(("احفظ","تذكر","خزن")):
            BOT_PAUSED=True; save_status(True); return

    if BOT_PAUSED: return
    if is_trivial(user_text): return

    if is_order_question(user_text):
        for aid in ADMIN_IDS:
            try: await context.bot.send_message(chat_id=int(aid), text=f"📦 سؤال عن طلب من {update.effective_user.first_name}: {user_text}\nرد على هذه الرسالة بجوابك")
            except: pass
        await update.message.reply_text("حولت استفسارك عن الطلب للأدمن 📦", reply_to_message_id=update.message.message_id)
        return

    knowledge = load_knowledge()
    # اذا البوت فاضي وما تعلم شيء، لا يهبد
    if not knowledge.strip():
        # ردود تحية بسيطة بدون ذكاء
        if low_text in ["مرحبا","هلا","السلام","سلام","هلا والله","كيفك","كيف حالك"]:
            await update.message.reply_text("هلا والله، حياك", reply_to_message_id=update.message.message_id)
            return
        if low_text in ["تصبح خير","تصبح على خير","ممتاز","طيب"]:
            await update.message.reply_text(low_text, reply_to_message_id=update.message.message_id)
            return
        await update.message.reply_text("المعلومة غير موجودة حاليا، الأدمن بيضيفها قريبا", reply_to_message_id=update.message.message_id)
        return

    prompt = SYSTEM_PROMPT.format(knowledge=knowledge) + f"\nرسالة العضو: {user_text}"
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        res = model.generate_content(prompt)
        if res.text: await update.message.reply_text(res.text, reply_to_message_id=update.message.message_id)
    except: pass

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.is_bot or BOT_PAUSED: return
    if is_order_question(update.message.caption or ""):
        for aid in ADMIN_IDS:
            try: await context.bot.send_message(chat_id=int(aid), text=f"صورة لطلب: {update.message.caption}")
            except: pass
        await update.message.reply_text("حولت صورتك للأدمن 📦", reply_to_message_id=update.message.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("on", on_command))
    app.add_handler(CommandHandler("off", off_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.Regex(r'^/?(شغل|وقف|مسح|امسح|احذف)$'), arabic_commands))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print(f"Running Clean Private-Only {MODEL_NAME}")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
