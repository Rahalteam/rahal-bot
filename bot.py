
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

# لو فيه Volume /data استخدمه عشان ما ينحذف، اذا ما فيه استخدم المحلي
if os.path.exists("/data"):
    KNOWLEDGE_FILE = "/data/knowledge/learned.json"
else:
    KNOWLEDGE_FILE = "knowledge/learned.json"

os.makedirs(os.path.dirname(KNOWLEDGE_FILE), exist_ok=True)
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
    print(f"Saved to {KNOWLEDGE_FILE}: {q} -> {a[:50]}")

def delete_knowledge(index):
    data=load_knowledge()
    if 0 <= index < len(data):
        removed = data.pop(index)
        with open(KNOWLEDGE_FILE,"w",encoding="utf-8") as f:
            json.dump(data,f,ensure_ascii=False,indent=2)
        return removed
    return None

def call_groq(system_prompt, user_text, max_tokens=500):
    if not GROQ_KEY:
        raise Exception("GROQ_API_KEY فاضي")
    from groq import Groq
    client=Groq(api_key=GROQ_KEY)
    models = [
        "openai/gpt-oss-20b",
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "gemma2-9b-it",
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
            return comp.choices[0].message.content
        except Exception as e:
            print(f"Model {model} failed: {e}")
            last_err=e
            if "decommissioned" in str(e).lower() or "401" in str(e):
                continue
    raise last_err

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    count=len(load_knowledge())
    is_vol = "✅ Volume شغال" if "/data" in KNOWLEDGE_FILE else "⚠️ بدون Volume"
    if uid in ADMIN_IDS:
        await update.message.reply_text(
            f"هلا يا شادي! 👑\nID:{uid}\n{is_vol}\nمحفوظات: {count}\n\n"
            "انت في الخاص - تقدر تعلمني أي شي\n\n"
            "طريقة التعليم:\n"
            "احفظ السؤال | الجواب\n\n"
            "أمثلة:\n"
            "احفظ كم السعر | 50 ريال\n"
            "احفظ كيف اثبت | من RahalTeam.com\n"
            "احفظ رابط التحميل | RahalTeam.com/download\n\n"
            "الأوامر:\n"
            "/list - وش حفظت\n"
            "/del رقم - حذف معلومة\n"
            "/clear - مسح الكل\n"
            "/export - تصدير كل شي\n\n"
            "تقدر تعلمني 500 معلومة وكلها محفوظة للأبد!"
        )
    else:
        await update.message.reply_text("هلا والله حياك في خرائط رحال 🗺️\nRahalTeam.com")

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"ايديك: {update.effective_user.id}\nالملف: {KNOWLEDGE_FILE}")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    if uid not in ADMIN_IDS and 0 not in ADMIN_IDS: return
    data=load_knowledge()
    if not data:
        await update.message.reply_text("ما حفظت شي لسه")
        return
    # آخر 25
    recent=data[-25:]
    txt="\n\n".join([f"{len(data)-len(recent)+i+1}. س:{x['q']}\nج:{x['a'][:150]}" for i,x in enumerate(recent)])
    await update.message.reply_text(f"محفوظ {len(data)}/500 - آخر 25:\n\n{txt}\n\nاحذف بـ /del رقم")

async def del_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    if uid not in ADMIN_IDS and 0 not in ADMIN_IDS: return
    args=context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("استخدم: /del رقم\nمثال /del 5")
        return
    idx=int(args[0])-1
    removed=delete_knowledge(idx)
    if removed:
        await update.message.reply_text(f"تم الحذف 🗑️\n{removed['q']}")
    else:
        await update.message.reply_text("رقم غلط")

async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    if uid not in ADMIN_IDS: return
    with open(KNOWLEDGE_FILE,"w",encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False)
    await update.message.reply_text("تم مسح كل شي 🗑️")

async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    if uid not in ADMIN_IDS: return
    data=load_knowledge()
    if not data:
        await update.message.reply_text("فاضي")
        return
    txt="\n\n".join([f"س: {x['q']}\nج: {x['a']}\n---" for x in data])
    # ارسل كملف لو كبير
    if len(txt) > 3500:
        path="/tmp/export.txt"
        with open(path,"w",encoding="utf-8") as f:
            f.write(txt)
        await update.message.reply_document(document=open(path,"rb"), filename="rahal_knowledge.txt")
    else:
        await update.message.reply_text(txt)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text=update.message.text.strip()
    if text.startswith("/"): return
    uid=update.effective_user.id
    is_admin = uid in ADMIN_IDS or 0 in ADMIN_IDS

    # === الادمن - الخاص ===
    if is_admin:
        low=text.lower()
        # تعليم
        if low.startswith("احفظ") or low.startswith("حفظ") or low.startswith("علم"):
            cleaned=text
            for w in ["احفظ","حفظ","علم",":","-"]:
                if cleaned.startswith(w):
                    cleaned=cleaned[len(w):].strip()
            if low.startswith("احفظ") and cleaned.lower().startswith("احفظ"):
                cleaned=cleaned[4:].strip().lstrip(":").strip()
            if "|" in cleaned:
                q,a=cleaned.split("|",1)
                if len(q.strip())>1 and len(a.strip())>1:
                    save_knowledge(q,a)
                    await update.message.reply_text(f"تم الحفظ ✅\n📚 العدد: {len(load_knowledge())}/500\n\nس: {q.strip()}\nج: {a.strip()[:300]}")
                    return
            await update.message.reply_text("صيغة التعليم:\nاحفظ السؤال | الجواب\n\nمثال:\nاحفظ كيف اثبت | ادخل RahalTeam.com")
            return

        # كلام حر ذكي للادمن
        try:
            reply=call_groq("أنت مساعد ذكي حر وصديق لشادي مالك خرائط رحال. سعودي ودود، ذكي، تساعد في أي موضوع بحرية. لا تقول انك بوت خرائط.", text, 800)
            await update.message.reply_text(reply)
            return
        except Exception as e:
            await update.message.reply_text(f"⚠️ خطأ: {str(e)[:300]}")
            return

    # === الزبون - ذكي + من اللي علمته ===
    learned=load_knowledge()
    # ناخذ آخر 40 معلومة مهمة
    recent = learned[-40:] if len(learned) > 40 else learned
    ctx="\n".join([f"- س: {x.get('q')} => ج: {x.get('a')}" for x in recent])

    system = f"""أنت بوت خرائط رحال الرسمي RahalTeam.com ذكي جدا.
لهجة سعودية ودودة مختصرة 2-4 أسطر.
فيديو الشرح: https://youtu.be/8TEil-9tsfY

معلومات تعلمتها من شادي (استخدمها أولاً إذا السؤال عنها):
{ctx}

تعليمات:
- إذا السؤال موجود في المعلومات أعلاه، جاوب منه حرفيا
- إذا السؤال جديد، جاوب بذكائك كمساعد خرائط رحال
- لا تقول "ما أعرف" - حاول تساعد
- اذكر RahalTeam.com دائما
"""

    try:
        reply=call_groq(system, text, 500)
        await update.message.reply_text(reply)
    except Exception as e:
        print(f"Customer error: {e}")
        await update.message.reply_text("هلا والله حياك في خرائط رحال 🗺️\nRahalTeam.com\nhttps://youtu.be/8TEil-9tsfY")

def main():
    vol_status = "WITH VOLUME /data" if "/data" in KNOWLEDGE_FILE else "NO VOLUME"
    print(f"Rahal Bot Ready - {vol_status} - Admins: {ADMIN_IDS} - Count: {len(load_knowledge())} - File: {KNOWLEDGE_FILE}")
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("id",id_cmd))
    app.add_handler(CommandHandler("list",list_cmd))
    app.add_handler(CommandHandler("del",del_cmd))
    app.add_handler(CommandHandler("clear",clear_cmd))
    app.add_handler(CommandHandler("export",export_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__": main()
