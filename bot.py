import os, threading
from datetime import time, timezone
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Rahal - Talks To Admin Now"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask, daemon=True).start()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip().strip('"').strip("'")
ADMIN_ID_RAW = os.getenv("ADMIN_ID","").strip().strip('"').strip("'")
ADMIN_IDS = [s.strip() for s in ADMIN_ID_RAW.replace(" ", "").split(",") if s.strip()]
GROQ_KEY = os.getenv("GROQ_API_KEY","").strip()

client = OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_KEY else None
MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]

BASE_INFO = """متجر خرائط رحال: www.RahalTeam.com
الشرح: https://youtu.be/8TEil-9tsfY
الرابط: https://RahalTeam.com"""

KNOWLEDGE_FILE = "knowledge.txt"

def load_knowledge():
    if os.path.exists(KNOWLEDGE_FILE):
        try: return BASE_INFO + "\n" + open(KNOWLEDGE_FILE,"r",encoding="utf-8").read()
        except: return BASE_INFO
    return BASE_INFO

def save_text(t):
    with open(KNOWLEDGE_FILE,"a",encoding="utf-8") as f:
        f.write(f"\n{t[:800]}\n---\n")

def get_answer(q):
    facts = load_knowledge()
    if not client:
        return facts[:1000]
    for m in MODELS:
        try:
            r = client.chat.completions.create(
                model=m,
                messages=[
                    {"role":"system","content": f"انت بوت خرائط رحال، سعودي، ذكي، ودود. تتحدث مع المشرفين وتتعلم منهم. معلوماتك:\n{facts}\nروابطك: www.RahalTeam.com https://youtu.be/8TEil-9tsfY"},
                    {"role":"user","content": q}
                ],
                temperature=0.8,
                max_tokens=600
            )
            return r.choices[0].message.content
        except Exception as e:
            print(f"{m} fail: {e}")
            continue
    return "هلا والله! أنا رحال، متجرنا www.RahalTeam.com والشرح https://youtu.be/8TEil-9tsfY - وش حاب تعرف؟"

async def daily_backup(context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(KNOWLEDGE_FILE): return
    try:
        with open(KNOWLEDGE_FILE,"r",encoding="utf-8") as f:
            content = f.read()
        if not content.strip(): return
        for admin_id in ADMIN_IDS:
            try:
                if len(content) > 3500:
                    tmp_path = "/tmp/rahal_backup.txt"
                    with open(tmp_path,"w",encoding="utf-8") as tmp:
                        tmp.write(content)
                    await context.bot.send_document(chat_id=admin_id, document=open(tmp_path,"rb"), filename="rahal_backup.txt", caption=f"📚 نسخة يومية - {len(content)} حرف")
                else:
                    await context.bot.send_message(chat_id=admin_id, text=f"📚 نسخة يومية:\n{content[:3500]}")
            except: pass
    except: pass

async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS: return
    if not os.path.exists(KNOWLEDGE_FILE):
        await update.message.reply_text("ما فيه شي محفوظ لسه")
        return
    with open(KNOWLEDGE_FILE,"r",encoding="utf-8") as f:
        content = f.read()
    await update.message.reply_text(content[:4000] if content else "فاضي")

async def post_init(app: Application):
    try: await app.bot.delete_webhook(drop_pending_updates=True)
    except: pass
    try:
        app.job_queue.run_daily(daily_backup, time=time(hour=18, minute=0, tzinfo=timezone.utc), name="daily_backup")
    except: pass

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid in ADMIN_IDS:
        await update.message.reply_text(f"✅ هلا بالمشرف! ID حقك {uid} محفوظ\n\nأقدر أعلمك:\n- اكتب أي معلومة وبتحفظ لحالها\n- مثال: احفظ رابط الايفون كذا\n- أو تصدير لتصدير البيانات\n- أو علمني في القروب بردك على الأعضاء\n\nوش تبي تعلمني اليوم؟")
    else:
        await update.message.reply_text("✅ هلا! أنا بوت رحال - اسألني عن الخرائط www.RahalTeam.com")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.is_bot: return
    text = update.message.text or ""
    if not text: return
    
    # أوامر نصية عربية
    low = text.strip().lower()
    if low in ["تصدير", "تصدير البيانات", "نسخة", "النسخة"]:
        await export_cmd(update, context)
        return
    if text.startswith("/"):
        return

    uid = str(update.effective_user.id)
    chat_type = update.effective_chat.type
    is_admin = uid in ADMIN_IDS

    # === الخاص مع المشرف - الحين يتكلم ويحفظ ===
    if is_admin and chat_type == "private":
        # أي رسالة من المشرف في الخاص تنحفظ
        if len(text.strip()) >= 3:
            # لو فيها ID جديد احفظه
            if "1110419285" in text or "958444499" in text or "id" in text.lower() or "احفظ" in text:
                save_text(text)
                await update.message.reply_text(f"✅ تم يا مشرف! حفظت:\n{text[:800]}\n\nID حقكم: {', '.join(ADMIN_IDS)}\nالحين أقدر أرد على الأعضاء بنفس كلامك")
                return
            # أي كلام ثاني من المشرف ينحفظ ويرد عليه
            if len(text) > 10:
                save_text(text)
                ans = get_answer(text)
                await update.message.reply_text(f"✅ حفظت وأنا أتعلم\n\n{ans}")
                return
            else:
                await update.message.reply_text(f"هلا {uid} - اكتب المعلومة اللي تبي تحفظها، مثال:\nاحفظ طريقة التثبيت كذا وكذا")
                return

    # === القروب - رد المشرف ينحفظ بدون ما يرد البوت ===
    if is_admin and chat_type in ["group", "supergroup", "channel"]:
        if len(text.strip()) >= 8:
            q = ""
            if update.message.reply_to_message and update.message.reply_to_message.text:
                q = update.message.reply_to_message.text
                save_text(f"س: {q[:300]}\nج: {text[:800]}")
            else:
                save_text(text)
        return

    # === عضو عادي يسأل ===
    if not is_admin:
        ans = get_answer(text)
        await update.message.reply_text(ans, reply_to_message_id=update.message.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Bot talks to admin fixed")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
