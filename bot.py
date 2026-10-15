import os, threading
from datetime import time, timezone
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from openai import OpenAI

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Rahal - Daily Backup 9PM KSA"
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

# === النسخ الاحتياطي اليومي ===
async def daily_backup(context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(KNOWLEDGE_FILE):
        return
    try:
        with open(KNOWLEDGE_FILE,"r",encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            content = "ما تعلم شي جديد اليوم - الملف فاضي"
        
        for admin_id in ADMIN_IDS:
            try:
                # لو الملف كبير ارسله كملف
                if len(content) > 3500:
                    # نكتب ملف مؤقت
                    tmp_path = "/tmp/rahal_backup.txt"
                    with open(tmp_path,"w",encoding="utf-8") as tmp:
                        tmp.write(content)
                    await context.bot.send_document(
                        chat_id=admin_id,
                        document=open(tmp_path,"rb"),
                        filename=f"rahal_backup_{context.job.next_t.strftime('%Y-%m-%d')}.txt",
                        caption=f"📚 النسخة الاحتياطية اليومية - {len(content)} حرف - كل ردودك المحفوظة"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"📚 النسخة الاحتياطية اليومية\n{len(content)} حرف محفوظ:\n\n{content[:3500]}"
                    )
            except Exception as e:
                print(f"Backup send failed to {admin_id}: {e}")
    except Exception as e:
        print(f"Daily backup error: {e}")

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
        await update.message.reply_document(
            document=open(tmp_path,"rb"),
            filename="rahal_knowledge.txt",
            caption="كل ردودك المحفوظة"
        )
    else:
        await update.message.reply_text(content[:4000])

async def post_init(app: Application):
    try: await app.bot.delete_webhook(drop_pending_updates=True)
    except: pass
    # كل يوم 9 مساء بتوقيت السعودية = 6 مساء UTC
    try:
        app.job_queue.run_daily(
            daily_backup,
            time=time(hour=18, minute=0, tzinfo=timezone.utc),
            name="daily_backup_9pm_ksa"
        )
        print("Daily backup scheduled 9PM KSA")
    except Exception as e:
        print(f"Scheduling failed: {e}")

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ شغال - يحفظ ردودك فقط + نسخة يومية 9 مساء على الخاص", reply_to_message_id=update.message.message_id)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.is_bot: return
    text = update.message.text or ""
    if not text or text.startswith("/"): return
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
            await update.message.reply_text(f"✅ حفظت: {clean[:600]}")
        return

    if not is_admin:
        ans = get_answer(text)
        await update.message.reply_text(ans, reply_to_message_id=update.message.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("تصدير", export_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("Bot with daily backup ready")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
