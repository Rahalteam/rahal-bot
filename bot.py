import os
from flask import Flask
import threading
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 1. حل مشكلة No open ports في Render المجاني ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "Rahal Bot is Live @rahalai_bot - OK"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()
# ----------------------------------------------------

# --- 2. قراءة المتغيرات مع تنظيف ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip().strip('"').strip("'")
ADMIN_ID = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")

print(f"--- Checking ENV ---")
print(f"Token exists? {bool(TELEGRAM_TOKEN)} Length: {len(TELEGRAM_TOKEN)}")
print(f"Gemini exists? {bool(GEMINI_API_KEY)}")
print(f"Admin ID: {ADMIN_ID}")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN فاضي! روح Render > Environment وحطه بدون علامات تنصيص")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY فاضي!")

# --- 3. اعداد Gemini ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

KNOWLEDGE_FILE = "knowledge.txt"

def load_knowledge():
    if os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "فريق رحال هو فريق تطوعي شبابي أردني مقره عمان، هدفه تمكين الشباب."

def save_knowledge(text):
    with open(KNOWLEDGE_FILE, "a", encoding="utf-8") as f:
        f.write("\n" + text)

SYSTEM_PROMPT = "انت مساعد فريق رحال الأردني. احكي لهجة أردنية بسيطة وودودة ومختصرة ومفيدة."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً! أنا بوت رحال @rahalai_bot 🚀\nجاهز أساعدك، اسألني أي شي.")

async def learn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and str(update.effective_user.id) != str(ADMIN_ID):
        await update.message.reply_text("هذا الأمر للأدمن فقط 🔒")
        return
    if not context.args:
        await update.message.reply_text("استخدم:\n/learn المعلومة\nمثال: /learn رحال تأسس 2020 في عمان")
        return
    info = " ".join(context.args)
    save_knowledge(info)
    await update.message.reply_text(f"✅ تم الحفظ: {info}")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    knowledge = load_knowledge()
    full_prompt = f"{SYSTEM_PROMPT}\n\nمعلومات عن الفريق:\n{knowledge}\n\nسؤال المستخدم: {user_text}\nجاوب بشكل مفيد:"
    try:
        response = model.generate_content(full_prompt)
        await update.message.reply_text(response.text)
    except Exception as e:
        print(f"Gemini Error: {e}")
        await update.message.reply_text("صار ضغط شوي، جرب مرة ثانية بعد دقيقة.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("learn", learn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Bot @rahalai_bot is RUNNING and polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
