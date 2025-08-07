import sqlite3
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, InputMediaVideo
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

BOT_TOKEN = "8227817016:AAFaI1J3KPn-8WCrXl2MsvPtKTYoDL4TINo"
ADMIN_IDS = [6181430071, 5944937406]

# --- Database ---
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    chances INTEGER DEFAULT 0,
    registered INTEGER DEFAULT 0,
    ref_by INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE
)
""")

conn.commit()

# --- Helper Functions ---
def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()

def add_user(user_id, username, ref_by=None):
    if not get_user(user_id):
        cursor.execute("INSERT INTO users (user_id, username, ref_by) VALUES (?, ?, ?)", (user_id, username, ref_by))
        conn.commit()

def get_channels():
    cursor.execute("SELECT username FROM channels")
    return [row[0] for row in cursor.fetchall()]

def user_in_channels(user_id, context: ContextTypes.DEFAULT_TYPE):
    async def check():
        for ch in get_channels():
            try:
                member = await context.bot.get_chat_member(ch, user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    return False
            except:
                return False
        return True
    return check

# --- Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ref = None
    if context.args:
        try:
            ref = int(context.args[0])
        except:
            pass

    add_user(user.id, user.username or "", ref)

    if not await user_in_channels(user.id, context)():
        buttons = [[InlineKeyboardButton(f"عضویت در {ch}", url=f"https://t.me/{ch}")] for ch in get_channels()]
        await update.message.reply_text("🔒 برای استفاده از ربات باید در کانال‌های زیر عضو شوید:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    await update.message.reply_text("به ربات قرعه‌کشی خوش آمدید!\n\nاز منوی زیر استفاده کنید.", reply_markup=main_menu())

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 ثبت‌نام در قرعه‌کشی", callback_data="register")],
        [InlineKeyboardButton("💎 افزایش امتیاز", callback_data="referral")],
        [InlineKeyboardButton("🎲 تبدیل امتیاز به شانس", callback_data="convert")],
        [InlineKeyboardButton("📊 لیدربورد", callback_data="leaderboard")],
        [InlineKeyboardButton("ℹ️ حساب من", callback_data="account")],
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 پیام همگانی", callback_data="broadcast")],
        [InlineKeyboardButton("📋 لیست کانال‌های اجباری", callback_data="list_channels")],
        [InlineKeyboardButton("➕ افزودن کانال", callback_data="add_channel")],
        [InlineKeyboardButton("➖ حذف کانال", callback_data="remove_channel")],
    ])

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or ""

    if not get_user(user_id):
        add_user(user_id, username)

    if query.data == "register":
        cursor.execute("SELECT registered FROM users WHERE user_id=?", (user_id,))
        reg = cursor.fetchone()[0]
        if reg:
            await query.edit_message_text("✅ شما قبلاً در قرعه‌کشی ثبت‌نام کرده‌اید.")
        else:
            cursor.execute("UPDATE users SET registered=1, chances=chances+1 WHERE user_id=?", (user_id,))
            conn.commit()
            await query.edit_message_text("🎉 شما با موفقیت در قرعه‌کشی ثبت‌نام کردید.")

    elif query.data == "referral":
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        await query.edit_message_text(f"🔗 لینک دعوت شما:\n{link}\n\nبه ازای هر دعوت، ۱ امتیاز دریافت می‌کنید.")

    elif query.data == "convert":
        cursor.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        points = cursor.fetchone()[0]
        if points > 0:
            cursor.execute("UPDATE users SET chances=chances+?, points=0 WHERE user_id=?", (points, user_id))
            conn.commit()
            await query.edit_message_text(f"✅ {points} امتیاز به شانس تبدیل شد.")
        else:
            await query.edit_message_text("❌ شما امتیازی برای تبدیل ندارید.")

    elif query.data == "account":
        cursor.execute("SELECT points, chances, registered FROM users WHERE user_id=?", (user_id,))
        p, c, r = cursor.fetchone()
        reg_status = "✅ ثبت‌نام شده" if r else "❌ ثبت‌نام نشده"
        await query.edit_message_text(f"""
🔹 یوزرنیم: @{username}
🔸 امتیاز: {p}
🔸 شانس: {c}
🔸 وضعیت ثبت‌نام: {reg_status}
        """.strip())

    elif query.data == "leaderboard":
        cursor.execute("SELECT username, chances FROM users ORDER BY chances DESC LIMIT 10")
        rows = cursor.fetchall()
        if rows:
            text = "🏆 لیدربورد بر اساس شانس:\n\n"
            for i, (u, c) in enumerate(rows, 1):
                text += f"{i}. @{u or '---'} - {c} شانس\n"
            await query.edit_message_text(text)
        else:
            await query.edit_message_text("❌ هیچ کاربری یافت نشد.")

    elif is_admin(user_id):
        if query.data == "broadcast":
            context.user_data["awaiting_broadcast"] = True
            await query.edit_message_text("لطفاً پیام (متن، عکس یا ویدیو) را ارسال کنید.")

        elif query.data == "add_channel":
            context.user_data["awaiting_channel"] = "add"
            await query.edit_message_text("لطفاً یوزرنیم کانال را با @ ارسال کنید.")

        elif query.data == "remove_channel":
            context.user_data["awaiting_channel"] = "remove"
            await query.edit_message_text("لطفاً یوزرنیم کانالی که می‌خواهید حذف کنید را ارسال کنید.")

        elif query.data == "list_channels":
            chs = get_channels()
            if chs:
                await query.edit_message_text("📋 کانال‌های اجباری:\n" + "\n".join([f"@{c}" for c in chs]))
            else:
                await query.edit_message_text("❌ هیچ کانالی ثبت نشده است.")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_broadcast"):
        context.user_data["awaiting_broadcast"] = False
        cursor.execute("SELECT user_id FROM users")
        all_users = cursor.fetchall()

        media = None
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            caption = update.message.caption or ""
            media = InputMediaPhoto(media=file_id, caption=caption)
        elif update.message.video:
            file_id = update.message.video.file_id
            caption = update.message.caption or ""
            media = InputMediaVideo(media=file_id, caption=caption)
        elif update.message.text:
            media = update.message.text

        for (uid,) in all_users:
            try:
                if isinstance(media, str):
                    await context.bot.send_message(uid, media)
                else:
                    await context.bot.send_media_group(uid, [media])
            except:
                continue
        await update.message.reply_text("✅ پیام همگانی ارسال شد.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "awaiting_channel" in context.user_data:
        action = context.user_data.pop("awaiting_channel")
        ch_username = update.message.text.strip().lstrip("@")
        if not ch_username:
            await update.message.reply_text("❌ لطفاً یوزرنیم معتبر ارسال کنید.")
            return

        if action == "add":
            try:
                cursor.execute("INSERT OR IGNORE INTO channels (username) VALUES (?)", (ch_username,))
                conn.commit()
                await update.message.reply_text(f"✅ کانال @{ch_username} اضافه شد.")
            except:
                await update.message.reply_text("❌ خطا در افزودن کانال.")
        elif action == "remove":
            cursor.execute("DELETE FROM channels WHERE username=?", (ch_username,))
            conn.commit()
            await update.message.reply_text(f"✅ کانال @{ch_username} حذف شد.")

# --- Main ---
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.TEXT, handle_media))

print("Bot is running...")
app.run_polling()
