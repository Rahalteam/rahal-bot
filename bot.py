import os
from flask import Flask
import threading
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- حل مشكلة No open ports في Render المجاني ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Rahal Bot is Live @rahalai_bot"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()
# ---------------------------------------------

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID") # اللي حطيته في Render

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

KNOWLEDGE_FILE = "knowledge.txt"

def load_knowledge():
    if os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "فريق رحال فريق تطوعي أردني."

def save_knowledge(text):
    with open(KNOWLEDGE_FILE, "a", encoding="utf-8") as f:
        f.write("\n" + text)

SYSTEM_PROMPT = "انت مساعد فريق رحال الأردني. احكي لهجة أردنية بسيطة، ودودة ومختصرة."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً! أنا بوت رحال @rahalai_bot 🚀\nاسألني أي شي عن الفريق.")

async def learn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # حماية - انت بس بتقدر تعلمه
    if ADMIN_ID and str(update.effective_user.id) != str(ADMIN_ID):
        await update.message.reply_text("هذا الأمر للأدمن فقط 🔒")
        return
    if not context.args:
        await update.message.reply_text("استخدم: /learn المعلومة الجديدة\nمثال: /learn رحال تأسس سنة 2020")
        return
    info = " ".join(context.args)
    save_knowledge(info)
    await update.message.reply_text(f"✅ تم الحفظ: {info}")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    knowledge = load_knowledge()
    full_prompt = f"{SYSTEM_PROMPT}\n\nمعلومات عن رحال:\n{knowledge}\n\nسؤال: {user_text}"
    try:
        response = model.generate_content(full_prompt)
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text("صار عندي ضغط شوي، جرب مرة ثانية.")

def main():
    bot_app = Application.builder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("learn", learn))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Bot @rahalai_bot is running...")
    bot_app.run_polling()

if __name__ == "__main__":
    main()
