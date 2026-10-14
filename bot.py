import os
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# المفاتيح بنجيبها من متغيرات البيئة في Koyeb - لا تحطها هنا
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@Rahalteam2_bot")

# إعداد Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="انت خبير في تطبيق OsmAnd للخرائط. مجموعتنا اسمها مناقشات خرائط رحال. جاوب بالعربي السعودي باختصار ومفيد جداً. اشرح خطوات عملية واضحة. اذا السؤال ليس عن الخرائط جاوب بشكل عام ومفيد."
)

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    chat_type = update.message.chat.type
    
    # في الخاص: رد على كل شيء. في المجموعة: رد فقط اذا انذكر او سؤال
    if chat_type != "private":
        is_mentioned = BOT_USERNAME.lower() in text.lower() if BOT_USERNAME else False
        is_reply_to_bot = False
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            username = update.message.reply_to_message.from_user.username or ""
            is_reply_to_bot = username.lower() == BOT_USERNAME.replace("@","").lower()
        
        is_question = any(k in text for k in ["؟", "كيف", "OsmAnd", "خريطة", "مسار", "osm", "رسم", "تنزيل"])
        if not (is_mentioned or is_reply_to_bot or is_question):
            return

    try:
        response = model.generate_content(text)
        # تيليجرام بسمح 4096 حرف فقط
        await update.message.reply_text(response.text[:4000])
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("صار ضغط شوي على السيرفر، ارجع اسأل بعد ثانية.")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    print("خطأ: لازم تحط TELEGRAM_TOKEN و GEMINI_API_KEY في Environment variables في Koyeb")
else:
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print(f"البوت {BOT_USERNAME} شغال...")
    app.run_polling()
