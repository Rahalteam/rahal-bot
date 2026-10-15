import os, json, re, random
from flask import Flask
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# نحاول نستورد openai - لو مو موجود يشتغل بدون ذكاء
try:
    from openai import OpenAI
    HAS_OPENAI = True
except:
    HAS_OPENAI = False

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Rahal Cheap AI Bot"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
ADMIN_ID_RAW = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")
ADMIN_IDS = [s.strip() for s in ADMIN_ID_RAW.replace(" ", "").split(",") if s.strip()]

# اختار مزود الذكاء من المتغيرات - Groq مجاني افتراضي
AI_PROVIDER = os.getenv("AI_PROVIDER","groq").lower() # groq, deepseek, openai, openrouter
GROQ_KEY = os.getenv("GROQ_API_KEY","").strip()
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY","").strip()
OPENAI_KEY = os.getenv("OPENAI_API_KEY","").strip()
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY","").strip()

def get_ai_client():
    if not HAS_OPENAI: return None, None
    if AI_PROVIDER == "groq" and GROQ_KEY:
        return OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1"), "llama-3.3-70b-versatile"
    if AI_PROVIDER == "deepseek" and DEEPSEEK_KEY:
        return OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com"), "deepseek-chat"
    if AI_PROVIDER == "openai" and OPENAI_KEY:
        return OpenAI(api_key=OPENAI_KEY), "gpt-4o-mini"
    if AI_PROVIDER == "openrouter" and OPENROUTER_KEY:
        return OpenAI(api_key=OPENROUTER_KEY, base_url="https://openrouter.ai/api/v1"), "deepseek/deepseek-chat"
    # محاولة تلقائية - يشوف اي مفتاح موجود
    if GROQ_KEY:
        return OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1"), "llama-3.3-70b-versatile"
    if DEEPSEEK_KEY:
        return OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com"), "deepseek-chat"
    if OPENAI_KEY:
        return OpenAI(api_key=OPENAI_KEY), "gpt-4o-mini"
    if OPENROUTER_KEY:
        return OpenAI(api_key=OPENROUTER_KEY, base_url="https://openrouter.ai/api/v1"), "deepseek/deepseek-chat"
    return None, None

KNOWLEDGE_BASE = {
    "ايفون": """📱 شرح التثبيت للايفون:

1- الشراء من الموقع الالكتروني 👇
www.RahalTeam.com

2- شرح فيديو 👇
https://youtu.be/8TEil-9tsfY

3- بعد الشراء يجيك رابط، افتحه في تطبيق OsmAnd.

https://RahalTeam.com""",
    "تثبيت": """📱 شرح التثبيت:
للايفون: www.RahalTeam.com + https://youtu.be/8TEil-9tsfY
للأندرويد وهواوي: https://RahalTeam.com حمل الملف وافتحه في OsmAnd""",
    "شراء": """🛒 الشراء من www.RahalTeam.com
اختر الخريطة > اضف للسلة > ادفع (مدى/فيزا) > يوصلك الكود""",
    "خريطة": "🗺️ خرائط رحال في www.RahalTeam.com اختر منطقتك",
}

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

def get_relevant(query):
    q = query.lower()
    # ابحث في الملف اولا
    file_k = load_file_knowledge()
    if file_k:
        chunks = [c.strip() for c in file_k.split("---") if c.strip()]
        for ch in chunks[::-1]:
            cl = ch.lower()
            if any(w in q for w in ["ايفون","تثبيت","شراء","خريطة"]) and any(w in cl for w in ["ايفون","تثبيت","http","www"]):
                if sum(1 for w in re.findall(r'\w+', q) if len(w)>2 and w in cl) >= 1:
                    return ch
    if any(k in q for k in ["ايفون"]): return KNOWLEDGE_BASE["ايفون"]
    if "تثبيت" in q: return KNOWLEDGE_BASE["تثبيت"]
    if "شراء" in q: return KNOWLEDGE_BASE["شراء"]
    if "خريطة" in q or "اريد" in q: return KNOWLEDGE_BASE["خريطة"]
    return None

def ask_cheap_ai(prompt, relevant=None):
    client, model = get_ai_client()
    if not client: return None
    try:
        system = "انت بوت خرائط رحال، سعودي ودود، ترد بحرية ومختصر، لا تكرر نفس الجملة."
        if relevant:
            system += f"\nمعلومات مهمة استخدمها مع روابطها حرفيا:\n{relevant}"
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return resp.choices[0].message.content
    except Exception as e:
        print(f"AI Error {model}: {e}")
        return None

async def post_init(application: Application):
    try: await application.bot.delete_webhook(drop_pending_updates=True)
    except: pass

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client, model = get_ai_client()
    ai_status = f"ذكاء شغال ✅ {model}" if client else "ذكاء مطفي (يرد من الذاكرة فقط)"
    status = "موقف ⏸️" if BOT_PAUSED else "شغال ✅"
    await update.message.reply_text(f"رحال {status}\n{ai_status}\n\n/on\n/off\n/memory\n/save", reply_to_message_id=update.message.message_id)

async def on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED=False; save_status(False)
    await update.message.reply_text("اشتغلت ✅", reply_to_message_id=update.message.message_id)

async def off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED=True; save_status(True)
    await update.message.reply_text("وقفت ⏸️", reply_to_message_id=update.message.message_id)

async def memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    fk = load_file_knowledge() or "لا يوجد اضافي"
    await update.message.reply_text(fk[:3500], reply_to_message_id=update.message.message_id)

async def save_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    text = " ".join(context.args)
    if not text: 
        await update.message.reply_text("استخدم: /save النص", reply_to_message_id=update.message.message_id)
        return
    save_knowledge(text)
    await update.message.reply_text(f"✅ حفظت:\n{text[:1000]}", reply_to_message_id=update.message.message_id)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if update.effective_user.is_bot: return
    user_text = update.message.text or ""
    uid = str(update.effective_user.id)
    chat_type = update.effective_chat.type
    low = user_text.strip().lower()

    if chat_type == "private" and uid in ADMIN_IDS:
        if low in ["مسح","امسح"]:
            open(KNOWLEDGE_FILE, "w", encoding="utf-8").close()
            await update.message.reply_text("✅ مسحت", reply_to_message_id=update.message.message_id)
            return
        if user_text.startswith("احفظ") or low.startswith("احفظ"):
            clean = user_text.replace("احفظ","").strip(" :")
            if len(clean)>2:
                save_knowledge(clean)
                await update.message.reply_text(f"✅ حفظت:\n{clean[:1200]}", reply_to_message_id=update.message.message_id)
            return
    else:
        if BOT_PAUSED: return

    # 1- لو السؤال عن شرح او رابط - جاوب مباشرة بدون ما تدفع API
    relevant = get_relevant(user_text)
    if relevant and any(k in low for k in ["تثبيت","ايفون","شراء","رابط","خريطة"]):
        if "http" in relevant or "www" in relevant:
            await update.message.reply_text(relevant, reply_to_message_id=update.message.message_id)
            return

    # 2- لو تحية بسيطة - رد متنوع بدون API
    if any(k in low for k in ["سلام","مرحبا","هلا","صباح","مساء","شكرا","اخبارك"]):
        if relevant: # فيه رد من المعرفة
            pass
        else:
            greetings = {
                "سلام": ["وعليكم السلام ورحمة الله حياك","هلا وعليكم السلام"],
                "مرحبا": ["هلا والله نورت","يا هلا حياك","مرحبا مليون"],
                "صباح": ["صباح النور","صباح الورد حياك"],
                "شكرا": ["العفو حاضرين","العفو يا غالي"],
                "اخبارك": ["بخير الله يسعدك","تمام الحمدلله"]
            }
            for k,v in greetings.items():
                if k in low:
                    await update.message.reply_text(random.choice(v), reply_to_message_id=update.message.message_id)
                    return

    # 3- لو سؤال جديد - استخدم الذكاء الرخيص
    ai_ans = ask_cheap_ai(user_text, relevant)
    if ai_ans:
        await update.message.reply_text(ai_ans, reply_to_message_id=update.message.message_id)
        return

    # 4- Fallback لو الذكاء فاصل
    if relevant:
        await update.message.reply_text(relevant, reply_to_message_id=update.message.message_id)
    else:
        await update.message.reply_text("هلا والله حياك، وش تبي تعرف عن خرائط رحال؟\nقل: شرح التثبيت للايفون", reply_to_message_id=update.message.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("on", on_cmd))
    app.add_handler(CommandHandler("off", off_cmd))
    app.add_handler(CommandHandler("memory", memory_cmd))
    app.add_handler(CommandHandler("save", save_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Rahal Cheap AI Bot Ready")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
