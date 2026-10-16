
import os, json
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_KEY = (os.getenv("GROQ_API_KEY") or "").strip()

raw = os.getenv("ADMIN_ID", "0") or "0"
ADMIN_IDS = []
for p in raw.replace(",", " ").split():
    if p.isdigit():
        try: ADMIN_IDS.append(int(p))
        except: pass
if not ADMIN_IDS: ADMIN_IDS=[0]

AMMAN_TZ = pytz.timezone("Asia/Amman")
KNOWLEDGE_FILE = "knowledge/learned.json"
os.makedirs("knowledge", exist_ok=True)
if not os.path.exists(KNOWLEDGE_FILE):
    with open(KNOWLEDGE_FILE,"w",encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False)

def load_knowledge():
    try:
        with open(KNOWLEDGE_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    except: return []

def save_knowledge(q,a):
    data=load_knowledge()
    data.append({"q":q.strip(),"a":a.strip(),"time":datetime.now(AMMAN_TZ).isoformat()})
    if len(data)>500: data=data[-500:]
    with open(KNOWLEDGE_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)

def call_groq(system_prompt, user_text, max_tokens=500):
    if not GROQ_KEY:
        raise Exception("GROQ_API_KEY فاضي - حطه في Fly Secrets")
    from groq import Groq
    client=Groq(api_key=GROQ_KEY)
    # موديلات شغالة حاليا في Groq - نوفمبر 2024 وما بعد
    models = [
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "gemma2-9b-it",
        "llama-3.2-90b-text-preview",
    ]
    last_err=None
    for model in models:
        try:
            comp=client.chat.completions.create(
                model=model,
                messages=[
                    {"role":"system","content":system_prompt},
                    {"role":"user","content":user_text}
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )
            print(f"Model OK: {model}")
            return comp.choices[0].message.content
        except Exception as e:
            print(f"Model {model} failed: {e}")
            last_err=e
            # لو الموديل محذوف جرب اللي بعده فورا
            if "decommissioned" in str(e) or "model_decommissioned" in str(e):
                continue
            # لو خطأ مفتاح API وقف
            if "401" in str(e) or "invalid_api_key" in str(e) or "Unauthorized" in str(e):
                raise e
            continue
    raise last_err

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    key_ok = "موجود ✅" if GROQ_KEY else "مو موجود ❌"
    if uid in ADMIN_IDS:
        await update.message.reply_text(
            f"هلا يا شادي! 👑 ID:{uid}\nGROQ: {key_ok} ({len(GROQ_KEY)} حرف)\n\n"
            "كلمني بحرية\n"
            "ولما تبي تحفظ: احفظ السؤال | الجواب\n\n"
            "/list - وش حفظت"
        )
    else:
        await update.message.reply_text("هلا والله حياك في خرائط رحال 🗺️\nRahalTeam.com")

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"ايديك: {update.effective_user.id}")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    if uid not in ADMIN_IDS and 0 not in ADMIN_IDS: return
    data=load_knowledge()[-20:]
    if not data:
        await update.message.reply_text("ما حفظت شي لسه")
        return
    txt="\n\n".join([f"{i+1}. س:{x['q']}\nج:{x['a']}" for i,x in enumerate(data)])
    await update.message.reply_text(f"آخر 20:\n\n{txt}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text=update.message.text.strip()
    if text.startswith("/"): return
    uid=update.effective_user.id
    is_admin = uid in ADMIN_IDS or 0 in ADMIN_IDS

    if is_admin:
        low=text.lower()
        if low.startswith("احفظ") or low.startswith("حفظ"):
            cleaned=text
            for w in ["احفظ","حفظ",":","-"]:
                if cleaned.startswith(w):
                    cleaned=cleaned[len(w):].strip()
            if "|" in cleaned:
                q,a=cleaned.split("|",1)
                if len(q.strip())>2 and len(a.strip())>2:
                    save_knowledge(q,a)
                    await update.message.reply_text(f"تم الحفظ ✅\nس: {q.strip()}\nج: {a.strip()}")
                    return
            await update.message.reply_text("صيغة: احفظ السؤال | الجواب")
            return

        try:
            reply=call_groq("أنت مساعد ذكي حر وصديق لشادي، لهجة سعودية ودودة.", text, 700)
            await update.message.reply_text(reply)
            return
        except Exception as e:
            err=str(e)
            print(f"Groq error: {err}")
            if "decommissioned" in err:
                await update.message.reply_text("Groq حذف الموديل، جاري التحديث التلقائي... جرب مرة ثانية بعد دقيقة")
            else:
                await update.message.reply_text(f"⚠️ خطأ GROQ:\n{err[:350]}")
            return

    # زبون
    learned=load_knowledge()[-20:]
    ctx="\n".join([f"س:{x.get('q')} ج:{x.get('a')}" for x in learned])
    try:
        reply=call_groq(f"أنت بوت خرائط رحال RahalTeam.com فيديو https://youtu.be/8TEil-9tsfY لهجة سعودية مختصرة. معلومات:\n{ctx}", text, 400)
        await update.message.reply_text(reply)
    except:
        await update.message.reply_text("هلا والله حياك في خرائط رحال 🗺️\nRahalTeam.com")

def main():
    print(f"Rahal Bot Ready - Admins: {ADMIN_IDS} - Key len: {len(GROQ_KEY)}")
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("id",id_cmd))
    app.add_handler(CommandHandler("list",list_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
