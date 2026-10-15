import os, json, re
from flask import Flask
import threading
from google import genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Rahal Smart Bot"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip().strip('"').strip("'")
ADMIN_ID_RAW = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")
ADMIN_IDS = [s.strip() for s in ADMIN_ID_RAW.replace(" ", "").split(",") if s.strip()]

client = genai.Client(api_key=GEMINI_API_KEY)

# هذه ذاكرة ثابتة ما تنمسح حتى لو Render مسح الملف
DEFAULT_KNOWLEDGE = """
متجر خرائط رحال الاحترافية - RahalTeam.com

1- الشراء من الموقع الإلكتروني:
رابط المتجر: www.RahalTeam.com
تختار الخريطة اللي تبيها، تضيفها للسلة، تكمل الدفع (مدى، فيزا، تحويل)، يوصلك كود التفعيل.

2- شرح التثبيت للايفون من الموقع الإلكتروني:
رابط الموقع الإلكتروني 👇
www.RahalTeam.com
شرح الشراء والتثبيت من الموقع الالكتروني 👇
https://youtu.be/8TEil-9tsfY
شرح التثبيت لخرائط رحال الاحترافية لأجهزة الايفون من متجر رحال لتطبيق اوسماند
رابط متجر خرائط رحال للأندرويد والأيفون وهواوي وشاشات السيارات https://RahalTeam.com

3- تثبيت الأندرويد وهواوي وشاشات السيارات من نفس الرابط https://RahalTeam.com

4- الدعم الفني: اذا واجهت مشكلة ارسل صورة للمشكلة
"""

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
def clear_file_knowledge():
    open(KNOWLEDGE_FILE, "w", encoding="utf-8").close()

def get_all_knowledge():
    return DEFAULT_KNOWLEDGE + "\n\n---\n\n" + load_file_knowledge()

def get_relevant(query, all_text):
    if not all_text.strip():
        return ""
    chunks = [c.strip() for c in all_text.split("---") if c.strip()]
    q = query.lower()
    # اذا تحية لا تجيب ذاكرة
    if any(w in q for w in ["مرحبا","هلا","سلام","شكرا","كيفك","طيب","ممتاز","تصبح"]):
        # الا اذا السؤال فيه كلمة شرح او تثبيت او ايفون
        if not any(w in q for w in ["شرح","تثبيت","ايفون","اندرويد","رابط","موقع"]):
            return ""
    
    scored = []
    for ch in chunks:
        score = 0
        cl = ch.lower()
        if "ايفون" in q and "ايفون" in cl: score += 20
        if "تثبيت" in q and "تثبيت" in cl: score += 15
        if "شراء" in q and "شراء" in cl: score += 10
        if "رابط" in q and ("http" in cl or "www." in cl): score += 10
        # تطابق كلمات عام
        for w in re.findall(r'\w+', q):
            if len(w) > 2 and w in cl:
                score += 1
        scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    rel = [c for s,c in scored if s>0][:2]
    if not rel:
        # لو ما لقى شيء والموضوع عن ايفون، جيب شرح الايفون الافتراضي
        if "ايفون" in q or "تثبيت" in q:
            for s,c in scored:
                if "youtu.be" in c or "RahalTeam" in c:
                    rel = [c]
                    break
    return "\n\n---\n\n".join(rel)

def ask_gemini(prompt):
    try:
        res = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        return res.text
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None

SYSTEM_PROMPT = """
انت بوت خرائط رحال، ذكي جدا وترد بشكل حر ومتنوع، لهجتك سعودية بيضاء وودودة.

قواعد:
- لا تكرر نفس الجملة ابدا.
- اذا المستخدم قال مرحبا: رد هلا والله نورت، او يا هلا، او هلا حياك، نوع.
- اذا قال شكرا لك: قل العفو، حاضرين، او العفو يا غالي، او من عيوني.
- اذا قال السلام عليكم: وعليكم السلام ورحمة الله، او هلا والله وعليكم السلام.
- اذا قال اريد شرح او شرح التثبيت: استخدم المعلومات المحفوظة اللي بعطيك اياها وارسل الروابط كما هي.
- جاوب بذكاء وحرية، لا تقول "تفضل وش تبي تعرف" كل مرة.
"""

async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED=False; save_status(False)
    await update.message.reply_text("اشتغلت ✅", reply_to_message_id=update.message.message_id)

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED=True; save_status(True)
    await update.message.reply_text("وقفت ⏸️", reply_to_message_id=update.message.message_id)

async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    clear_file_knowledge()
    await update.message.reply_text("✅ مسحت الذاكرة الإضافية، بقيت الذاكرة الأساسية الثابتة", reply_to_message_id=update.message.message_id)

async def show_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    all_k = get_all_knowledge()
    await update.message.reply_text(f"الذاكرة الحالية ({len(all_k)} حرف):\n\n{all_k[:3000]}", reply_to_message_id=update.message.message_id)

async def arabic_control(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    txt = update.message.text.strip().lower().replace("/","")
    if txt in ["شغل","تشغيل"]:
        BOT_PAUSED=False; save_status(False)
        await update.message.reply_text("اشتغلت ✅", reply_to_message_id=update.message.message_id)
    elif txt in ["وقف","ايقاف"]:
        BOT_PAUSED=True; save_status(True)
        await update.message.reply_text("وقفت ⏸️", reply_to_message_id=update.message.message_id)
    elif txt in ["مسح","امسح","احذف"]:
        clear_file_knowledge()
        await update.message.reply_text("✅ تم المسح", reply_to_message_id=update.message.message_id)
    elif txt in ["الذاكرة","ذاكرة","اعرض الذاكرة"]:
        all_k = get_all_knowledge()
        await update.message.reply_text(all_k[:3500], reply_to_message_id=update.message.message_id)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if update.effective_user.is_bot: return
    user_text=update.message.text or ""
    uid=str(update.effective_user.id)
    chat_type=update.effective_chat.type
    low = user_text.strip().lower()

    if chat_type == "private" and uid in ADMIN_IDS:
        if low in ["مسح","امسح","احذف","احذف جميع التعليمات","الذاكرة"]:
            if low == "الذاكرة" or "ذاكرة" in low:
                await show_memory(update, context)
                return
            clear_file_knowledge()
            await update.message.reply_text("✅ مسحت الإضافي، الأساسي باقي", reply_to_message_id=update.message.message_id)
            return
        if low.startswith(("احفظ","تذكر","خزن")):
            clean = user_text
            for w in ["احفظ","تذكر","خزن"]: clean = clean.replace(w,"").strip(" :")
            if len(clean) > 2:
                save_knowledge(clean)
                await update.message.reply_text(f"✅ حفظت وثبتت (ما راح تنمسح الا بأمر مسح):\n{clean[:800]}", reply_to_message_id=update.message.message_id)
            return
        if low.startswith("الذاكرة") or low == "اعرض":
            await show_memory(update, context)
            return

    if BOT_PAUSED: return

    if any(k in low for k in ["طلبي","رقم الطلب","وين طلبي","تتبع"]):
        for aid in ADMIN_IDS:
            try: await context.bot.send_message(chat_id=int(aid), text=f"📦 سؤال طلب من {update.effective_user.first_name}: {user_text}")
            except: pass
        await update.message.reply_text("حولت سؤالك للأدمن 📦 بيتواصل معك", reply_to_message_id=update.message.message_id)
        return

    all_knowledge = get_all_knowledge()
    relevant = get_relevant(user_text, all_knowledge)

    if relevant:
        prompt = f"""{SYSTEM_PROMPT}

معلومات محفوظة مهمة (استخدمها حرفيا مع روابطها):
{relevant}

المستخدم قال: {user_text}
ردك بذكاء وحرية مع استخدام المعلومات المحفوظة والروابط كما هي:"""
    else:
        prompt = f"""{SYSTEM_PROMPT}

المستخدم قال: {user_text}
رد بشكل حر ومتنوع وذكي:"""

    answer = ask_gemini(prompt)
    if answer:
        await update.message.reply_text(answer, reply_to_message_id=update.message.message_id)
    else:
        await update.message.reply_text("هلا والله حياك، وش أقدر أساعدك فيه؟", reply_to_message_id=update.message.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("on", on_command))
    app.add_handler(CommandHandler("off", off_command))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("memory", show_memory))
    app.add_handler(MessageHandler(filters.Regex(r'^(/?شغل|/?وقف|/?مسح|/?امسح|/?احذف|/?الذاكرة)$'), arabic_control))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Rahal Smart Free Learning BOT")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
