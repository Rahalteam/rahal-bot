import os, json, threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Rahal Smart Final Bot"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
ADMIN_ID_RAW = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")
ADMIN_IDS = [s.strip() for s in ADMIN_ID_RAW.replace(" ", "").split(",") if s.strip()]
GROQ_KEY = os.getenv("GROQ_API_KEY","").strip()

client = OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_KEY else None
MODEL = "llama-3.3-70b-versatile"

KNOWLEDGE_FILE = "knowledge.txt"

def load_knowledge():
    base = """متجرك www.RahalTeam.com - شرح الفيديو https://youtu.be/8TEil-9tsfY - الرابط العام https://RahalTeam.com
الشراء: ادخل الموقع اختر خريطتك اضف للسلة ادفع مدى/فيزا يجيك الكود
الايفون: بعد الشراء افتح الرابط في OsmAnd
الاندرويد وهواوي وشاشات السيارات: حمل الملف وافتحه في OsmAnd"""
    if os.path.exists(KNOWLEDGE_FILE):
        try:
            extra = open(KNOWLEDGE_FILE,"r",encoding="utf-8").read()
            return base + "\n" + extra
        except:
            return base
    return base

def save_knowledge(t):
    with open(KNOWLEDGE_FILE,"a",encoding="utf-8") as f:
        f.write("\n"+t+"\n---\n")

def ask_ai(user_q):
    if not client:
        return "المفتاح مو شغال، تأكد من GROQ_API_KEY في Render"
    facts = load_knowledge()
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role":"system","content": f"""انت مساعد خرائط رحال، سعودي، ذكي جداً، مبدع، تتكلم عامية بيضاء مفهومة.

قواعد:
1- جاوب على أي سؤال يسأله العميل، حتى لو مو عن الخرائط - انت ذكاء عام
2- اذا السؤال عن الخرائط استخدم هذه المعلومات لكن صغها بابداعك ولا تنسخها حرفيا، وحافظ على الروابط كما هي:
{facts}
3- لا تكرر نفس الجملة ابدا، كل مرة ابدع بصياغة جديدة
4- خلك ودود ومختصر ومفيد
5- الروابط لازم تذكرها كاملة: www.RahalTeam.com و https://youtu.be/8TEil-9tsfY و https://RahalTeam.com"""},
                {"role":"user","content": user_q}
            ],
            temperature=0.9,
            max_tokens=700
        )
        return resp.choices[0].message.content
    except Exception as e:
        print(f"Groq Error: {e}")
        return f"صار خطأ في الذكاء: {e}\n\nالمعلومات الاساسية:\n{facts[:1000]}"

async def post_init(app: Application):
    try: await app.bot.delete_webhook(drop_pending_updates=True)
    except: pass

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("رحال الذكي شغال ✅\nجرب اسألني أي شي\n/on /off /memory", reply_to_message_id=update.message.message_id)

async def on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    await update.message.reply_text("شغال ✅", reply_to_message_id=update.message.message_id)

async def memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    txt = load_knowledge()
    await update.message.reply_text(txt[:3500], reply_to_message_id=update.message.message_id)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.is_bot: return
    text = update.message.text or ""
    uid = str(update.effective_user.id)
    chat_type = update.effective_chat.type

    # تعليم من الخاص فقط
    if chat_type == "private" and uid in ADMIN_IDS:
        low = text.lower().strip()
        if low in ["مسح","امسح"]:
            open(KNOWLEDGE_FILE,"w",encoding="utf-8").close()
            await update.message.reply_text("✅ مسحت كل التعليم", reply_to_message_id=update.message.message_id)
            return
        if text.startswith("احفظ"):
            clean = text.replace("احفظ","").strip(" :")
            if len(clean)>2:
                save_knowledge(clean)
                await update.message.reply_text(f"✅ حفظت وبتعلمه بابداع:\n{clean[:1000]}", reply_to_message_id=update.message.message_id)
            return

    # كل الرسائل تمر على الذكاء المبدع
    answer = ask_ai(text)
    await update.message.reply_text(answer, reply_to_message_id=update.message.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("on", on_cmd))
    app.add_handler(CommandHandler("memory", memory_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Rahal Smart Final Ready")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
