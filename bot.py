import os, json, hashlib
from flask import Flask
import threading
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 1. Render keep alive ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Rahal Bot Live - Cache + Auto Learn"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

# --- 2. ENV ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip().strip('"').strip("'")
ADMIN_ID = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")

genai.configure(api_key=GEMINI_API_KEY)
AVAILABLE_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.8-flash"]

KNOWLEDGE_FILE = "knowledge.txt"
CACHE_FILE = "cache.json"

# --- 3. الذاكرة والكاش ---
def load_knowledge():
    if os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f: return f.read()
    return "فريق رحال فريق تطوعي شبابي أردني، خرائط رحال منصة للفرص التطوعية."

def save_knowledge(text):
    with open(KNOWLEDGE_FILE, "a", encoding="utf-8") as f: f.write("\n" + text)

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f: json.dump(cache, f, ensure_ascii=False)
    except: pass

cache_data = load_cache()

def normalize_q(q):
    return q.lower().strip().replace("؟","").replace("?","").replace(" "," ")

def get_from_cache(q):
    key = hashlib.md5(normalize_q(q).encode()).hexdigest()
    return cache_data.get(key)

def add_to_cache(q, answer):
    if len(cache_data) > 500: # اذا كبر الكاش احذف اقدم واحد
        cache_data.pop(next(iter(cache_data)))
    key = hashlib.md5(normalize_q(q).encode()).hexdigest()
    cache_data[key] = answer
    save_cache(cache_data)

SYSTEM_PROMPT = "انت مساعد فريق رحال الأردني. احكي أردني بسيط وودود ومختصر."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً @Rahalteam2_bot 🚀\nبقدر اتعلم منك: قول 'احفظ انه...'\nوبقدر اجاوب من الذاكرة عشان اوفر!")

async def learn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and str(update.effective_user.id)!= str(ADMIN_ID):
        await update.message.reply_text("للأدمن فقط 🔒"); return
    if not context.args: return
    info = " ".join(context.args)
    save_knowledge(info)
    await update.message.reply_text(f"✅ تم الحفظ: {info}")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = str(update.effective_user.id)

    # 1. تعليم بالحكي العادي
    if ADMIN_ID and user_id == str(ADMIN_ID):
        if any(w in user_text for w in ["احفظ","تذكر","تعلم ان","خزن"]):
            clean = user_text
            for w in ["احفظ","تذكر","تعلم ان","تعلم أن","خزن"]: clean = clean.replace(w,"").strip()
            if clean:
                save_knowledge(clean)
                # امسح الكاش القديم عشان يتعلم الجديد
                cache_data.clear(); save_cache(cache_data)
                await update.message.reply_text(f"✅ حفظت ومسحت الذاكرة القديمة: {clean}")
                return

    # 2. افحص الكاش اولاً - منع التكرار
    cached = get_from_cache(user_text)
    if cached:
        print(f"CACHE HIT: {user_text}")
        await update.message.reply_text(cached + "\n\n_💾 من الذاكرة السريعة_")
        return

    # 3. اذا مش بالكاش روح لجوجل
    knowledge = load_knowledge()
    full_prompt = f"{SYSTEM_PROMPT}\nمعلومات:\n{knowledge}\nسؤال: {user_text}"

    for model_name in AVAILABLE_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(full_prompt)
            if response.text:
                add_to_cache(user_text, response.text) # احفظه للمرات الجاي
                await update.message.reply_text(response.text)
                return
        except Exception as e:
            print(f"Error {model_name}: {e}"); continue

    await update.message.reply_text("صار ضغط شوي، جرب بعد دقيقة 🙏")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("learn", learn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Bot RUNNING with Cache + Auto Learn...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__": main()
