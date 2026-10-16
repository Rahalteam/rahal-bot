import os, json, re
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
AMMAN_TZ = pytz.timezone("Asia/Amman")
KNOWLEDGE_FILE = "knowledge/learned.json"

# نفس كود البوت اللي كان شغال عندك
os.makedirs("knowledge", exist_ok=True)
if not os.path.exists(KNOWLEDGE_FILE):
    with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

def load_knowledge():
    try:
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def save_knowledge(q, a):
    data = load_knowledge()
    data.append({"q": q, "a": a, "time": datetime.now(AMMAN_TZ).isoformat()})
    with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً! أنا بوت خرائط رحال 🗺️\nwww.RahalTeam.com")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text: return

    # اذا رسالة في قروب التدريب احفظها
    if "تدريب" in (update.effective_chat.title or "").lower() or update.effective_chat.type == "private":
        # هنا تتعلم
        pass

    # رد ثابت + ذكاء Groq لو موجود
    reply = f"www.RahalTeam.com\nhttps://youtu.be/8TEil-9tsfY\n\n"
    try:
        if GROQ_KEY:
            from groq import Groq
            client = Groq(api_key=GROQ_KEY)
            learned = load_knowledge()[-20:]
            context_text = "\n".join([f"Q:{x['q']} A:{x['a']}" for x in learned])
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": f"انت بوت خرائط رحال. معلوماتك: {context_text}. موقعك RahalTeam.com وفيديو https://youtu.be/8TEil-9tsfY"},
                    {"role": "user", "content": text}
                ],
                max_tokens=500
            )
            reply = completion.choices[0].message.content
        else:
            reply += f"سؤالك: {text}"
    except Exception as e:
        reply += f"سؤالك: {text}"

    await update.message.reply_text(reply)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Rahal Bot Ready on Fly.io ✅")
    app.run_polling()

if __name__ == "__main__":
    main()
