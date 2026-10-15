import os, json, threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Rahal Smart Fixed V2"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
ADMIN_ID_RAW = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")
ADMIN_IDS = [s.strip() for s in ADMIN_ID_RAW.replace(" ", "").split(",") if s.strip()]
GROQ_KEY = os.getenv("GROQ_API_KEY","").strip()

client = OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_KEY else None

MODELS_TO_TRY = [
    "llama-3.1-8b-instant",
    "llama3-8b-8192", 
    "mixtral-8x7b-32768",
    "gemma2-9b-it"
]

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

def ask_ai_smart(user_q):
    if not client:
        return "المفتاح مو موجود في Render، تأكد من GROQ_API_KEY"
    facts = load_knowledge()
    last_error = ""
    for model_name in MODELS_TO_TRY:
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role":"system","content": f"""انت مساعد خرائط رحال الذكي، سعودي، مبدع، لهجتك عامية ودودة.
مهمتك: جاوب على أي سؤال بابداع، لا تكرر نفس الجملة.
معلومات متجرك (استخدمها لو سأل عن الخرائط، وحافظ على الروابط كما هي):
{facts}
قواعد:
- الروابط تبقى نفسها حرفيا: www.RahalTeam.com و https://youtu.be/8TEil-9tsfY و https://RahalTeam.com
- اذا قال مساء الخير/صباح الخير/مرحبا، رد بابداع كل مرة
- جاوب على اي سؤال حتى لو مو عن الخرائط"""},
                    {"role":"user","content": user_q}
                ],
                temperature=0.9,
                max_tokens=700
            )
            return resp.choices[0].message.content
        except Exception as e:
            last_error = str(e)
            print(f"Model {model_name} failed: {e}")
            continue
    return f"كل الموديلات فشلت. اخر خطأ: {last_error[:500]}"

async def post_init(app: Application):
    try: await app.bot.delete_webhook(drop_pending_updates=True)
    except: pass

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("رحال الذكي المبدع شغال ✅\nقل مساء الخير", reply_to_message_id=update.message.message_id)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.is_bot: return
    text = update.message.text or ""
    uid = str(update.effective_user.id)
    chat_type = update.effective_chat.type
    if chat_type == "private" and uid in ADMIN_IDS:
        low = text.lower().strip()
        if low in ["مسح","امسح"]:
            open(KNOWLEDGE_FILE,"w",encoding="utf-8").close()
            await update.message.reply_text("✅ مسحت", reply_to_message_id=update.message.message_id)
            return
        if text.startswith("احفظ"):
            clean = text.replace("احفظ","").strip(" :")
            if len(clean)>2:
                save_knowledge(clean)
                await update.message.reply_text(f"✅ حفظت:\n{clean[:1000]}", reply_to_message_id=update.message.message_id)
            return
    answer = ask_ai_smart(text)
    await update.message.reply_text(answer, reply_to_message_id=update.message.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Rahal Smart Fixed Ready")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
