import os, json, re
from flask import Flask
import threading
from google import genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Rahal Bot Working"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","").strip().strip('"').strip("'")
ADMIN_ID_RAW = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")
ADMIN_IDS = [s.strip() for s in ADMIN_ID_RAW.replace(" ", "").split(",") if s.strip()]

client = genai.Client(api_key=GEMINI_API_KEY)

DEFAULT_KNOWLEDGE = """
متجر خرائط رحال - www.RahalTeam.com

الشراء من الموقع: تدخل www.RahalTeam.com تختار الخريطة تضيف للسلة تكمل الدفع (مدى، فيزا) يوصلك كود.

شرح الشراء والتثبيت من الموقع الالكتروني:
رابط الموقع 👇 www.RahalTeam.com
شرح فيديو 👇 https://youtu.be/8TEil-9tsfY
شرح التثبيت لخرائط رحال للايفون من متجر رحال لتطبيق اوسماند.
رابط متجر رحال للأندرويد والأيفون وهواوي وشاشات السيارات https://RahalTeam.com

التثبيت للايفون: من موقع RahalTeam.com بعد الشراء يجيك رابط تفتحه في تطبيق OsmAnd
التثبيت للأندرويد: نفس الموقع، يحمل ملف الخريطة ويفتح في OsmAnd
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
    return DEFAULT_KNOWLEDGE + "\n---\n" + load_file_knowledge()

def get_relevant(query, all_text):
    chunks = [c.strip() for c in all_text.split("---") if c.strip()]
    q = query.lower()
    if not any(k in q for k in ["شرح","تثبيت","ايفون","اندرويد","رابط","موقع","شراء","كيف","طريقة"]):
        if any(k in q for k in ["مرحبا","هلا","سلام","شكرا","كيفك","طيب","ممتاز","تصبح"]):
            return ""
    scored = []
    for ch in chunks:
        cl = ch.lower()
        score = 0
        if "ايفون" in q and "ايفون" in cl: score += 20
        if "تثبيت" in q and "تثبيت" in cl: score += 15
        if "شراء" in q and "شراء" in cl: score += 10
        if "youtu.be" in cl or "RahalTeam" in ch: score += 5
        for w in re.findall(r'\w+', q):
            if len(w)>2 and w in cl: score+=1
        scored.append((score,ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    rel = [c for s,c in scored if s>0][:2]
    return "\n---\n".join(rel)

def ask_gemini(prompt):
    try:
        res = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        return res.text
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None

SYSTEM_PROMPT = """
انت بوت خرائط رحال الذكي، ترد بلهجة سعودية ودودة ومتنوعة، لا تكرر نفس الجملة.

اذا اعطيتك معلومات محفوظة استخدمها حرفيا مع روابطها.
اذا ما فيه معلومات محفوظة، جاوب بشكل حر وذكي.
"""

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "موقف ⏸️" if BOT_PAUSED else "شغال ✅"
    await update.message.reply_text(f"بوت رحال {status}\n/on لتشغيل\n/off لإيقاف\n/clear لمسح الذاكرة الإضافية\n/memory لعرض الذاكرة", reply_to_message_id=update.message.message_id)

async def on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: 
        await update.message.reply_text("فقط الأدمن يقدر يشغلني", reply_to_message_id=update.message.message_id)
        return
    BOT_PAUSED=False; save_status(False)
    await update.message.reply_text("اشتغلت ✅ الآن أرد على الجميع", reply_to_message_id=update.message.message_id)

async def off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED=True; save_status(True)
    await update.message.reply_text("وقفت ⏸️ اكتب /on لتشغيلي", reply_to_message_id=update.message.message_id)

async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    clear_file_knowledge()
    await update.message.reply_text("✅ مسحت الذاكرة الإضافية", reply_to_message_id=update.message.message_id)

async def memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    all_k = get_all_knowledge()
    await update.message.reply_text(all_k[:3500], reply_to_message_id=update.message.message_id)

async def arabic_control(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    txt = update.message.text.strip().lower().replace("/","")
    if txt in ["شغل","تشغيل","on"]:
        BOT_PAUSED=False; save_status(False)
        await update.message.reply_text("اشتغلت ✅", reply_to_message_id=update.message.message_id)
    elif txt in ["وقف","ايقاف","off"]:
        BOT_PAUSED=True; save_status(True)
        await update.message.reply_text("وقفت ⏸️", reply_to_message_id=update.message.message_id)
    elif txt in ["مسح","امسح"]:
        clear_file_knowledge()
        await update.message.reply_text("✅ تم المسح", reply_to_message_id=update.message.message_id)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if update.effective_user.is_bot: 
        return
    user_text = update.message.text or ""
    uid = str(update.effective_user.id)
    chat_type = update.effective_chat.type
    low = user_text.strip().lower()

    # الخاص - الأدمن
    if chat_type == "private" and uid in ADMIN_IDS:
        if low in ["مسح","امسح","احذف"]:
            clear_file_knowledge()
            await update.message.reply_text("✅ مسحت الإضافي", reply_to_message_id=update.message.message_id)
            return
        if low.startswith(("احفظ","تذكر","خزن")):
            clean = user_text
            for w in ["احفظ","تذكر","خزن"]: clean = clean.replace(w,"").strip(" :")
            if len(clean)>2:
                save_knowledge(clean)
                await update.message.reply_text(f"✅ حفظت:\n{clean[:1000]}", reply_to_message_id=update.message.message_id)
            return
        # في الخاص يرد حتى لو موقف في القروبات
        # لا نعمل return للـ paused هنا
    else:
        # في القروبات فقط نحترم الوقف
        if BOT_PAUSED:
            return

    # تحويل طلبات
    if any(k in low for k in ["طلبي","رقم الطلب","وين طلبي"]):
        for aid in ADMIN_IDS:
            try: await context.bot.send_message(chat_id=int(aid), text=f"📦 طلب: {user_text} من {update.effective_user.first_name}")
            except: pass
        await update.message.reply_text("حولت سؤالك للأدمن 📦", reply_to_message_id=update.message.message_id)
        return

    all_knowledge = get_all_knowledge()
    relevant = get_relevant(user_text, all_knowledge)

    if relevant:
        prompt = f"""{SYSTEM_PROMPT}
معلومات محفوظة:
{relevant}

المستخدم: {user_text}
رد باستخدام المعلومات المحفوظة مع روابطها حرفيا وبشكل حر:"""
    else:
        prompt = f"""{SYSTEM_PROMPT}
المستخدم: {user_text}
رد بشكل حر ومتنوع:"""

    ans = ask_gemini(prompt)
    if ans:
        await update.message.reply_text(ans, reply_to_message_id=update.message.message_id)
    else:
        # رد احتياطي متنوع
        if "سلام" in low: await update.message.reply_text("وعليكم السلام ورحمة الله حياك", reply_to_message_id=update.message.message_id)
        elif "مرحبا" in low or "هلا" in low: await update.message.reply_text("هلا والله نورت", reply_to_message_id=update.message.message_id)
        elif "شكرا" in low: await update.message.reply_text("العفو حاضرين", reply_to_message_id=update.message.message_id)
        else: await update.message.reply_text("هلا والله، تفضل كيف أقدر أساعدك؟", reply_to_message_id=update.message.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("on", on_cmd))
    app.add_handler(CommandHandler("off", off_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("memory", memory_cmd))
    app.add_handler(MessageHandler(filters.Regex(r'^(/?شغل|/?وقف|/?مسح|/?امسح)$'), arabic_control))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Rahal Working Bot - No auto pause")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
