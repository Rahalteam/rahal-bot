import os, threading
from datetime import time, timezone
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Rahal - Fixed No Arabic Command"
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

def save_admin_reply(question, answer):
    with open(KNOWLEDGE_FILE,"a",encoding="utf-8") as f:
        if question:
            f.write(f"\nس: {question[:300]}\nج: {answer[:800]}\n---\n")
        else:
            f.write(f"\n{answer[:800]}\n---\n")

def get_answer(q):
    facts = load_knowledge()
    if not client:
        return facts[:1000]
    for m in MODELS:
        try:
            r = client.chat.completions.create(
                model=m,
                messages=[
                    {"role":"system","content": f"انت بوت خرائط رحال، سعودي ذكي. معلوماتك:\n{facts}"},
                    {"role":"user","content": q}
                ],
                temperature=0.7,
                max_tokens=600
            )
            return r.choices[0].message.content
        except:
            continue
    return facts[:1000]

async def daily_backup(context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(KNOWLEDGE_FILE):
        return
    try:
        with open(KNOWLEDGE_FILE,"r",encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            return
        for admin_id in ADMIN_IDS:
            try:
                if len(content) > 3500:
                    tmp_path = "/tmp/rahal_backup.txt"
                    with open(tmp_path,"w",encoding="utf-8") as tmp:
                        tmp.write(content)
                    await context.bot.send_document(
                        chat_id=admin_id,
                        document=open(tmp_path,"rb"),
                        filename="rahal_backup.txt",
                        caption=f"📚 النسخة اليومية - {len(content)} حرف"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"📚 النسخة اليومية:\n\n{content[:3500]}"
                    )
            except Exception as e:
                print(f"Backup fail {admin_id}: {e}")
    except Exception as e:
        print(f"Daily error: {e}")

async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) not in ADMIN_IDS:
        return
    if not os.path.exists(KNOWLEDGE_FILE):
        await update.message.reply_text("ما فيه شي محفوظ لسه")
        return
    with open(KNOWLEDGE_FILE,"r",encoding="utf-8") as f:
        content = f.read()
    if len(content) > 3500:
        tmp_path = "/tmp/rahal_export.txt"
        with open(tmp_path,"w",encoding="utf-8") as tmp:
            tmp.write(content)
        await update.message.reply_document(document=open(tmp_path,"rb"), filename="rahal_knowledge.txt")
    else:
        await update.message.reply_text(content[:4000] if content else "فاضي")

async def post_init(app: Application):
    try: await app.bot.delete_webhook(drop_pending_updates=True)
    except: pass
    try:
        app.job_queue.run_daily(
            daily_backup,
            time=time(hour=18, minute=0, tzinfo=timezone.utc),
            name="daily_backup"
        )
        print("Daily backup scheduled 9PM KSA")
    except Exception as e:
        print(f"Scheduling fail: {e}")

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ شغال - يحفظ ردود المشرف + نسخة يومية 9 مساء", reply_to_message_id=update.message.message_id)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.is_bot: return
    text = update.message.text or ""
    if not text:
        return
    # امر تصدير بالعربي بدون CommandHandler
    if text.strip() in ["تصدير", "تصدير البيانات", "نسخة"]:
        await export_cmd(update, context)
        return
    if text.startswith("/"):
        return
    uid = str(update.effective_user.id)
    chat_type = update.effective_chat.type
    is_admin = uid in ADMIN_IDS

    if is_admin and chat_type in ["group", "supergroup", "channel"]:
        if len(text.strip()) < 8:
            return
        q = ""
        if update.message.reply_to_message and update.message.reply_to_message.text:
            q = update.message.reply_to_message.text
        save_admin_reply(q, text)
        return

    if is_admin and chat_type == "private" and text.startswith("احفظ"):
        clean = text.replace("احفظ","").strip(" :")
        if len(clean)>5:
            save_admin_reply("", clean)
            await update.message.reply_text(f"✅ حفظت")
        return

    if not is_admin:
        ans = get_answer(text)
        await update.message.reply_text(ans, reply_to_message_id=update.message.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    # لا يوجد CommandHandler عربي هنا - هذا كان سبب الخطأ
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Bot fixed ready")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
