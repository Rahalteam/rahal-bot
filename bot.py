import os, json, re
from flask import Flask
import threading
from google import genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot Free OK New SDK"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip().strip('"').strip("'")
ADMIN_ID_RAW = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")
ADMIN_IDS = [s.strip() for s in ADMIN_ID_RAW.replace(" ", "").split(",") if s.strip()]

client = genai.Client(api_key=GEMINI_API_KEY)

KNOWLEDGE_FILE = "knowledge.txt"
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

def is_order_question(text):
    if not text: return False
    t = text.lower()
    keywords = ["طلبي","طلبية","رقم الطلب","وين طلبي","فين طلبي","متى يوصل","تتبع","الشحنة","شحنتي"]
    return any(k in t for k in keywords)

def ask_gemini(prompt):
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None

SYSTEM_PROMPT = """
انت مساعد ذكي لمتجر خرائط رحال، لهجتك سعودية ودودة وطبيعية.

- لا تكرر نفس الجملة ابدا. نوع ردودك.
- اذا قال مرحبا قل هلا والله نورت، اذا قال شكرا لك قل العفو حاضرين، اذا قال السلام عليكم قل وعليكم السلام ورحمة الله، اذا قال تصبح على خير قل وانت من اهل الخير.
- اذا قال اريد شرح اشرح له خطوات الشراء من المتجر بذكاء من عندك.
- اذا قال ممتاز او طيب قل الله يسعدك، اي خدمة ثانية؟
- ترد بشكل حر وذكي ومختصر.

معلومات اضافية علمك بها الادمن:
{knowledge}
"""

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
    await update.message.reply_text("✅ تم مسح كل التعليمات القديمة، الآن البوت نظيف ويسولف حر", reply_to_message_id=update.message.message_id)

async def arabic_control(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    txt = update.message.text.strip().lower().replace("/","")
    if txt in ["شغل","تشغيل"]:
        BOT_PAUSED=False; save_status(False)
        await update.message.reply_text("اشتغلت", reply_to_message_id=update.message.message_id)
    elif txt in ["وقف","ايقاف"]:
        BOT_PAUSED=True; save_status(True)
        await update.message.reply_text("وقفت", reply_to_message_id=update.message.message_id)
    elif txt in ["مسح","امسح","احذف"]:
        clear_knowledge()
        await update.message.reply_text("✅ تم المسح، البوت صار نظيف ويسولف حر", reply_to_message_id=update.message.message_id)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if update.effective_user.is_bot: return
    user_text=update.message.text or ""
    uid=str(update.effective_user.id)
    chat_type=update.effective_chat.type
    low = user_text.strip().lower()

    if chat_type == "private" and uid in ADMIN_IDS:
        if low in ["مسح","امسح","احذف","احذف جميع التعليمات"]:
            clear_knowledge()
            await update.message.reply_text("✅ مسحت كل شيء", reply_to_message_id=update.message.message_id)
            return
        if low.startswith(("احفظ","تذكر","خزن")):
            clean = user_text
            for w in ["احفظ","تذكر","خزن"]: clean = clean.replace(w,"").strip(" :")
            if len(clean) > 2:
                save_knowledge(clean)
                await update.message.reply_text(f"✅ حفظت:\n{clean}", reply_to_message_id=update.message.message_id)
            return

    if BOT_PAUSED: return
    if is_order_question(user_text):
        for aid in ADMIN_IDS:
            try: await context.bot.send_message(chat_id=int(aid), text=f"📦 سؤال طلب: {user_text}")
            except: pass
        await update.message.reply_text("حولت سؤالك للأدمن 📦", reply_to_message_id=update.message.message_id)
        return

    knowledge = load_knowledge()
    prompt = SYSTEM_PROMPT.format(knowledge=knowledge) + f"\nالمستخدم قال: {user_text}\nردك:"
    
    answer = ask_gemini(prompt)
    if answer:
        await update.message.reply_text(answer, reply_to_message_id=update.message.message_id)
    else:
        # رد احتياطي متنوع لو فشل gemini
        if "مرحبا" in low: await update.message.reply_text("هلا والله، نورت", reply_to_message_id=update.message.message_id)
        elif "سلام" in low: await update.message.reply_text("وعليكم السلام ورحمة الله، حياك", reply_to_message_id=update.message.message_id)
        elif "شكرا" in low: await update.message.reply_text("العفو، حاضرين", reply_to_message_id=update.message.message_id)
        elif "شرح" in low: await update.message.reply_text("تدخل المتجر، تختار الخريطة اللي تبيها، تضيفها للسلة، وتكمل الدفع، ويوصلك الطلب", reply_to_message_id=update.message.message_id)
        elif "ممتاز" in low or "طيب" in low: await update.message.reply_text("الله يسعدك، أي خدمة ثانية؟", reply_to_message_id=update.message.message_id)
        else: await update.message.reply_text("هلا بك، تفضل", reply_to_message_id=update.message.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("on", on_command))
    app.add_handler(CommandHandler("off", off_command))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(MessageHandler(filters.Regex(r'^(/?شغل|/?وقف|/?مسح|/?امسح|/?احذف)$'), arabic_control))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Running New SDK gemini-2.0-flash")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
