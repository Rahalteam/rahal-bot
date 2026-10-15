import os, threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Rahal Working Now"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
ADMIN_ID_RAW = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")
ADMIN_IDS = [s.strip() for s in ADMIN_ID_RAW.replace(" ", "").split(",") if s.strip()]
GROQ_KEY = os.getenv("GROQ_API_KEY","").strip()

client = OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_KEY else None

# موديلات Groq الجديدة الشغالة حاليا - يونيو 2026 - مجربة
CURRENT_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "groq/compound-mini",
    "llama-3.1-8b-instant",
]

KNOWLEDGE_FILE = "knowledge.txt"

def load_knowledge():
    base = """متجر خرائط رحال: www.RahalTeam.com
فيديو الشرح: https://youtu.be/8TEil-9tsfY
الرابط العام: https://RahalTeam.com
الشراء: ادخل الموقع اختر خريطتك اضف للسلة ادفع مدى/فيزا يجيك الكود
الايفون: افتح الرابط في OsmAnd بعد الشراء
الاندرويد وشاشات السيارات: حمل الملف وافتحه في OsmAnd"""
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

def ask_groq(user_q):
    if not client:
        return "❌ مفتاح GROQ_API_KEY مو موجود في Render"
    facts = load_knowledge()
    for model in CURRENT_MODELS:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role":"system","content": f"""انت بوت خرائط رحال، سعودي ذكي ومبدع، رد بلهجة عامية ودودة ومختصرة.

معلومات المتجر (استخدمها عند الحاجة وحافظ على الروابط حرفيا):
{facts}

الروابط: www.RahalTeam.com - https://youtu.be/8TEil-9tsfY - https://RahalTeam.com"""},
                    {"role":"user","content": user_q}
                ],
                temperature=0.8,
                max_tokens=600
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"Model {model} error: {e}")
            last = str(e)
            continue
    return f"عذرا، كل الموديلات فشلت. اخر خطأ: {last[:400]}"

async def post_init(app: Application):
    try: await app.bot.delete_webhook(drop_pending_updates=True)
    except: pass

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ رحال شغال الآن - قل السلام عليكم وجرب", reply_to_message_id=update.message.message_id)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.is_bot: return
    text = update.message.text or ""
    uid = str(update.effective_user.id)
    if update.effective_chat.type == "private" and uid in ADMIN_IDS:
        if text.lower().strip() in ["مسح","امسح"]:
            open(KNOWLEDGE_FILE,"w",encoding="utf-8").close()
            await update.message.reply_text("✅ مسحت", reply_to_message_id=update.message.message_id)
            return
        if text.startswith("احفظ"):
            clean = text.replace("احفظ","").strip(" :")
            if len(clean)>2:
                save_knowledge(clean)
                await update.message.reply_text(f"✅ حفظت: {clean[:800]}", reply_to_message_id=update.message.message_id)
            return
    ans = ask_groq(text)
    await update.message.reply_text(ans, reply_to_message_id=update.message.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Rahal Working Bot Ready")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
