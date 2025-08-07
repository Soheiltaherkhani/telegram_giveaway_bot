import sqlite3
import random
import requests
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8227817016:AAGwqzCfx6abijss3ksZyju1ifXHLJ1lNCw"

requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")

ADMIN_IDS = [6181430071, 5944937406]

conn = sqlite3.connect("raffle.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    chances INTEGER DEFAULT 0,
    is_registered INTEGER DEFAULT 0,
    referred_by INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS raffle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT
)
""")
conn.commit()

def main_menu():
    return ReplyKeyboardMarkup([
        ["💎 افزایش امتیاز", "👤 اطلاعات حساب"],
        ["💳 تبدیل امتیاز به شانس", "🎰 ثبت نام در قرعه کشی"],
        ["🏆 لیدربورد"]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        ["🎯 انتخاب برنده", "📊 آمار"],
        ["📢 ارسال پیام به همه", "📋 لیست کاربران"],
        ["➕ افزودن کانال", "📋 لیست کانال‌های جوین اجباری"],
        ["❌ حذف کانال جوین اجباری", "🔄 ریست قرعه‌کشی"],
        ["🏆 لیدربورد"]
    ], resize_keyboard=True)

async def is_member(user_id, context):
    cursor.execute("SELECT username FROM channels")
    channels = cursor.fetchall()
    for ch in channels:
        try:
            member = await context.bot.get_chat_member(ch[0], user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referred_by = None

    if context.args:
        try:
            referred_by = int(context.args[0])
        except:
            pass

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user.id,))
    exists = cursor.fetchone()

    if not exists:
        cursor.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
                       (user.id, user.username or user.first_name, referred_by))
        if referred_by:
            cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (referred_by,))
            try:
                await context.bot.send_message(referred_by, f"🎉 یک نفر با لینک شما وارد شد و 1 امتیاز گرفتید!")
            except:
                pass
    conn.commit()

    if user.id in ADMIN_IDS:
        await update.message.reply_text("👑 به پنل مدیریت خوش آمدید!", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید!", reply_markup=main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if user_id in ADMIN_IDS:
        pass
    else:
        if not await is_member(user_id, context):
            cursor.execute("SELECT username FROM channels")
            channels = cursor.fetchall()
            buttons = [[InlineKeyboardButton(f"عضویت در {ch[0]}", url=f"https://t.me/{ch[0][1:]}")] for ch in channels]
            markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(
                "🔒 برای استفاده از ربات باید در کانال‌های زیر عضو شوید:", reply_markup=markup
            )
            return

        if text == "🎰 ثبت نام در قرعه کشی":
            cursor.execute("SELECT is_registered FROM users WHERE user_id = ?", (user_id,))
            if cursor.fetchone()[0]:
                await update.message.reply_text("⚠️ شما قبلاً ثبت‌نام کرده‌اید.")
            else:
                cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,))
                cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
                conn.commit()
                await update.message.reply_text("✅ شما در قرعه‌کشی ثبت‌نام شدید!")

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
                await update.message.reply_text(f"✅ {points} امتیاز شما به شانس تبدیل شد!")
            else:
                await update.message.reply_text("⚠️ شما امتیازی ندارید.")

        elif text == "👤 اطلاعات حساب":
            cursor.execute("SELECT username, points, chances, is_registered FROM users WHERE user_id = ?", (user_id,))
            username, points, chances, is_registered = cursor.fetchone()
            status = "✅ ثبت‌نام شده" if is_registered else "❌ ثبت‌نام نشده"
            await update.message.reply_text(
                f"📊 اطلاعات شما:\n👤 کاربر: @{username}\n🎯 وضعیت: {status}\n💎 امتیاز: {points}\n🎟️ شانس: {chances}"
            )

        elif text == "🏆 لیدربورد":
            cursor.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT 10")
            rows = cursor.fetchall()
            board = "🏆 برترین کاربران:\n\n" + "\n".join([f"{i+1}. @{row[0]} - {row[1]} امتیاز" for i, row in enumerate(rows)])
            await update.message.reply_text(board)

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🤖 ربات در حال اجراست...")
app.run_polling()
