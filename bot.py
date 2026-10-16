import os
import json
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")

AMMAN_TZ = pytz.timezone("Asia/Amman")
KNOWLEDGE_FILE = "knowledge/learned.json"

os.makedirs("knowledge", exist_ok=True)
if not os.path.exists(KNOWLEDGE_FILE):
    with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False)

def load_knowledge():
    try:
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في خرائط رحال 🗺️\n"
        "www.RahalTeam.com\n"
        "شاهد الشرح: https://youtu.be/8TEil-9tsfY"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    
    learned = load_knowledge()[-20:]
    context_text = "\n".join([f"س: {x.get('q','')} ج: {x.get('a','')}" for x in learned])

    reply_text = ""
    
    if GROQ_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_KEY)
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",  # 14,400 رسالة باليوم مجانا
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "انت بوت خرائط رحال. لهجتك سعودية ودودة. "
                            "موقعك www.RahalTeam.com وفيديو الشرح https://youtu.be/8TEil-9tsfY . "
                            f"معلومات سابقة:\n{context_text}"
                        )
                    },
                    {"role": "user", "content": text}
                ],
                max_tokens=600,
                temperature=0.7
            )
            reply_text = completion.choices[0].message.content
        except Exception as e:
            print(f"Groq error: {e}")
            reply_text = f"www.RahalTeam.com\nhttps://youtu.be/8TEil-9tsfY\n\nبخصوص: {text}"
    else:
        reply_text = f"www.RahalTeam.com\nhttps://youtu.be/8TEil-9tsfY\n\nبخصوص: {text}"

    await update.message.reply_text(reply_text)

def main():
    print("Rahal Bot Ready - Model: llama-3.1-8b-instant (14,400 msg/day) ✅")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
