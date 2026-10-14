import os
from flask import Flask
import threading
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 1. حل مشكلة Render ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "Rahal Bot is Live @Rahalteam2_bot - OK - Auto Learn Active"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# --- 2. قراءة المتغيرات ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip().strip('"').strip("'")
ADMIN_ID = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")

print(f"--- ENV CHECK --- Token: {bool(TELEGRAM_TOKEN)} | Gemini: {bool(GEMINI_API_KEY)} | Admin: {ADMIN_ID}")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise ValueError("تأكد من TELEGRAM_TOKEN و GEMINI_API_KEY في Render")

# --- 3. اعداد Gemini بالموديلات الجديدة ---
genai.configure(api_key=GEMINI_API_KEY)
AVAILABLE_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-2.5-flash-lite"]

KNOWLEDGE_FILE = "knowledge.txt"

def load_knowledge():
    if os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "فريق رحال فريق تطوعي شبابي أردني مقره عمان، هدفه تمكين الشباب من خلال المبادرات والتدريب وخرائط رحال."

def save_knowledge(text):
    with open(KNOWLEDGE_FILE, "a", encoding="utf-8") as f:
        f.write("\n" + text)
    print(f"Saved knowledge: {text}")

SYSTEM_PROMPT = "انت مساعد فريق رحال الأردني. احكي لهجة أردنية بسيطة وودودة ومختصرة."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً! أنا بوت رحال @Rahalteam2_bot 🚀\nبتقدر تعلمني بالحكي العادي، قول: احفظ انه... \nوأنا بحفظ فوراً!")

async def learn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and str(update.effective_user.id) != str(ADMIN_ID):
        await update.message.reply_text("هذا الأمر للأدمن فقط 🔒")
        return
    if not context.args:
        await update.message.reply_text("استخدم: /learn المعلومة")
        return
    info = " ".join(context.args)
    save_knowledge(info)
    await update.message.reply_text(f"✅ تم الحفظ: {info}")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = str(update.effective_user.id)
    print(f"Message from {user_id}: {user_text}")

    # --- ميزة التعليم بالحكي العادي (للأدمن فقط) ---
    if ADMIN_ID and user_id == str(ADMIN_ID):
        learn_keywords = ["احفظ", "تذكر", "تعلم ان", "تعلم أن", "خزن", "احفظي"]
        if any(word in user_text for word in learn_keywords):
            # نظف كلمة احفظ من النص واحفظ الباقي
            clean_text = user_text
            for word in learn_keywords:
                clean_text = clean_text.replace(word, "").strip()
            if clean_text:
                save_knowledge(clean_text)
                await update.message.reply_text(f"✅ تمام حفظت: {clean_text}\nرح أتذكرها بعد هيك!")
                return

    # --- الرد العادي ---
    knowledge = load_knowledge()
    full_prompt = f"{SYSTEM_PROMPT}\n\nمعلومات عن الفريق:\n{knowledge}\n\nسؤال المستخدم: {user_text}\n\nجاوب بلهجة أردنية ودية:"

    for model_name in AVAILABLE_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(full_prompt)
            if response.text:
                await update.message.reply_text(response.text)
                return
        except Exception as e:
            print(f"Gemini Error with {model_name}: {e}")
            continue
    
    await update.message.reply_text("صار ضغط شوي، جرب بعد دقيقة 🙏")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("learn", learn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Bot @Rahalteam2_bot is RUNNING with Auto-Learn...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
