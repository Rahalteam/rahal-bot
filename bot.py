
import os, json
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")

# FIX: يدعم ايدي واحد او اكثر مفصول بفاصلة
admin_raw = os.getenv("ADMIN_ID", "0")
ADMIN_IDS = []
for part in admin_raw.replace(",", " ").split():
    part=part.strip()
    if part.isdigit():
        try:
            ADMIN_IDS.append(int(part))
        except:
            pass
if not ADMIN_IDS:
    ADMIN_IDS = [0]

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

def save_knowledge(q, a):
    data = load_knowledge()
    data.append({"q": q.strip(), "a": a.strip(), "time": datetime.now(AMMAN_TZ).isoformat()})
    if len(data) > 500:
        data = data[-500:]
    with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

GREETINGS = ["صباح الخير","صباح النور","مساء الخير","السلام عليكم","هلا","مرحبا","اهلا","السلام","صباح","مساء"]

def is_greeting(text):
    t = text.strip().lower()
    return any(g in t for g in GREETINGS) and len(t) < 20

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in ADMIN_IDS:
        await update.message.reply_text(
            f"هلا يا شادي! 👑 انت الادمن (ID: {uid})\n"
            "هنا تتكلم معي بحرية وتعطيني معلومات.\n\n"
            "طريقة التعليم:\n"
            "اكتب: السؤال | الجواب\n"
            "مثال: كيف اثبت الخريطة | ادخل RahalTeam.com\n\n"
            "الايديهات المسموحة: " + str(ADMIN_IDS)
        )
    else:
        await update.message.reply_text("هلا والله حياك في خرائط رحال 🗺️\nوش ودك تعرف؟")

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"الايدي حقك: {update.effective_user.id}")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS and 0 not in ADMIN_IDS:
        return
    data = load_knowledge()[-20:]
    if not data:
        await update.message.reply_text("ما في شي محفوظ لسه")
        return
    txt = "\n\n".join([f"{i+1}. س: {x['q']}\nج: {x['a']}" for i,x in enumerate(data)])
    await update.message.reply_text(f"آخر ما تعلمته:\n{txt}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if not text or text.startswith("/"):
        return
    
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS or 0 in ADMIN_IDS

    # وضع الادمن
    if is_admin:
        if "|" in text and len(text.split("|")) == 2:
            q, a = text.split("|", 1)
            if len(q.strip()) > 2 and len(a.strip()) > 2:
                save_knowledge(q, a)
                await update.message.reply_text(f"تم الحفظ ✅\nس: {q.strip()}\nج: {a.strip()}")
                return
        if GROQ_KEY:
            try:
                from groq import Groq
                client = Groq(api_key=GROQ_KEY)
                completion = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": "أنت مساعد ذكي حر تابع لشادي. تكلم بحرية وذكاء وبلهجة سعودية ودودة."},
                        {"role": "user", "content": text}
                    ],
                    max_tokens=600,
                    temperature=0.8
                )
                await update.message.reply_text(completion.choices[0].message.content)
                return
            except Exception as e:
                print(e)

    if is_greeting(text):
        await update.message.reply_text(f"{text} هلا والله صباح النور 🌹 حياك في خرائط رحال، آمرني؟")
        return

    learned = load_knowledge()[-15:]
    context_text = "\n".join([f"س: {x.get('q','')} ج: {x.get('a','')}" for x in learned])

    reply_text = ""
    if GROQ_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_KEY)
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": f"أنت مساعد خرائط رحال الرسمي. اسمك رحال. لهجتك سعودية ودودة. موقعك RahalTeam.com وشرح التثبيت https://youtu.be/8TEil-9tsfY جاوب باختصار 2-4 اسطر. معلومات محفوظة:\n{context_text}"},
                    {"role": "user", "content": text}
                ],
                max_tokens=400,
                temperature=0.6
            )
            reply_text = completion.choices[0].message.content
        except Exception as e:
            print(e)
            reply_text = "هلا والله، وش حاب تعرف عن خرائط رحال؟"
    else:
        reply_text = "هلا والله حياك في خرائط رحال 🗺️"

    await update.message.reply_text(reply_text)

def main():
    print(f"Rahal Bot Ready - Admins: {ADMIN_IDS} - 14,400/day")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
