import os
import sqlite3
import random
import threading
from flask import Flask, request, jsonify
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ChatMemberStatus

# تنظیمات
BOT_TOKEN = "8227817016:AAHL4vVYIAOBmBHun6iWhezZdyXSwJBjzY8"
WEBHOOK_URL = "https://0kzbboy4.up.railway.app/8227817016:AAHL4vVYIAOBmBHun6iWhezZdyXSwJBjzY8"
CHANNEL_ID = "@fut180"
ADMIN_IDS = [6181430071, 5944937406]

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
conn.commit()

# Flask
flask_app = Flask(__name__)
telegram_app = None

# دکمه‌ها
def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💎 افزایش امتیاز"), KeyboardButton("👤 اطلاعات حساب")],
        [KeyboardButton("💳 تبدیل امتیاز به شانس")],
        [KeyboardButton("🎰 ثبت نام در قرعه کشی")]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎯 انتخاب برنده"), KeyboardButton("📊 آمار")]
    ], resize_keyboard=True)

# بررسی عضویت
async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception as e:
        print(f"❌ خطا در بررسی عضویت: {e}")
        return False

# هندلر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("✅ دستور /start دریافت شد")
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()

    if is_admin(user_id):
        await update.message.reply_text("👑 پنل ادمین فعال شد!", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید!", reply_markup=main_menu())

def is_admin(user_id):
    return user_id in ADMIN_IDS

# هندلر پیام‌ها
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📩 پیام جدید از {update.effective_user.id}: {update.message.text}")
    user_id = update.effective_user.id

    # اگر عضو کانال نباشه، فقط پیام عضویت بده
    if not await is_member(user_id, context):
        await update.message.reply_text("🔒 لطفاً ابتدا در کانال عضو شوید:\n" + CHANNEL_ID)
        return

    text = update.message.text
    if text == "🎰 ثبت نام در قرعه کشی":
        cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,))
        cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
        conn.commit()
        await update.message.reply_text("✅ شما در قرعه‌کشی ثبت‌نام شدید!")

    elif text == "💎 افزایش امتیاز":
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        await update.message.reply_text(f"🔗 لینک معرفی شما:\n{link}")

    elif text == "👤 اطلاعات حساب":
        cursor.execute("SELECT points, chances, is_registered FROM users WHERE user_id = ?", (user_id,))
        points, chances, reg = cursor.fetchone()
        status = "✅ ثبت‌نام شده" if reg else "❌ ثبت‌نام نشده"
        await update.message.reply_text(f"📊 امتیاز: {points}\n🎰 شانس: {chances}\nوضعیت: {status}")

# وبهوک
@flask_app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "ok", 200

@flask_app.route('/', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

# تنظیم ربات
async def setup_telegram():
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await telegram_app.bot.set_webhook(url=WEBHOOK_URL)
    print("✅ وبهوک تنظیم شد:", WEBHOOK_URL)

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    print("🚀 در حال اجرای ربات...")
    threading.Thread(target=run_flask, daemon=True).start()

    import asyncio
    asyncio.run(setup_telegram())

    while True:
        import time
        time.sleep(1)
