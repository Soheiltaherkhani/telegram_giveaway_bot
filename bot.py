import os
import sqlite3
import random
import threading
from flask import Flask, request, jsonify
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ChatMemberStatus

# --- تنظیمات ---
BOT_TOKEN = "8227817016:AAHL4vVYIAOBmBHun6iWhezZdyXSwJBjzY8"
WEBHOOK_URL = "https://0kzbboy4.up.railway.app"
CHANNEL_ID = "@fcxter"
ADMIN_IDS = [6181430071, 5944937406]

# --- دیتابیس ---
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

# --- منوها ---
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

# --- بررسی عضویت ---
async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        print(f"[DEBUG] وضعیت کاربر {user_id}: {member.status}")
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception as e:
        print(f"[ERROR] بررسی عضویت: {e}")
        return False

def is_admin(user_id):
    return user_id in ADMIN_IDS

# --- استارت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    print(f"[DEBUG] /start از {user.id}")

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                   (user.id, user.username or user.first_name))
    conn.commit()

    if not await is_member(user.id, context):
        keyboard = [[InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
        await update.message.reply_text(
            f"🔒 برای استفاده از ربات باید در کانال عضو شوید:\n\n{CHANNEL_ID}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if is_admin(user.id):
        await update.message.reply_text("👑 پنل مدیریت فعال شد", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید", reply_markup=main_menu())

# --- پیام‌ها ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if not await is_member(user_id, context):
        keyboard = [[InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
        await update.message.reply_text("❌ ابتدا در کانال عضو شوید", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if not is_admin(user_id):
        if text == "🎰 ثبت نام در قرعه کشی":
            cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,))
            cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
            conn.commit()
            await update.message.reply_text("✅ در قرعه‌کشی ثبت نام شدید")

        elif text == "💎 افزایش امتیاز":
            link = f"https://t.me/{context.bot.username}?start={user_id}"
            await update.message.reply_text(f"🔗 لینک اختصاصی شما:\n{link}")

        elif text == "💳 تبدیل امتیاز به شانس":
            cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
            points = cursor.fetchone()[0]
            if points > 0:
                cursor.execute("UPDATE users SET points = 0, chances = chances + ? WHERE user_id = ?", (points, user_id))
                for _ in range(points):
                    cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
                conn.commit()
                await update.message.reply_text(f"✅ {points} امتیاز به شانس تبدیل شد")
            else:
                await update.message.reply_text("⚠️ امتیازی ندارید")

        elif text == "👤 اطلاعات حساب":
            cursor.execute("SELECT points, chances, is_registered FROM users WHERE user_id = ?", (user_id,))
            points, chances, reg = cursor.fetchone()
            await update.message.reply_text(
                f"📊 اطلاعات شما:\nثبت‌نام: {'✅' if reg else '❌'}\nامتیاز: {points}\nشانس: {chances}"
            )

    else:
        if text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            users = [r[0] for r in cursor.fetchall()]
            if not users:
                await update.message.reply_text("⚠️ هیچ شرکت‌کننده‌ای وجود ندارد")
            else:
                winner = random.choice(users)
                cursor.execute("SELECT username FROM users WHERE user_id = ?", (winner,))
                username = cursor.fetchone()[0]
                await update.message.reply_text(f"🎉 برنده: @{username}")

        elif text == "🔄 ریست قرعه‌کشی":
            cursor.execute("DELETE FROM raffle")
            cursor.execute("UPDATE users SET is_registered = 0, chances = 0")
            conn.commit()
            await update.message.reply_text("✅ قرعه‌کشی ریست شد")

        elif text == "📊 آمار":
            cursor.execute("SELECT COUNT(*) FROM users")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered=1")
            registered = cursor.fetchone()[0]
            await update.message.reply_text(f"📊 آمار:\nکاربران: {total}\nثبت‌نامی‌ها: {registered}")

# --- رفرال ---
async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        try:
            ref_id = int(context.args[0])
            if ref_id != update.effective_user.id:
                cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (ref_id,))
                conn.commit()
                await context.bot.send_message(ref_id, "🎉 یک کاربر جدید با لینک شما وارد شد")
        except:
            pass
    await start(update, context)

# --- Flask ---
flask_app = Flask(__name__)
telegram_app = None

@flask_app.route('/', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@flask_app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "ok", 200

async def setup_telegram():
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", referral))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    print(f"[INFO] وبهوک ثبت شد: {WEBHOOK_URL}/{BOT_TOKEN}")

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

if __name__ == "__main__":
    import asyncio
    print("[INFO] راه‌اندازی ربات...")
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(setup_telegram())
    while True:
        import time
        time.sleep(1)        [KeyboardButton("🎰 ثبت نام در قرعه کشی")]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎯 انتخاب برنده"), KeyboardButton("👥 انتخاب چند برنده")],
        [KeyboardButton("📢 ارسال پیام به همه"), KeyboardButton("📊 آمار")],
        [KeyboardButton("🔄 ریست قرعه‌کشی")]
    ], resize_keyboard=True)

async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

def is_admin(user_id):
    return user_id in ADMIN_IDS

# استارت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    print(f"[LOG] کاربر {user.id} دستور /start فرستاد")

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                   (user.id, user.username or user.first_name))
    conn.commit()

    if not await is_member(user.id, context):
        keyboard = [[InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
        await update.message.reply_text(
            f"🔒 لطفاً ابتدا در کانال {CHANNEL_ID} عضو شوید و سپس دوباره /start را بزنید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if is_admin(user.id):
        await update.message.reply_text("👑 پنل ادمین فعال شد!", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید!", reply_markup=main_menu())

# پیام‌ها
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if not await is_member(user_id, context):
        keyboard = [[InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
        await update.message.reply_text(f"❌ لطفاً ابتدا در {CHANNEL_ID} عضو شوید.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if not is_admin(user_id):
        if text == "🎰 ثبت نام در قرعه کشی":
            cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,))
            cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
            conn.commit()
            await update.message.reply_text("✅ شما ثبت‌نام شدید!")

        elif text == "💎 افزایش امتیاز":
            await update.message.reply_text(f"🔗 لینک شما:\nhttps://t.me/{context.bot.username}?start={user_id}")

        elif text == "💳 تبدیل امتیاز به شانس":
            cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
            points = cursor.fetchone()[0]
            if points > 0:
                cursor.execute("UPDATE users SET points = 0, chances = chances + ? WHERE user_id = ?", (points, user_id))
                for _ in range(points):
                    cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
                conn.commit()
                await update.message.reply_text("✅ امتیازها به شانس تبدیل شد!")
            else:
                await update.message.reply_text("⚠️ شما امتیازی ندارید.")

        elif text == "👤 اطلاعات حساب":
            cursor.execute("SELECT points, chances, is_registered FROM users WHERE user_id = ?", (user_id,))
            points, chances, reg = cursor.fetchone()
            await update.message.reply_text(f"📊 امتیاز: {points}\n🎟 شانس: {chances}\nوضعیت ثبت‌نام: {'✅' if reg else '❌'}")
    else:
        if text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            users = [r[0] for r in cursor.fetchall()]
            if users:
                winner = random.choice(users)
                cursor.execute("SELECT username FROM users WHERE user_id = ?", (winner,))
                username = cursor.fetchone()[0]
                await update.message.reply_text(f"🎉 برنده: @{username}")
            else:
                await update.message.reply_text("⚠️ هنوز کسی ثبت‌نام نکرده.")

# رفرال
async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and len(context.args) > 0:
        ref_id = int(context.args[0])
        if ref_id != update.effective_user.id:
            cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (ref_id,))
            conn.commit()
            try:
                await context.bot.send_message(ref_id, "🎉 یک کاربر با لینک شما وارد شد!")
            except:
                pass
    await start(update, context)

# Flask
flask_app = Flask(__name__)
telegram_app = None

@flask_app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@flask_app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        asyncio.run(telegram_app.process_update(update))
    except Exception as e:
        print(f"[ERROR] Webhook: {e}")
    return "ok"

async def setup_telegram():
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", handle_referral))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    await telegram_app.initialize()
    await telegram_app.start()
    print(f"[LOG] Webhook تنظیم شد: {WEBHOOK_URL}/{BOT_TOKEN}")

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(setup_telegram())
    while True:
        import time
        time.sleep(1)



