import os
import sqlite3
import random
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ChatMemberStatus

# ========================= تنظیمات =========================
BOT_TOKEN = "8227817016:AAHL4vVYIAOBmBHun6iWhezZdyXSwJBjzY8"
WEBHOOK_URL = "https://0kzbboy4.up.railway.app"  # دامنه جدید
CHANNEL_IDS = ["@fcxter"]  # کانال‌های اجباری
ADMIN_IDS = [6181430071, 5944937406]  # آیدی مدیران

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

# ========================= توابع =========================
async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE):
    """بررسی عضویت کاربر در کانال‌ها"""
    for channel in CHANNEL_IDS:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            print(f"[DEBUG] وضعیت عضویت {user_id} در {channel}: {member.status}")
            if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                return False
        except Exception as e:
            print(f"[ERROR] بررسی عضویت کاربر {user_id} در {channel} با خطا مواجه شد: {e}")
            return False
    return True

def is_admin(user_id):
    return user_id in ADMIN_IDS

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

# ========================= هندلر استارت =========================
async def start_with_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    print(f"[DEBUG] دستور /start دریافت شد از {username} ({user_id})")

    # ثبت کاربر در دیتابیس
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()

    # بررسی رفرال
    if context.args and len(context.args) > 0:
        try:
            ref_id = int(context.args[0])
            if ref_id != user_id:
                cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (ref_id,))
                conn.commit()
                print(f"[DEBUG] امتیاز برای {ref_id} اضافه شد")
                try:
                    await context.bot.send_message(ref_id, "🎉 یک کاربر جدید با لینک شما وارد ربات شد!")
                except:
                    pass
        except Exception as e:
            print(f"[ERROR] خطا در پردازش رفرال: {e}")

    # بررسی عضویت
    if not await is_member(user_id, context):
        channels_list = "\n".join([f"🔗 {c}" for c in CHANNEL_IDS])
        await update.message.reply_text(f"🔒 لطفاً ابتدا در کانال‌های زیر عضو شوید:\n\n{channels_list}")
        print(f"[DEBUG] کاربر {user_id} عضو کانال‌ها نیست")
        return

    # نمایش منو
    if is_admin(user_id):
        await update.message.reply_text("📌 پنل مدیریت فعال شد!", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید!", reply_markup=main_menu())

    print(f"[DEBUG] منوی مناسب برای {user_id} ارسال شد")

# ========================= هندلر پیام‌ها =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    print(f"[DEBUG] پیام دریافت شد: {text} از {user_id}")

    if not is_admin(user_id):  # کاربر عادی
        if text == "🎰 ثبت نام در قرعه کشی":
            cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,))
            cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
            conn.commit()
            await update.message.reply_text("✅ شما در قرعه‌کشی ثبت نام شدید!")

        elif text == "💎 افزایش امتیاز":
            link = f"https://t.me/{context.bot.username}?start={user_id}"
            await update.message.reply_text(f"🔗 لینک اختصاصی شما:\n{link}")

        elif text == "💳 تبدیل امتیاز به شانس":
            cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            points = row[0] if row else 0
            if points > 0:
                cursor.execute("UPDATE users SET points = 0, chances = chances + ? WHERE user_id = ?", (points, user_id))
                for _ in range(points):
                    cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
                conn.commit()
                await update.message.reply_text("✅ امتیازها به شانس تبدیل شد!")
            else:
                await update.message.reply_text("⚠️ شما امتیازی برای تبدیل ندارید.")

        elif text == "👤 اطلاعات حساب":
            cursor.execute("SELECT points, chances, is_registered FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                points, chances, registered = row
                status = "بله" if registered else "خیر"
                await update.message.reply_text(f"📊 اطلاعات حساب:\n\nثبت‌نام: {status}\nامتیاز: {points}\nشانس: {chances}")

    else:  # مدیر
        if text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            participants = [row[0] for row in cursor.fetchall()]
            if not participants:
                await update.message.reply_text("⚠️ هنوز کسی در قرعه‌کشی ثبت‌نام نکرده.")
                return
            winner_id = random.choice(participants)
            cursor.execute("SELECT username FROM users WHERE user_id = ?", (winner_id,))
            winner_username = cursor.fetchone()[0]
            await update.message.reply_text(f"🎉 برنده قرعه‌کشی: @{winner_username}")

        elif text == "👥 انتخاب چند برنده":
            cursor.execute("SELECT user_id FROM raffle")
            participants = [row[0] for row in cursor.fetchall()]
            if not participants:
                await update.message.reply_text("⚠️ هیچ شرکت‌کننده‌ای نیست.")
                return
            winners = random.sample(participants, min(3, len(participants)))
            result = []
            for w in winners:
                cursor.execute("SELECT username FROM users WHERE user_id = ?", (w,))
                result.append("@" + cursor.fetchone()[0])
            await update.message.reply_text("🎯 برندگان:\n" + "\n".join(result))

        elif text == "📢 ارسال پیام به همه":
            await update.message.reply_text("✍️ پیام خود را ارسال کنید:")
            context.user_data["broadcast"] = True

        elif text == "📊 آمار":
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered = 1")
            registered_users = cursor.fetchone()[0]
            await update.message.reply_text(f"📊 آمار کلی:\n\n👥 تعداد کاربران: {total_users}\n✅ ثبت‌نامی‌ها: {registered_users}")

        elif text == "🔄 ریست قرعه‌کشی":
            cursor.execute("DELETE FROM raffle")
            conn.commit()
            await update.message.reply_text("✅ قرعه‌کشی ریست شد!")

        elif context.user_data.get("broadcast"):
            cursor.execute("SELECT user_id FROM users")
            users = [row[0] for row in cursor.fetchall()]
            for u in users:
                try:
                    await context.bot.send_message(u, text)
                except:
                    pass
            context.user_data["broadcast"] = False
            await update.message.reply_text("✅ پیام به همه ارسال شد!")

# ========================= Flask و Webhook =========================
flask_app = Flask(__name__)
telegram_app = None

@flask_app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "ok"

async def init_telegram():
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start_with_referral))
    telegram_app.add_handler(MessageHandler(filters.TEXT, handle_message))
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    print(f"[DEBUG] Webhook ثبت شد: {WEBHOOK_URL}/{BOT_TOKEN}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_telegram())
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
