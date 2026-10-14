import os
from flask import Flask
import threading
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 1. حل مشكلة Render (يبقي الموقع شغال) ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "Rahal Bot is Live @Rahalteam2_bot - OK - Using gemini-2.5-flash"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# --- 2. قراءة المتغيرات وتنظيفها ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip().strip('"').strip("'")
ADMIN_ID = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")

print(f"--- ENV CHECK --- Token: {bool(TELEGRAM_TOKEN)} | Gemini: {bool(GEMINI_API_KEY)} | Admin: {ADMIN_ID}")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise ValueError("تأكد من TELEGRAM_TOKEN و GEMINI_API_KEY في Render Environment")

# --- 3. اعداد Gemini بالموديلات الجديدة 2026 ---
genai.configure(api_key=GEMINI_API_KEY)

# الموديلات المتاحة حاليا - جوجل وقفت 2.0-flash يوم 2026-06-01
# المستقر حاليا هو 2.5-flash
AVAILABLE_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-2.5-flash-lite"]

KNOWLEDGE_FILE = "knowledge.txt"

def load_knowledge():
    if os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "فريق رحال فريق تطوعي شبابي أردني مقره عمان، هدفه تمكين الشباب من خلال المبادرات والتدريب والرحلات التطوعية وخرائط رحال."

def save_knowledge(text):
    with open(KNOWLEDGE_FILE, "a", encoding="utf-8") as f:
        f.write("\n" + text)

SYSTEM_PROMPT = "انت مساعد فريق رحال الأردني. احكي لهجة أردنية بسيطة وودودة ومختصرة ومفيدة. اذا حدا سأل عن خرائط رحال، احكي عن مبادرة الخرائط التفاعلية للشباب."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً! أنا بوت رحال @Rahalteam2_bot 🚀\nجاهز أساعدك عن فريق رحال وخرائط رحال، اسألني أي شي.")

async def learn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and str(update.effective_user.id) != str(ADMIN_ID):
        await update.message.reply_text("هذا الأمر للأدمن فقط 🔒")
        return
    if not context.args:
        await update.message.reply_text("استخدم: /learn المعلومة الجديدة")
        return
    info = " ".join(context.args)
    save_knowledge(info)
    await update.message.reply_text(f"✅ تم الحفظ: {info}")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    knowledge = load_knowledge()
    full_prompt = f"{SYSTEM_PROMPT}\n\nمعلومات عن الفريق:\n{knowledge}\n\nسؤال المستخدم: {user_text}\n\nجاوب بلهجة أردنية:"

    # جرب الموديلات واحد واحد لحد ما يزبط واحد
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
    
    await update.message.reply_text("صار ضغط شوي على الذكاء الاصطناعي، جرب بعد دقيقة 🙏")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("learn", learn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Bot @Rahalteam2_bot is RUNNING with gemini-2.5-flash...")
    # drop_pending_updates عشان يحل مشكلة Conflict
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
