import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, CallbackQueryHandler
import asyncio

# ------------------ تنظیمات ------------------
BOT_TOKEN = "8227817016:AAHL4vVYIAOBmBHun6iWhezZdyXSwJBjzY8"
CHANNEL_IDS = ["@fcxter", "@FCXTERGP"]  # کانال‌های اجباری
ADMIN_IDS = [6181430071, 5944937406]  # آیدی ادمین‌ها
کانال‌هایی که کاربر باید عضو باشد

db = {
    "users": {},  # user_id: {"points": 0, "chances": 0, "referred_by": None}
    "waiting_broadcast": False,
    "raffle": [],
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# ------------------ بررسی عضویت در کانال ------------------
async def is_user_in_channels(app, user_id):
    for ch in CHANNELS:
        try:
            member = await app.bot.get_chat_member(ch, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True


# ------------------ دکمه‌های کاربر ------------------
def get_user_buttons():
    keyboard = [
        [InlineKeyboardButton("🎟 تبدیل امتیاز به شانس", callback_data="convert_points")],
        [InlineKeyboardButton("ℹ️ اطلاعات حساب", callback_data="account_info")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ------------------ دکمه‌های مدیر ------------------
def get_admin_buttons():
    keyboard = [
        [InlineKeyboardButton("📊 آمار", callback_data="stats")],
        [InlineKeyboardButton("🎯 انتخاب برنده", callback_data="pick_winner")],
        [InlineKeyboardButton("📢 ارسال پیام به همه", callback_data="broadcast")],
        [InlineKeyboardButton("📋 لیست کاربران", callback_data="list_users")],
        [InlineKeyboardButton("🔄 ریست قرعه‌کشی", callback_data="reset_raffle")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ------------------ شروع ربات ------------------
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if user_id not in db["users"]:
        db["users"][user_id] = {"points": 0, "chances": 0, "referred_by": None}

    if user_id == ADMIN_ID:
        await update.message.reply_text("به پنل مدیریت خوش آمدید 👑", reply_markup=get_admin_buttons())
    else:
        await update.message.reply_text("به ربات قرعه‌کشی خوش آمدید!", reply_markup=get_user_buttons())


# ------------------ هندل دکمه‌ها ------------------
async def handle_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # بررسی عضویت در کانال‌ها
    if not await is_user_in_channels(context.application, user_id) and query.data not in ["stats", "broadcast", "list_users"]:
        await query.edit_message_text("🔒 برای استفاده از ربات باید در کانال‌های زیر عضو شوید:\n\n" + "\n".join(CHANNELS))
        return

    # مدیریت پنل مدیر
    if user_id == ADMIN_ID:
        if query.data == "stats":
            total_users = len(db["users"])
            registered = sum(1 for u in db["users"].values() if u["chances"] > 0)
            await query.edit_message_text(f"📊 آمار:\n\n👥 کاربران: {total_users}\n✅ ثبت‌نام کرده: {registered}", reply_markup=get_admin_buttons())

        elif query.data == "pick_winner":
            if db["raffle"]:
                winner = db["raffle"].pop(0)
                await query.edit_message_text(f"🎉 برنده: @{winner}", reply_markup=get_admin_buttons())
            else:
                await query.edit_message_text("❌ هیچ کاربری در قرعه‌کشی وجود ندارد.", reply_markup=get_admin_buttons())

        elif query.data == "broadcast":
            db["waiting_broadcast"] = True
            await query.edit_message_text("📢 لطفاً پیام خود را ارسال کنید:", reply_markup=get_admin_buttons())

        elif query.data == "list_users":
            user_list = "\n".join([f"- {uid}" for uid in db["users"].keys()]) or "هیچ کاربری وجود ندارد."
            await query.edit_message_text(f"📋 لیست کاربران:\n\n{user_list}", reply_markup=get_admin_buttons())

        elif query.data == "reset_raffle":
            db["raffle"].clear()
            for user in db["users"].values():
                user["chances"] = 0
            await query.edit_message_text("🔄 قرعه‌کشی و آمار ریست شد.", reply_markup=get_admin_buttons())

    # مدیریت پنل کاربر
    else:
        if query.data == "convert_points":
            if db["users"][user_id]["points"] >= 10:
                db["users"][user_id]["points"] -= 10
                db["users"][user_id]["chances"] += 1
                db["raffle"].append(user_id)
                await query.edit_message_text("🎟 10 امتیاز به 1 شانس تبدیل شد!", reply_markup=get_user_buttons())
            else:
                await query.edit_message_text("⚠️ امتیاز کافی ندارید!", reply_markup=get_user_buttons())

        elif query.data == "account_info":
            user = db["users"][user_id]
            await query.edit_message_text(f"ℹ️ اطلاعات حساب:\n\nامتیاز: {user['points']}\nشانس‌ها: {user['chances']}", reply_markup=get_user_buttons())


# ------------------ هندل پیام‌ها ------------------
async def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if user_id == ADMIN_ID and db["waiting_broadcast"]:
        message = update.message.text
        for uid in db["users"]:
            try:
                await context.bot.send_message(uid, f"📢 پیام مدیر:\n\n{message}")
            except:
                pass
        db["waiting_broadcast"] = False
        await update.message.reply_text("✅ پیام به همه ارسال شد.", reply_markup=get_admin_buttons())
    else:
        await update.message.reply_text("❌ دستور ناشناخته!")


# ------------------ اجرای ربات ------------------
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("ربات در حال اجراست (Polling)")
    app.run_polling()


if __name__ == "__main__":
    main()
