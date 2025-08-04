import os
import sqlite3
import random
import threading
from flask import Flask, request, jsonify
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ChatMemberStatus

# ========================= تنظیمات =========================
BOT_TOKEN = "8227817016:AAHL4vVYIAOBmBHun6iWhezZdyXSwJBjzY8"
WEBHOOK_URL = "https://0kzbboy4.up.railway.app"  # دامنه Railway
CHANNEL_ID = "@fut180"  # کانال اجباری
ADMIN_IDS = [6181430071, 5944937406]  # آیدی مدیرها

# ========================= دیتابیس =========================
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

# ========================= منوها =========================
def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💎 افزایش امتیاز"), KeyboardButton("👤 اطلاعات حساب")],
        [KeyboardButton("💳 تبدیل امتیاز به شانس")],
        [KeyboardButton("🎰 ثبت نام در قرعه کشی")]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎯 انتخاب برنده"), KeyboardButton("👥 انتخاب چند برنده")],
        [KeyboardButton("📢 ارسال پیام به همه"), KeyboardButton("📊 آمار")],
        [KeyboardButton("🔄 ریست قرعه‌کشی")]
    ], resize_keyboard=True)

# ========================= توابع کمکی =========================
async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE):
    """بررسی عضویت کاربر در کانال"""
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ========================= دستورات ربات =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    print(f"کاربر {user.id} دستور /start را ارسال کرد")

    # ذخیره کاربر در دیتابیس
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                   (user.id, user.username or user.first_name))
    conn.commit()

    # بررسی عضویت در کانال
    if not await is_member(user.id, context):
        keyboard = [[InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🔒 لطفاً ابتدا در کانال زیر عضو شوید:\n\n{CHANNEL_ID}\n\n"
            "پس از عضویت دوباره /start را بزنید.",
            reply_markup=reply_markup
        )
        return

    # نمایش منو
    if is_admin(user.id):
        await update.message.reply_text("👑 پنل مدیریت فعال شد!", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید!", reply_markup=main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if not await is_member(user_id, context):
        keyboard = [[InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
        await update.message.reply_text("❌ ابتدا در کانال عضو شوید.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if not is_admin(user_id):  # کاربران عادی
        if text == "🎰 ثبت نام در قرعه کشی":
            cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,))
            cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
            conn.commit()
            await update.message.reply_text("✅ شما با موفقیت در قرعه‌کشی ثبت‌نام شدید!")

        elif text == "💎 افزایش امتیاز":
            link = f"https://t.me/{context.bot.username}?start={user_id}"
            await update.message.reply_text(f"🔗 لینک معرفی شما:\n{link}")

        elif text == "💳 تبدیل امتیاز به شانس":
            cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
            points = cursor.fetchone()[0]
            if points > 0:
                cursor.execute("UPDATE users SET points = 0, chances = chances + ? WHERE user_id = ?", (points, user_id))
                for _ in range(points):
                    cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
                conn.commit()
                await update.message.reply_text(f"✅ {points} امتیاز به شانس تبدیل شد!")
            else:
                await update.message.reply_text("⚠️ شما امتیازی ندارید.")

        elif text == "👤 اطلاعات حساب":
            cursor.execute("SELECT points, chances, is_registered FROM users WHERE user_id = ?", (user_id,))
            points, chances, registered = cursor.fetchone()
            await update.message.reply_text(
                f"📊 اطلاعات حساب:\nثبت‌نام: {'✅ بله' if registered else '❌ خیر'}\n"
                f"امتیاز: {points}\nشانس: {chances}"
            )

    else:  # مدیران
        if text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            participants = [r[0] for r in cursor.fetchall()]
            if participants:
                winner = random.choice(participants)
                cursor.execute("SELECT username FROM users WHERE user_id = ?", (winner,))
                username = cursor.fetchone()[0]
                await update.message.reply_text(f"🎉 برنده: @{username}")
            else:
                await update.message.reply_text("⚠️ کسی ثبت‌نام نکرده!")

        elif text == "👥 انتخاب چند برنده":
            cursor.execute("SELECT user_id FROM raffle")
            participants = [r[0] for r in cursor.fetchall()]
            if participants:
                winners = random.sample(participants, min(3, len(participants)))
                result = []
                for w in winners:
                    cursor.execute("SELECT username FROM users WHERE user_id = ?", (w,))
                    result.append("@" + cursor.fetchone()[0])
                await update.message.reply_text("🎯 برندگان:\n" + "\n".join(result))
            else:
                await update.message.reply_text("⚠️ هیچ شرکت‌کننده‌ای وجود ندارد.")

        elif text == "📊 آمار":
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered = 1")
            registered_users = cursor.fetchone()[0]
            await update.message.reply_text(f"📊 آمار:\nکاربران: {total_users}\nثبت‌نامی‌ها: {registered_users}")

        elif text == "🔄 ریست قرعه‌کشی":
            cursor.execute("DELETE FROM raffle")
            conn.commit()
            await update.message.reply_text("✅ قرعه‌کشی ریست شد!")

# ========================= وب‌هوک =========================
flask_app = Flask(__name__)
telegram_app = None

@flask_app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

@flask_app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "ok"

async def setup_telegram():
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    print(f"✅ وب‌هوک تنظیم شد: {WEBHOOK_URL}/{BOT_TOKEN}")

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

