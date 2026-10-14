async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED = False
    save_status(False)
    await update.message.reply_text("🔔 اشتغلت ورجعت أرد على الكل")

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if str(update.effective_user.id) not in ADMIN_IDS: return
    BOT_PAUSED = True
    save_status(True)
    await update.message.reply_text("🔕 وقفت، ما راح أرد على أي أحد لين تكتب /on")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    user_text = update.message.text or ""
    uid = str(update.effective_user.id)
    chat_type = update.effective_chat.type

    # إذا البوت موقف، ما يرد على أي أحد إلا على أمر /on من الأدمن
    if BOT_PAUSED:
        return

    # إذا الأدمن تدخل في القروب، وقف البوت تلقائياً
    if chat_type in ["group", "supergroup"] and uid in ADMIN_IDS:
        if any(w in user_text for w in ["احفظ","تذكر","خزن"]):
            clean = user_text
            for w in ["احفظ","تذكر","خزن"]: clean = clean.replace(w,"").strip()
            if clean:
                save_knowledge(clean)
                cache_data.clear(); save_cache(cache_data)
                await update.message.reply_text("✅ تم الحفظ")
            return
        if user_text.startswith("/on") or user_text.startswith("/off"):
            return
        # أي تدخل عادي منك = إيقاف تلقائي
        BOT_PAUSED = True
        save_status(True)
        return

    # في القروب ما يرد إلا بمنشن توفيراً للرسائل
    if chat_type in ["group", "supergroup"]:
        is_mention = f"@{context.bot.username}" in user_text
        is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
        if not (is_mention or is_reply):
            return

    # ... باقي كود الرد والكاش نفسه
