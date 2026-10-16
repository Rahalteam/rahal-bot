
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
    p=p.strip()
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
    print(f"Saved: {q} -> {a}")

def call_groq(system_prompt, user_text, max_tokens=600):
    """يحاول اكثر من موديل عشان ما يطفي"""
    if not GROQ_KEY:
        raise Exception("GROQ_API_KEY فاضي")
    from groq import Groq
    client=Groq(api_key=GROQ_KEY)
    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama3-8b-8192", "mixtral-8x7b-32768"]
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
                temperature=0.8
            )
            return comp.choices[0].message.content
        except Exception as e:
            print(f"Model {model} failed: {e}")
            last_err=e
            continue
    raise last_err

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    key_status = "موجود ✅" if GROQ_KEY else "مو موجود ❌"
    if uid in ADMIN_IDS:
        await update.message.reply_text(
            f"هلا يا شادي! 👑 ID:{uid}\n"
            f"GROQ: {key_status} ({len(GROQ_KEY)} حرف)\n\n"
            "انت في الوضع الحر - كلمني عادي\n\n"
            "عشان تحفظ:\n"
            "احفظ السؤال | الجواب\n\n"
            "مثال:\n"
            "احفظ كيف اثبت | من RahalTeam.com\n\n"
            "/list - وش حفظت\n"
            "/id - ايديك"
        )
    else:
        await update.message.reply_text("هلا والله حياك في خرائط رحال 🗺️\nRahalTeam.com")

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"ايديك: {update.effective_user.id}\nGROQ: {len(GROQ_KEY)} حرف")

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

    # ادمن
    if is_admin:
        low=text.lower()
        if low.startswith("احفظ") or low.startswith("حفظ") or low.startswith("علم"):
            cleaned=text
            for w in ["احفظ","حفظ","علم",":","-"]:
                if cleaned.startswith(w):
                    cleaned=cleaned[len(w):].strip()
            if cleaned.lower().startswith("احفظ"):
                cleaned=cleaned[4:].strip().lstrip(":").strip()
            if "|" in cleaned:
                q,a=cleaned.split("|",1)
                if len(q.strip())>2 and len(a.strip())>2:
                    save_knowledge(q,a)
                    await update.message.reply_text(f"تم الحفظ ✅\nس: {q.strip()}\nج: {a.strip()}")
                    return
            await update.message.reply_text("صيغة الحفظ: احفظ السؤال | الجواب")
            return

        # كلام حر للادمن
        try:
            reply=call_groq("أنت مساعد ذكي حر وصديق لشادي مالك خرائط رحال. لهجة سعودية ودودة، ذكي، تساعد في أي موضوع. لا تقول انك بوت خرائط رحال للادمن.", text, 700)
            await update.message.reply_text(reply)
            return
        except Exception as e:
            err=str(e)
            print(f"Groq admin error: {err}")
            await update.message.reply_text(f"⚠️ خطأ في الذكاء:\n{err[:400]}\n\nتأكد من GROQ_API_KEY في Fly Secrets (لازم يبدأ بـ gsk_ ) واعمل Start للماكينة")
            return

    # زبون
    learned=load_knowledge()[-20:]
    ctx="\n".join([f"س:{x.get('q')} ج:{x.get('a')}" for x in learned])
    try:
        reply=call_groq(f"أنت بوت خرائط رحال الرسمي RahalTeam.com فيديو https://youtu.be/8TEil-9tsfY لهجة سعودية مختصرة 2-4 اسطر. معلومات:\n{ctx}", text, 400)
        await update.message.reply_text(reply)
    except Exception as e:
        print(f"Groq customer error: {e}")
        await update.message.reply_text(f"هلا والله حياك في خرائط رحال 🗺️\nRahalTeam.com\nhttps://youtu.be/8TEil-9tsfY")

def main():
    print(f"Rahal Bot Ready - Admins: {ADMIN_IDS} - Key len: {len(GROQ_KEY)} - Free+احفظ")
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("id",id_cmd))
    app.add_handler(CommandHandler("list",list_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
