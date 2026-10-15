async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_PAUSED
    if update.effective_user.is_bot: return
    user_text=update.message.text or ""
    uid=str(update.effective_user.id)
    chat_type=update.effective_chat.type

    # === 1- الخاص مع الأدمن ===
    if chat_type == "private" and uid in ADMIN_IDS:
        # أ- رديت على سؤال طلب محول
        if update.message.reply_to_message and "السؤال:" in (update.message.reply_to_message.text or ""):
            orig = update.message.reply_to_message.text or ""
            m = re.search(r'السؤال:\s*(.*)', orig)
            q = m.group(1) if m else orig
            save_knowledge(f"سؤال: {q}\nجواب معتمد: {user_text}")
            cache_data.clear(); save_cache(cache_data)
            await update.message.reply_text(f"✅ حفظت جواب الطلب", reply_to_message_id=update.message.message_id)
            return
        
        # ب- كتبت احفظ بشكل واضح
        low = user_text.strip().lower()
        if low.startswith(("احفظ","تذكر","خزن")):
            clean = user_text
            for w in ["احفظ","تذكر","خزن"]: clean = clean.replace(w,"").strip()
            if clean and len(clean)>3:
                save_knowledge(clean)
                cache_data.clear(); save_cache(cache_data)
                await update.message.reply_text("✅ حفظت في الذاكرة", reply_to_message_id=update.message.message_id)
            return
        
        # ج- أي كلام ثاني في الخاص (مرحبا، كيف الحال، اريد محادثتك) -> يسولف طبيعي
        if is_trivial(user_text):
            return
        knowledge = load_knowledge()
        prompt = SYSTEM_PROMPT.format(knowledge=knowledge) + f"\n\nرسالة الأدمن في الخاص: {user_text}\nرد بود:"
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            res = model.generate_content(prompt)
            if res.text:
                await update.message.reply_text(res.text, reply_to_message_id=update.message.message_id)
        except:
            await update.message.reply_text("هلا والله، معك، وش تبي تعلمني؟", reply_to_message_id=update.message.message_id)
        return

    # === 2- القروب (الأدمن يعلم) ===
    if chat_type in ["group","supergroup"] and uid in ADMIN_IDS:
        if update.message.reply_to_message and not update.message.reply_to_message.from_user.is_bot and len(user_text)>2:
            orig = update.message.reply_to_message.text or ""
            save_knowledge(f"سؤال: {orig}\nجواب معتمد: {user_text}")
            cache_data.clear(); save_cache(cache_data)
            await update.message.reply_text("✅ تعلمت من ردك", reply_to_message_id=update.message.message_id)
            BOT_PAUSED=True; save_status(True)
            return
        if user_text.strip().lower().startswith(("احفظ","تذكر","خزن")) and len(user_text)>10:
            clean=user_text
            for w in ["احفظ","تذكر","خزن"]: clean=clean.replace(w,"").strip()
            save_knowledge(clean); cache_data.clear(); save_cache(cache_data)
            await update.message.reply_text("✅ تم الحفظ", reply_to_message_id=update.message.message_id)
            return
        if not user_text.startswith("/"):
            BOT_PAUSED=True; save_status(True); return

    # === 3- الأعضاء ===
    if BOT_PAUSED: return
    if is_trivial(user_text): return

    if is_order_question(user_text):
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=int(aid), text=f"📦 سؤال عن طلب\n\nمن: {update.effective_user.first_name}\nالسؤال: {user_text}\n\nرد على هذه الرسالة بجوابك")
            except: pass
        await update.message.reply_text("تمام، حولت استفسارك عن الطلب للأدمن بيتابع معك 📦", reply_to_message_id=update.message.message_id)
        return

    # سوالف حرة
    knowledge = load_knowledge()
    prompt = SYSTEM_PROMPT.format(knowledge=knowledge) + f"\n\nرسالة العضو: {user_text}"
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        res = model.generate_content(prompt)
        if res.text:
            await update.message.reply_text(res.text, reply_to_message_id=update.message.message_id)
    except:
        pass
