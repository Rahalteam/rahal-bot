
import os, json
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")

# يفهم فاصلة ومسافات
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    if uid in ADMIN_IDS:
        await update.message.reply_text(
            f"هلا يا شادي! 👑 ID:{uid}\n\n"
            "انت في الوضع الحر - كلمني عادي بأي شي\n\n"
            "عشان تحفظ معلومة للزباين اكتب:\n"
            "احفظ السؤال | الجواب\n\n"
            "مثال:\n"
            "احفظ كيف اثبت الخريطة | ادخل RahalTeam.com وحمل الملف\n\n"
            "اوامر:\n"
            "/list - تشوف وش حفظت\n"
            "/id - ايديك"
        )
    else:
        await update.message.reply_text("هلا والله حياك في خرائط رحال 🗺️\nRahalTeam.com\nوش ودك تعرف؟")

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
    await update.message.reply_text(f"آخر 20 معلومة حفظتها:\n\n{txt}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text=update.message.text.strip()
    if text.startswith("/"): return

    uid=update.effective_user.id
    is_admin = uid in ADMIN_IDS or 0 in ADMIN_IDS

    # ============ وضع الادمن - حر + حفظ بكلمة احفظ ============
    if is_admin:
        lower = text.lower()

        # اذا قال احفظ
        if lower.startswith("احفظ") or lower.startswith("حفظ") or lower.startswith("علم"):
            # شيل كلمة احفظ
            cleaned = text
            for w in ["احفظ","حفظ","علم",":","-"]:
                if cleaned.startswith(w):
                    cleaned = cleaned[len(w):].strip()
            # اذا لسه يبدأ ب احفظ مرة ثانية (احفظ احفظ)
            if cleaned.lower().startswith("احفظ"):
                cleaned = cleaned[4:].strip().lstrip(":").strip()

            if "|" in cleaned and len(cleaned.split("|",1))==2:
                q,a = cleaned.split("|",1)
                if len(q.strip())>2 and len(a.strip())>2:
                    save_knowledge(q,a)
                    await update.message.reply_text(f"تم الحفظ ✅\n\nس: {q.strip()}\nج: {a.strip()}\n\nالزباين الحين بيستفيدون منه")
                    return
                else:
                    await update.message.reply_text("اكتبها صح: احفظ السؤال | الجواب\nمثال: احفظ كيف احمل | من RahalTeam.com")
                    return
            else:
                await update.message.reply_text("اكتب بعد احفظ: السؤال | الجواب\n\nمثال:\nاحفظ كيف اثبت الخريطة | ادخل RahalTeam.com")
                return

        # كلام حر مع الادمن
        if GROQ_KEY:
            try:
                from groq import Groq
                client=Groq(api_key=GROQ_KEY)
                comp=client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role":"system","content":"أنت مساعد ذكي حر وصديق لشادي، مالك خرائط رحال. تكلم بلهجة سعودية ودودة، ذكي، تفهم، تساعد في أي موضوع. انت تتعلم من شادي عشان تجاوب الزباين بعدين. لا تقول انك بوت خرائط رحال للادمن، انت صديقه الحر."},
                        {"role":"user","content":text}
                    ],
                    max_tokens=700,
                    temperature=0.85
                )
                await update.message.reply_text(comp.choices[0].message.content)
                return
            except Exception as e:
                print(f"Groq admin error: {e}")

    # ============ وضع الزبون ============
    learned=load_knowledge()[-20:]
    ctx="\n".join([f"س:{x.get('q')} ج:{x.get('a')}" for x in learned])

    if GROQ_KEY:
        try:
            from groq import Groq
            client=Groq(api_key=GROQ_KEY)
            comp=client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role":"system","content":f"أنت مساعد خرائط رحال الرسمي. اسمك رحال. لهجتك سعودية ودودة ومختصرة 2-4 اسطر. موقعك RahalTeam.com وفيديو الشرح https://youtu.be/8TEil-9tsfY لا ترسل الرابط الا اذا سأل عن التثبيت. استخدم المعلومات المحفوظة:\n{ctx}"},
                    {"role":"user","content":text}
                ],
                max_tokens=400,
                temperature=0.6
            )
            await update.message.reply_text(comp.choices[0].message.content)
            return
        except Exception as e:
            print(f"Groq customer error: {e}")

    await update.message.reply_text(f"هلا والله حياك في خرائط رحال 🗺️\n{ctx[:200]}\n\nRahalTeam.com")

def main():
    print(f"Rahal Bot Ready - Admins: {ADMIN_IDS} - Free Talk + احفظ")
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("id",id_cmd))
    app.add_handler(CommandHandler("list",list_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
