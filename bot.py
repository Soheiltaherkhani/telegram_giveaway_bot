import os
import sqlite3
import random
import threading
import time
from flask import Flask, request, jsonify
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ChatMemberStatus

# --- تنظیمات ---
BOT_TOKEN = "8227817016:AAHL4vVYIAOBmBHun6iWhezZdyXSwJBzY8"
WEBHOOK_URL = "https://0kzbboy4.up.railway.app"
CHANNEL_ID = "@fcxter"
ADMIN_IDS = [6181430071, 5944937406]

# --- دیتابیس ---
conn = sqlite3.connect("raffle.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    chances INTEGER DEFAULT 0,
    is_registered INTEGER DEFAULT 0
)""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS raffle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER
)""")
conn.commit()

# --- منو ---
def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💎 افزایش امتیاز"), KeyboardButton("👤 اطلاعات حساب")],
        [KeyboardButton("💳 تبدیل امتیاز به شانس")],
        [KeyboardButton("🎰 ثبت نام در قرعه کشی")],
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎯 انتخاب برنده"), KeyboardButton("👥 انتخاب چند برنده")],
        [KeyboardButton("📢 ارسال پیام به همه"), KeyboardButton("📊 آمار")],
        [KeyboardButton("🔄 ریست قرعه‌کشی")],
    ], resize_keyboard=True)

# --- بررسی عضویت ---
async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except:
        return False

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# --- هندلر /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    uname = user.username or user.first_name

    # ثبت کاربر در دیتابیس
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (uid, uname))
    conn.commit()

    # نمایش منو (بدون توجه به عضویت)
    if is_admin(uid):
        await update.message.reply_text("👑 پنل مدیریت فعال شد!", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید!", reply_markup=main_menu())

# --- هندلر پیام‌ها ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id

    # بررسی عضویت
    if not await is_member(uid, context):
        kb = [[InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
        await update.message.reply_text(
            f"❌ لطفاً ابتدا در کانال {CHANNEL_ID} عضو شوید.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # کاربران عادی
    if not is_admin(uid):
        if text == "🎰 ثبت نام در قرعه کشی":
            cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (uid,))
            cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (uid,))
            conn.commit()
            await update.message.reply_text("✅ شما ثبت‌نام شدید!")
        elif text == "💎 افزایش امتیاز":
            link = f"https://t.me/{context.bot.username}?start={uid}"
            await update.message.reply_text(f"🔗 لینک شما:\n{link}")
        elif text == "💳 تبدیل امتیاز به شانس":
            cursor.execute("SELECT points FROM users WHERE user_id = ?", (uid,))
            pts = cursor.fetchone()[0]
            if pts > 0:
                cursor.execute("UPDATE users SET points = 0, chances = chances + ? WHERE user_id = ?", (pts, uid))
                for _ in range(pts):
                    cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (uid,))
                conn.commit()
                await update.message.reply_text(f"✅ {pts} امتیاز به شانس تبدیل شد!")
            else:
                await update.message.reply_text("⚠️ امتیازی ندارید.")
        elif text == "👤 اطلاعات حساب":
            cursor.execute("SELECT points, chances, is_registered FROM users WHERE user_id = ?", (uid,))
            pts, ch, reg = cursor.fetchone()
            await update.message.reply_text(
                f"📊 ثبت‌نام: {'✅' if reg else '❌'}\nامتیاز: {pts}\nشانس: {ch}"
            )

    # ادمین‌ها
    else:
        if text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            parts = [r[0] for r in cursor.fetchall()]
            if not parts:
                await update.message.reply_text("⚠️ کسی ثبت‌نام نکرده.")
            else:
                w = random.choice(parts)
                cursor.execute("SELECT username FROM users WHERE user_id = ?", (w,))
                un = cursor.fetchone()[0]
                await update.message.reply_text(f"🎉 برنده: @{un}")
        elif text == "📊 آمار":
            cursor.execute("SELECT COUNT(*) FROM users"); total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered = 1"); reg = cursor.fetchone()[0]
            await update.message.reply_text(f"📊 کاربران: {total}\nثبت‌نامی‌ها: {reg}")
        elif text == "🔄 ریست قرعه‌کشی":
            cursor.execute("DELETE FROM raffle"); conn.commit()
            await update.message.reply_text("✅ ریست شد.")

# --- referral ---
async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        rid = int(context.args[0])
        uid = update.effective_user.id
        if rid != uid:
            cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (rid,))
            conn.commit()
            try:
                await context.bot.send_message(rid, "🎉 یک نفر با لینک شما وارد شد!")
            except:
                pass
    await start(update, context)

# --- Flask & Webhook ---
flask_app = Flask(__name__)
telegram_app = None

@flask_app.route("/", methods=["GET"])
def health(): return jsonify({"status":"ok"}), 200

@flask_app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "ok", 200

async def setup_bot():
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", handle_referral))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    print(f"[INFO] وب‌هوک ثبت شد: {WEBHOOK_URL}/{BOT_TOKEN}")

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))

if __name__ == "__main__":
    print("🚀 راه‌اندازی ربات...")
    threading.Thread(target=run_flask, daemon=True).start()
    import asyncio
    asyncio.run(setup_bot())
    while True: time.sleep(1)
