import os, json, hashlib, re, datetime
from flask import Flask
import threading
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image
import pytz

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot Live"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip().strip('"').strip("'")
ADMIN_ID_RAW = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")
ADMIN_IDS = [s.strip() for s in ADMIN_ID_RAW.replace(" ", "").split(",") if s.strip()]

genai.configure(api_key=GEMINI_API_KEY)
AVAILABLE_MODELS = ["gemini-2.5-flash", "gemini-1.5-flash"]

KNOWLEDGE_FILE = "knowledge.txt"
CACHE_FILE = "cache.json"
STATUS_FILE = "bot_status.json"
STATS_FILE = "daily_stats.json"

def load_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f: return json.load(f).get("paused", False)
        except: return False
    return False
def save_status(p): json.dump({"paused": p}, open(STATUS_FILE, "w", encoding="utf-8"))
BOT_PAUSED = load_status()

def load_knowledge(): return open(KNOWLEDGE_FILE, "r", encoding="utf-8").read() if os.path.exists(KNOWLEDGE_FILE) else ""
def save_knowledge(t):
    with open(KNOWLEDGE_FILE, "a", encoding="utf-8") as f: f.write("\n" + t)

def load_cache():
    if os.path.exists(CACHE_FILE):
        try: return json.load(open(CACHE_FILE, "r", encoding="utf-8"))
        except: return {}
    return {}
def save_cache(c): json.dump(c, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False)
cache_data = load_cache()
def get_from_cache(q): return cache_data.get(hashlib.md5(q.lower().strip().encode()).hexdigest())
def add_to_cache(q,a):
    if len(cache_data)>500: cache_data.pop(next(iter(cache_data)))
    cache_data[hashlib.md5(q.lower().strip().encode()).hexdigest()]=a
    save_cache(cache_data)

def load_stats():
    if os.path.exists(STATS_FILE):
        try: return json.load(open(STATS_FILE, "r", encoding="utf-8"))
        except: return {"date": str(datetime.date.today()), "total":0, "questions":[], "unknown":[]}
    return {"date": str(datetime.date.today()), "total":0, "questions":[], "unknown":[]}
def save_stats(s): json.dump(s, open(STATS_FILE, "w", encoding="utf-8"), ensure_ascii=False)
def add_stat(q, unknown=False):
    s=load_stats()
    today=str(datetime.date.today())
    if s["date"]!=today: s={"date":today,"total":0,"questions":[],"unknown":[]}
    s["total"]+=1
    if len(s["questions"])<20: s["questions"].append(q[:100])
    if unknown and len(s["unknown"])<10: s["unknown"].append(q[:100])
    save_stats(s)

def is_trivial(text):
    if not text: return True
    t=text.strip().lower()
    if len(t)<=2: return True
    if t in ["هههه","ههههه","هه","تم","تمام","ok","اوك","ابشر","هلا","سلام","😂","❤️","👍"]: return True
    if len(set(t))<=2 and len(t)>3 and "ه" in t: return True
    return False

SYSTEM_PROMPT = "انت مساعد فريق ذكي بلهجة سعودية بيضاء ومختصرة. إذا ما تعرف الجواب قل بالضبط: لا أملك معلومة مؤكدة. حلل الصور."

async def daily_summary_job(context: ContextTypes.DEFAULT_TYPE):
    stats=load_stats()
    if stats["total"]==0: return
    unknown_text = "\n".join([f"- {u}" for u in stats.get("unknown",[])]) if stats.get("unknown") else "لا يوجد"
    summary = f"📊 ملخص اليوم {stats['date']}\n\nعدد الأسئلة: {stats['total']}\nأكثر الأسئلة:\n- " + "\n- ".join(stats["questions"][:10]) + f"\n\n❓ أسئلة ما عرفتها:\n{unknown_text}"
    for aid in ADMIN_IDS:
        try: await context.bot.send_message(chat_id=int(aid), text=summary)
        except: pass
    save_stats({"date": str(datetime.date.today()), "total":0, "questions":[], "unknown":[]})

async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED=False; save_status(False)
    await update.message.reply_text("🔔 اشتغلت", reply_to_message_id=update.message.message_id)
async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED=True; save_status(True)
    await update.message.reply_text("🔕 وقفت", reply_to_message_id=update.message.message_id)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if update.effective_user.is_bot: return
    user_text=update.message.text or ""
    uid=str(update.effective_user.id)
    chat_type=update.effective_chat.type

    # التعلم منك: ترد Reply على أي سؤال
    if uid in ADMIN_IDS and update.message.reply_to_message:
        orig = update.message.reply_to_message.text or update.message.reply_to_message.caption or ""
        if orig and not update.message.reply_to_message.from_user.is_bot and len(user_text)>5:
            save_knowledge(f"سؤال: {orig}\nجواب معتمد: {user_text}\n---")
            cache_data.clear(); save_cache(cache_data)
            await update.message.reply_text("✅ تعلمت وحفظت جوابك", reply_to_message_id=update.message.message_id)
            if chat_type != "private":
                BOT_PAUSED=True; save_status(True)
            return

    if chat_type in ["group","supergroup"] and uid in ADMIN_IDS:
        if any(w in user_text for w in ["احفظ","تذكر","خزن"]):
            clean=user_text
            for w in ["احفظ","تذكر","خزن"]: clean=clean.replace(w,"").strip()
            if clean:
                save_knowledge(clean); cache_data.clear(); save_cache(cache_data)
                await update.message.reply_text("✅ تم الحفظ", reply_to_message_id=update.message.message_id)
            return
        if user_text.startswith("/on") or user_text.startswith("/off"): return
        BOT_PAUSED=True; save_status(True); return

    if BOT_PAUSED: return
    if is_trivial(user_text): return

    cached=get_from_cache(user_text)
    if cached:
        await update.message.reply_text(cached, reply_to_message_id=update.message.message_id)
        add_stat(user_text)
        return

    knowledge=load_knowledge()
    full_prompt=f"{SYSTEM_PROMPT}\nمعلوماتك: {knowledge}\nسؤال: {user_text}"
    answer_text=None
    for m in AVAILABLE_MODELS:
        try:
            model=genai.GenerativeModel(m)
            res=model.generate_content(full_prompt)
            if res.text:
                answer_text=res.text
                break
        except: continue

    if not answer_text or "لا أملك معلومة مؤكدة" in answer_text:
        add_stat(user_text, unknown=True)
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=int(aid), text=f"❓ سؤال جديد ما عرفت أجاوبه\n\nمن: {update.effective_user.first_name}\nالسؤال: {user_text}\n\nرد على هذه الرسالة بجوابك وأنا أحفظه")
            except: pass
        await update.message.reply_text("ما عندي إجابة مؤكدة، حولت سؤالك للأدمن بيرد قريب 🙏", reply_to_message_id=update.message.message_id)
        return

    add_to_cache(user_text, answer_text)
    add_stat(user_text)
    await update.message.reply_text(answer_text, reply_to_message_id=update.message.message_id)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.is_bot: return
    if BOT_PAUSED: return
    if str(update.effective_user.id) in ADMIN_IDS and update.effective_chat.type in ["group","supergroup"]:
        BOT_PAUSED=True; save_status(True); return
    try:
        photo_file=await update.message.photo[-1].get_file()
        await photo_file.download_to_drive("temp_photo.jpg")
        img=Image.open("temp_photo.jpg")
        caption=update.message.caption or ""
        add_stat(caption or "صورة")
        prompt=f"{SYSTEM_PROMPT}\nمعلومات: {load_knowledge()}\nتعليق: {caption}\nحلل الصورة"
        model=genai.GenerativeModel("gemini-2.5-flash")
        res=model.generate_content([prompt,img])
        if res.text:
            await update.message.reply_text(res.text, reply_to_message_id=update.message.message_id)
    except: pass

def main():
    app=Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler(["on","شغل"], on_command))
    app.add_handler(CommandHandler(["off","وقف"], off_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    try:
        tz = pytz.timezone("Asia/Riyadh")
        app.job_queue.run_daily(daily_summary_job, time=datetime.time(hour=21, minute=0, tzinfo=tz))
    except:
        app.job_queue.run_daily(daily_summary_job, time=datetime.time(hour=18, minute=0))
    print(f"Running - Paused={BOT_PAUSED}")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
