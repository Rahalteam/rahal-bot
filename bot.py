
import os, json
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # حط ايدي تليجرامك هنا في Secrets
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
    print(f"Saved: {q} -> {a}")

GREETINGS = ["صباح الخير","صباح النور","مساء الخير","السلام عليكم","هلا","مرحبا","اهلا","السلام","صباح","مساء"]

def is_greeting(text):
    t = text.strip().lower()
    return any(g in t for g in GREETINGS) and len(t) < 20

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if ADMIN_ID != 0 and uid == ADMIN_ID:
        await update.message.reply_text(
            f"هلا يا شادي! 👑 انت الادمن (ID: {uid})\n"
            "هنا تتكلم معي بحرية وتعطيني معلومات.\n\n"
            "طريقة التعليم:\n"
            "اكتب: السؤال | الجواب\n"
            "مثال:\n"
            "كيف اثبت الخريطة | ادخل RahalTeam.com وحمل الملف وفك الضغط\n\n"
            "أو تكلم معي عادي وراح اتعلم منك."
        )
    else:
        await update.message.reply_text(
            "هلا والله حياك في خرائط رحال 🗺️\n"
            "أقدر أساعدك في التثبيت والخرائط. وش ودك تعرف؟"
        )

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"الايدي حقك: {update.effective_user.id}\nارسله لي احطه في ADMIN_ID")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID !=0 and update.effective_user.id != ADMIN_ID:
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
    is_admin = (ADMIN_ID != 0 and user_id == ADMIN_ID) or ADMIN_ID == 0  # لو ما حطيت ADMIN_ID يعتبر الكل ادمن مؤقتا

    # ====== وضع الادمن (انت) تتكلم بحرية ======
    if is_admin:
        # لو كتب بصيغة تعليم: سؤال | جواب
        if "|" in text and len(text.split("|")) == 2:
            q, a = text.split("|", 1)
            if len(q.strip()) > 2 and len(a.strip()) > 2:
                save_knowledge(q, a)
                await update.message.reply_text(f"تم الحفظ ✅\nس: {q.strip()}\nج: {a.strip()}\n\nالزباين الحين بيستفيدون منه")
                return
        
        # لو كتب احفظ: ...
        if text.startswith("احفظ") or text.startswith("علم"):
            # نحاول نستخرج بعد الكلمة
            cleaned = text.replace("احفظ", "").replace("علم", "").replace(":", "").strip()
            if "|" in cleaned:
                q, a = cleaned.split("|", 1)
                save_knowledge(q, a)
                await update.message.reply_text(f"تم الحفظ ✅\nس: {q.strip()}")
                return

        # كلام حر مع الادمن - نموذج ذكي يتكلم بحرية
        if GROQ_KEY:
            try:
                from groq import Groq
                client = Groq(api_key=GROQ_KEY)
                # محادثة حرة بدون قيود رحال
                completion = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": "أنت مساعد ذكي حر تابع لشادي. تكلم بحرية وذكاء وبلهجة سعودية ودودة. انت تتعلم من شادي عشان بعدين تجاوب الزباين. اذا اعطاك معلومة احفظها في ذاكرتك."},
                        {"role": "user", "content": text}
                    ],
                    max_tokens=600,
                    temperature=0.8
                )
                reply = completion.choices[0].message.content
                await update.message.reply_text(reply)
                return
            except Exception as e:
                print(e)

    # ====== وضع الزبون العادي ======
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
                model="llama-3.1-8b-instant",  # 14,400 رسالة
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "أنت مساعد خرائط رحال الرسمي. اسمك رحال. لهجتك سعودية ودودة. "
                            "لا تقل بخصوص. لا ترسل رابط اليوتيوب الا اذا سأل عن التثبيت. "
                            "موقعك RahalTeam.com وشرح التثبيت https://youtu.be/8TEil-9tsfY "
                            "جاوب باختصار 2-4 اسطر. استخدم المعلومات المحفوظة التالية:\n"
                            f"{context_text}"
                        )
                    },
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
    print("Rahal Bot - Admin Free Mode + 14,400 msgs")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
