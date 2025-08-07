import sqlite3
import random
import requests
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = "8227817016:AAGwqzCfx6abijss3ksZyju1ifXHLJ1lNCw"
ADMIN_IDS = [6181430071, 5944937406]

# حذف وبهوک قبل از شروع Polling
requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")

# دیتابیس
conn = sqlite3.connect("raffle.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    chances INTEGER DEFAULT 0,
    is_registered INTEGER DEFAULT 0
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS raffle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS join_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT
)""")

# افزودن کانال پیش‌فرض اگر خالی بود
cursor.execute("SELECT COUNT(*) FROM join_channels")
if cursor.fetchone()[0] == 0:
    cursor.execute("INSERT INTO join_channels (channel) VALUES (?)", ("@fcxter",))
    cursor.execute("INSERT INTO join_channels (channel) VALUES (?)", ("@FCXTERGP",))
conn.commit()

def main_menu():
    return ReplyKeyboardMarkup([
        ["💎 افزایش امتیاز", "👤 اطلاعات حساب"],
        ["💳 تبدیل امتیاز به شانس", "🎰 ثبت نام در قرعه کشی"]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        ["🎯 انتخاب برنده", "📊 آمار"],
        ["📢 ارسال پیام به همه", "📋 لیست کاربران"],
        ["➕ افزودن کانال جوین اجباری", "🔄 ریست قرعه‌کشی"]
    ], resize_keyboard=True)

async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT channel FROM join_channels")
    channels = cursor.fetchall()
    not_joined = []

    for (channel,) in channels:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                not_joined.append(channel)
        except:
            not_joined.append(channel)

    return not_joined

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username or user.first_name))
    conn.commit()
    if user.id in ADMIN_IDS:
        await update.message.reply_text("👑 به پنل مدیریت خوش آمدید!", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید!", reply_markup=main_menu())

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    not_joined = await is_member(query.from_user.id, context)
    if not not_joined:
        await query.edit_message_text("✅ با موفقیت عضو شدید، حالا از منو استفاده کنید.")
    else:
        await send_join_message(query.message, context, query.from_user.id)

async def send_join_message(message, context, user_id):
    not_joined = await is_member(user_id, context)
    if not_joined:
        keyboard = [[InlineKeyboardButton(f"عضویت در {ch}", url=f"https://t.me/{ch[1:]}")] for ch in not_joined]
        keyboard.append([InlineKeyboardButton("🔄 بررسی عضویت", callback_data="check_join")])
        markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text("🔒 برای استفاده از ربات باید در کانال‌های زیر عضو شوید:", reply_markup=markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username

    if user_id in ADMIN_IDS:
        if text == "📊 آمار":
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered = 1")
            registered = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM raffle")
            total_chances = cursor.fetchone()[0]
            await update.message.reply_text(f"📊 آمار:\n👥 کاربران: {total_users}\n🎰 شرکت‌کنندگان: {registered}\n🎟️ شانس‌ها: {total_chances}")
        elif text == "📋 لیست کاربران":
            cursor.execute("SELECT username FROM users")
            users = cursor.fetchall()
            names = "\n".join([f"@{u[0]}" if u[0] else "بدون نام" for u in users])
            await update.message.reply_text(f"📋 لیست کاربران:\n\n{names[:4000]}")
        elif text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            participants = cursor.fetchall()
            if not participants:
                await update.message.reply_text("❌ کسی در قرعه‌کشی نیست.")
            else:
                winner_id = random.choice(participants)[0]
                cursor.execute("SELECT username FROM users WHERE user_id = ?", (winner_id,))
                result = cursor.fetchone()
                winner_name = f"@{result[0]}" if result and result[0] else f"User {winner_id}"
                await update.message.reply_text(f"🏆 برنده قرعه‌کشی: {winner_name}")
                try:
                    await context.bot.send_message(winner_id, "🎉 تبریک! شما برنده قرعه‌کشی شدید!")
                except:
                    pass
        elif text == "📢 ارسال پیام به همه":
            context.user_data["broadcast"] = True
            await update.message.reply_text("پیام خود را ارسال کنید:")
        elif context.user_data.get("broadcast"):
            cursor.execute("SELECT user_id FROM users")
            for (uid,) in cursor.fetchall():
                try:
                    await context.bot.forward_message(uid, update.effective_chat.id, update.message.message_id)
                except:
                    pass
            context.user_data["broadcast"] = False
            await update.message.reply_text("✅ ارسال شد.")
        elif text == "🔄 ریست قرعه‌کشی":
            cursor.execute("DELETE FROM raffle")
            cursor.execute("UPDATE users SET is_registered = 0, chances = 0")
            conn.commit()
            await update.message.reply_text("♻️ ریست شد.")
        elif text == "➕ افزودن کانال جوین اجباری":
            context.user_data["awaiting_channel"] = True
            await update.message.reply_text("لطفاً آیدی کانال با @ وارد کن.")
        elif context.user_data.get("awaiting_channel"):
            if text.startswith("@"):
                cursor.execute("INSERT INTO join_channels (channel) VALUES (?)", (text,))
                conn.commit()
                await update.message.reply_text("✅ اضافه شد.")
                context.user_data["awaiting_channel"] = False
            else:
                await update.message.reply_text("⚠️ آیدی باید با @ شروع شود.")
    else:
        not_joined = await is_member(user_id, context)
        if not_joined:
            await send_join_message(update.message, context, user_id)
            return
        if text == "🎰 ثبت نام در قرعه کشی":
            cursor.execute("SELECT is_registered FROM users WHERE user_id = ?", (user_id,))
            if cursor.fetchone()[0]:
                await update.message.reply_text("⚠️ قبلاً ثبت نام کرده‌اید.")
            else:
                cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,))
                cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
                conn.commit()
                await update.message.reply_text("✅ ثبت نام شدید.")
        elif text == "💎 افزایش امتیاز":
            link = f"https://t.me/{context.bot.username}?start={user_id}"
            await update.message.reply_text(f"🔗 لینک دعوت شما:\n{link}")
        elif text == "💳 تبدیل امتیاز به شانس":
            cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
            points = cursor.fetchone()[0]
            if points > 0:
                cursor.execute("UPDATE users SET points = 0, chances = chances + ? WHERE user_id = ?", (points, user_id))
                for _ in range(points):
                    cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
                conn.commit()
                await update.message.reply_text(f"✅ {points} امتیاز به شانس تبدیل شد.")
            else:
                await update.message.reply_text("⚠️ امتیازی ندارید.")
        elif text == "👤 اطلاعات حساب":
            cursor.execute("SELECT username, points, chances, is_registered FROM users WHERE user_id = ?", (user_id,))
            u, p, c, r = cursor.fetchone()
            status = "✅ ثبت‌نام شده" if r else "❌ ثبت‌نام نشده"
            await update.message.reply_text(f"👤 @{u}\n🎯 وضعیت: {status}\n💎 امتیاز: {p}\n🎟️ شانس: {c}")

# راه‌اندازی ربات
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
app.add_handler(MessageHandler(filters.ALL, handle_message))

print("🤖 ربات فعال است...")
app.run_polling()
