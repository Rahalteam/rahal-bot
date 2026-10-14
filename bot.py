import os, json, hashlib
from flask import Flask
import threading
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Render keep alive ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot Live - Saudi + Private Safe"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

# --- ENV ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip().strip('"').strip("'")
ADMIN_ID_RAW = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")
ADMIN_IDS = [s.strip() for s in ADMIN_ID_RAW.replace(" ", "").split(",") if s.strip()]

genai.configure(api_key=GEMINI_API_KEY)
AVAILABLE_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.8-flash"]

KNOWLEDGE_FILE = "knowledge.txt"
CACHE_FILE = "cache.json"

def load_knowledge():
    if os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f: return f.read()
    return ""

def save_knowledge(text):
    with open(KNOWLEDGE_FILE, "a", encoding="utf-8") as f: f.write("\n" + text)

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}
def save_cache(c):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f: json.dump(c, f, ensure_ascii=False)
    except: pass

cache_data = load_cache()
def normalize_q(q): return q.lower().strip().replace("؟","").replace("?","").replace(" "," ")
def get_from_cache(q):
    key = hashlib.md5(normalize_q(q).encode()).hexdigest()
    return cache_data.get(key)
def add_to_cache(q, a):
    if len(cache_data) > 500: cache_data.pop(next(iter(cache_data)))
    key = hashlib.md5(normalize_q(q).encode()).hexdigest()
    cache_data[key] = a
    save_cache(cache_data)

# --- البرومبت النهائي المطلوب ---
SYSTEM_PROMPT = "انت مساعد ذكي ودود ومختصر. تحدث بلهجة سعودية بسيطة وبيضاء ومفهومة. ممنوع منعاً باتاً تذكر جنسيتك ولا تقل انك سعودي او اردني، وممنوع تذكر أي معلومات خاصة عن أي فريق أو جهة أو أشخاص نهائياً حتى لو المستخدم سألك بشكل مباشر وحتى لو المعلومات موجودة عندك. إذا سألك أحد عن معلومات خاصة، اعتذر بلطف وقل: 'ما أقدر أفيدك بهالمعلومة' وغير الموضوع بلطف."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("هلا والله! 👋\nأنا جاهز أساعدك، اسألني اللي تبيه.")

async def learn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS:
        await update.message.reply_text("عذراً، هالخاصية للأدمن فقط 🔒"); return
    if not context.args: return
    info = " ".join(context.args)
    save_knowledge(info)
    cache_data.clear(); save_cache(cache_data)
    await update.message.reply_text(f"✅ تم الحفظ")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    uid = str(update.effective_user.id)

    # الحفظ فقط للي ID حقهم محفوظ في Render
    if uid in ADMIN_IDS and any(w in user_text for w in ["احفظ","تذكر","تعلم ان","خزن"]):
        clean = user_text
        for w in ["احفظ","تذكر","تعلم ان","تعلم أن","خزن"]: clean = clean.replace(w,"").strip()
        if clean:
            save_knowledge(clean)
            cache_data.clear(); save_cache(cache_data)
            await update.message.reply_text(f"✅ تم الحفظ")
            return

    cached = get_from_cache(user_text)
    if cached:
        await update.message.reply_text(cached); return

    knowledge = load_knowledge()
    full_prompt = f"{SYSTEM_PROMPT}\n\nمعلومات عامة (لا تذكرها كمعلومات خاصة):\n{knowledge}\n\nسؤال المستخدم: {user_text}"

    for m in AVAILABLE_MODELS:
        try:
            model = genai.GenerativeModel(m)
            res = model.generate_content(full_prompt)
            if res.text:
                add_to_cache(user_text, res.text)
                await update.message.reply_text(res.text); return
        except Exception as e:
            print(f"Error {m}: {e}"); continue
    await update.message.reply_text("اعذرني، صار ضغط شوي، جرب بعد دقيقة 🙏")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("learn", learn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print(f"Admins: {ADMIN_IDS} - Bot RUNNING")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__": main()
