import os, json, re
from flask import Flask
import threading
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot Free Chat OK"
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
    if os.path.exists(CACHE_FILE): os.remove(CACHE_FILE)

def load_cache():
    if os.path.exists(CACHE_FILE):
        try: return json.load(open(CACHE_FILE, "r", encoding="utf-8"))
        except: return {}
    return {}
def save_cache(c):
    with open(CACHE_FILE, "w", encoding="utf-8") as f: json.dump(c, f, ensure_ascii=False)
cache_data = load_cache()

def is_order_question(text):
    if not text: return False
    t = text.lower()
    keywords = ["طلبي","طلبية","رقم الطلب","وين طلبي","فين طلبي","متى يوصل","تتبع","الشحنة","شحنتي","توصيل"]
    return any(k in t for k in keywords)

# هذا يخليه يسولف حر + يستخدم ذاكرتك
SYSTEM_PROMPT = """
انت مساعد ذكي وودود لمتجر خرائط رحال، ترد بلهجة سعودية بيضاء بشكل حر وطبيعي ومحترف.

مهمتك:
- ترد على التحيات: مرحبا، السلام عليكم، هلا، كيفك، ممتاز، طيب، تصبح على خير، تصبح خير.. رد بتحية مناسبة وطبيعية ومتنوعة، لا تكرر نفس الجملة.
- تشرح اي شيء: شرح الشراء، طرق الدفع، الخرائط، اي سؤال عام جاوب بذكاء من عندك.
- عندك ذاكرة اضافية علمك بها الادمن في الخاص:
{knowledge}
اذا فيها معلومة تناسب السؤال استخدمها اولاً.

- اذا سأل عن طلبه الخاص (وين طلبي) لا تجاوب انت، قل سيتم تحويلك للادمن.
"""

MODEL_NAME = "gemini-1.5-flash"

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

async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    clear_knowledge()
    await update.message.reply_text("✅ تم مسح جميع التعليمات القديمة\nالآن البوت فاضي وبيسولف حر، علمه من جديد بـ: احفظ", reply_to_message_id=update.message.message_id)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if update.effective_user.is_bot: return
    user_text=update.message.text or ""
    uid=str(update.effective_user.id)
    chat_type=update.effective_chat.type
    low = user_text.strip().lower()

    # الخاص - الادمن يعلم
    if chat_type == "private" and uid in ADMIN_IDS:
        if low in ["مسح","امسح","احذف","احذف جميع التعليمات","مسح الكل"]:
            clear_knowledge()
            await update.message.reply_text("✅ مسحت كل شيء، البوت الآن يسولف حر بدون ذاكرة قديمة\nعلمه الآن: احفظ المعلومة", reply_to_message_id=update.message.message_id)
            return
        if low.startswith(("احفظ","تذكر","خزن")):
            clean = user_text
            for w in ["احفظ","تذكر","خزن"]: clean = clean.replace(w,"").strip(" :")
            if len(clean) > 2:
                save_knowledge(clean)
                await update.message.reply_text(f"✅ حفظت:\n{clean}", reply_to_message_id=update.message.message_id)
            return
        if update.message.reply_to_message and "السؤال:" in (update.message.reply_to_message.text or ""):
            orig = update.message.reply_to_message.text or ""
            m = re.search(r'السؤال:\s*(.*)', orig)
            q = m.group(1) if m else orig
            save_knowledge(f"سؤال: {q}\nجواب: {user_text}")
            await update.message.reply_text("✅ حفظت الجواب", reply_to_message_id=update.message.message_id)
            return

    if BOT_PAUSED: return

    if is_order_question(user_text):
        for aid in ADMIN_IDS:
            try: await context.bot.send_message(chat_id=int(aid), text=f"📦 سؤال طلب من {update.effective_user.first_name}: {user_text}")
            except: pass
        await update.message.reply_text("حولت سؤالك عن الطلب للأدمن 📦", reply_to_message_id=update.message.message_id)
        return

    knowledge = load_knowledge()
    prompt = SYSTEM_PROMPT.format(knowledge=knowledge) + f"\nرسالة المستخدم: {user_text}"
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        res = model.generate_content(prompt)
        if res.text and res.text.strip():
            await update.message.reply_text(res.text, reply_to_message_id=update.message.message_id)
        else:
            await update.message.reply_text("هلا والله، معك تفضل", reply_to_message_id=update.message.message_id)
    except Exception as e:
        # لو صار خطأ يعلمنا السبب الحقيقي مو هلا والله
        print(f"Gemini Error: {e}")
        await update.message.reply_text("هلا والله، حياك، وش تبي تعرف؟", reply_to_message_id=update.message.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("on", on_command))
    app.add_handler(CommandHandler("off", off_command))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("مسح", clear_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print(f"Running FREE CHAT {MODEL_NAME}")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
