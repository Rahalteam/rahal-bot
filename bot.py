import os, json, re, random
from flask import Flask
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
try:
    from openai import OpenAI
    HAS_OPENAI = True
except:
    HAS_OPENAI = False

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Rahal Creative AI Bot"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
ADMIN_ID_RAW = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")
ADMIN_IDS = [s.strip() for s in ADMIN_ID_RAW.replace(" ", "").split(",") if s.strip()]
GROQ_KEY = os.getenv("GROQ_API_KEY","").strip()
AI_PROVIDER = os.getenv("AI_PROVIDER","groq").lower()

def get_ai_client():
    if not HAS_OPENAI or not GROQ_KEY: return None, None
    if AI_PROVIDER == "groq":
        return OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1"), "llama-3.3-70b-versatile"
    return None, None

KNOWLEDGE_FILE = "knowledge.txt"
STATUS_FILE = "bot_status.json"

def load_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f: return json.load(f).get("paused", False)
        except: return False
    return False
def save_status(p):
    with open(STATUS_FILE, "w", encoding="utf-8") as f: json.dump({"paused": p}, f)
BOT_PAUSED = load_status()

def load_file_knowledge():
    if os.path.exists(KNOWLEDGE_FILE):
        try: return open(KNOWLEDGE_FILE, "r", encoding="utf-8").read()
        except: return ""
    return ""
def save_knowledge(t):
    with open(KNOWLEDGE_FILE, "a", encoding="utf-8") as f: f.write("\n" + t + "\n---\n")

DEFAULT_FACTS = """
متجر خرائط رحال: www.RahalTeam.com
شرح فيديو الشراء والتثبيت: https://youtu.be/8TEil-9tsfY
رابط المتجر للأندرويد والأيفون وهواوي وشاشات السيارات: https://RahalTeam.com
طريقة الشراء: ادخل الموقع اختر الخريطة اضف للسلة ادفع (مدى - فيزا - تحويل) يوصلك كود
تثبيت الايفون: بعد الشراء يجيك رابط افتحه في OsmAnd
تثبيت الاندرويد: حمل الملف من نفس الرابط وافتحه في OsmAnd
"""

def get_relevant_facts(query):
    q = query.lower()
    file_k = load_file_knowledge()
    all_text = DEFAULT_FACTS + "\n" + file_k
    chunks = [c.strip() for c in all_text.split("---") if c.strip()]
    # ابحث عن الاكثر صلة
    scored=[]
    for ch in chunks:
        cl=ch.lower()
        score=0
        if "ايفون" in q and "ايفون" in cl: score+=10
        if "تثبيت" in q and "تثبيت" in cl: score+=8
        if "شراء" in q and "شراء" in cl: score+=8
        if "خريطة" in q and "خريطة" in cl: score+=5
        if "http" in cl or "www" in cl: score+=2
        for w in re.findall(r'\w+', q):
            if len(w)>2 and w in cl: score+=1
        scored.append((score,ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    # خذ اعلى 2
    best = [c for s,c in scored if s>0][:2]
    return "\n".join(best) if best else DEFAULT_FACTS

def ask_creative_ai(user_text, facts):
    client, model = get_ai_client()
    if not client: return None
    try:
        system = f"""انت بوت خرائط رحال، سعودي، ذكي، مبدع، لهجتك عامية ودودة، لا تكرر نفس الجملة ابدا، كل مرة صيغ جواب مختلف.

مهم:
- استخدم الحقائق التالية كمرجع لكن لا تنسخها حرفيا، اعد صياغتها بابداع مع الحفاظ على الروابط كما هي حرفيا
- الروابط لازم تبقى نفسها: www.RahalTeam.com و https://youtu.be/8TEil-9tsfY و https://RahalTeam.com
- اذا المستخدم قال سلام او مرحبا او صباح الخير، رد بتحية مختلفة ومبدعة كل مرة
- اذا سأل عن التثبيت او الشراء، اشرح بطريقتك المبدعة مع ذكر الروابط
- لا تقل "تفضل كيف اقدر اساعدك" كل مرة، نوع

الحقائق:
{facts}
"""
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_text}
            ],
            temperature=0.85,  # ابداع عالي
            max_tokens=600,
            top_p=0.9
        )
        return resp.choices[0].message.content
    except Exception as e:
        print(f"AI Error: {e}")
        return None

async def post_init(application: Application):
    try: await application.bot.delete_webhook(drop_pending_updates=True)
    except: pass

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client,_ = get_ai_client()
    ai = "ذكاء مبدع شغال ✅" if client else "ذكاء مطفي"
    status = "موقف ⏸️" if BOT_PAUSED else "شغال ✅"
    await update.message.reply_text(f"رحال المبدع {status} - {ai}\n/on /off /memory /save", reply_to_message_id=update.message.message_id)

async def on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED=False; save_status(False)
    await update.message.reply_text("اشتغلت ✅ المبدع شغال", reply_to_message_id=update.message.message_id)

async def off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED=True; save_status(True)
    await update.message.reply_text("وقفت ⏸️", reply_to_message_id=update.message.message_id)

async def memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    await update.message.reply_text(load_file_knowledge()[:3500] or "لا يوجد اضافي", reply_to_message_id=update.message.message_id)

async def save_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("استخدم: /save النص", reply_to_message_id=update.message.message_id)
        return
    save_knowledge(text)
    await update.message.reply_text(f"✅ حفظت، والذكاء بيبدع فيه:\n{text[:1000]}", reply_to_message_id=update.message.message_id)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if update.effective_user.is_bot: return
    user_text = update.message.text or ""
    uid = str(update.effective_user.id)
    chat_type = update.effective_chat.type

    if chat_type == "private" and uid in ADMIN_IDS:
        low=user_text.lower()
        if low in ["مسح","امسح"]:
            open(KNOWLEDGE_FILE, "w", encoding="utf-8").close()
            await update.message.reply_text("✅ مسحت", reply_to_message_id=update.message.message_id)
            return
        if user_text.startswith("احفظ") or low.startswith("احفظ"):
            clean=user_text.replace("احفظ","").strip(" :")
            if len(clean)>2:
                save_knowledge(clean)
                await update.message.reply_text(f"✅ حفظت:\n{clean[:1200]}", reply_to_message_id=update.message.message_id)
            return
    else:
        if BOT_PAUSED: return

    if any(k in user_text.lower() for k in ["طلبي","رقم الطلب"]):
        for aid in ADMIN_IDS:
            try: await context.bot.send_message(chat_id=int(aid), text=f"📦 {user_text} من {update.effective_user.first_name}")
            except: pass
        await update.message.reply_text("حولت سؤالك للأدمن 📦", reply_to_message_id=update.message.message_id)
        return

    facts = get_relevant_facts(user_text)
    # الذكاء المبدع يصيغ الجواب بطريقة مختلفة كل مرة
    creative = ask_creative_ai(user_text, facts)
    if creative:
        await update.message.reply_text(creative, reply_to_message_id=update.message.message_id)
        return
    # fallback لو الذكاء فاصل
    await update.message.reply_text(facts[:1500], reply_to_message_id=update.message.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("on", on_cmd))
    app.add_handler(CommandHandler("off", off_cmd))
    app.add_handler(CommandHandler("memory", memory_cmd))
    app.add_handler(CommandHandler("save", save_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Rahal Creative Bot Ready")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
