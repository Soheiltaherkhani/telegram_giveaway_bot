import sqlite3
import random
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8227817016:AAGwqzCfx6abijss3ksZyju1ifXHLJ1lNCw"
CHANNEL_IDS = ["@fcxter", "@FCXTERGP"]  # کانال‌های اجباری
ADMIN_IDS = [6181430071, 5944937406]  # آیدی ادمین‌ها

# --- حذف وبهوک قبل از اجرای Polling ---
delete_webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
print("حذف وبهوک:", requests.get(delete_webhook_url).json())

# اتصال به دیتابیس
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


# کیبورد کاربر
def main_menu():
    return ReplyKeyboardMarkup([
        ["💎 افزایش امتیاز", "👤 اطلاعات حساب"],
        ["💳 تبدیل امتیاز به شانس", "🎰 ثبت نام در قرعه‌کشی"]
    ], resize_keyboard=True)


# کیبورد مدیر
def admin_menu():
    return ReplyKeyboardMarkup([
        ["🎯 انتخاب برنده", "📊 آمار"],
        ["📢 ارسال پیام به همه", "📋 لیست کاربران"],
        ["🔄 ریست قرعه‌کشی"]
    ], resize_keyboard=True)


# بررسی عضویت در کانال‌ها
async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE):
    for channel in CHANNEL_IDS:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True


# دستور start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                   (user.id, user.username or user.first_name))
    conn.commit()

    if user.id in ADMIN_IDS:
        await update.message.reply_text("👑 به پنل مدیریت خوش آمدید!", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید!", reply_markup=main_menu())


# مدیریت پیام‌ها
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if user_id in ADMIN_IDS:  # پنل مدیر
        if text == "📊 آمار":
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered = 1")
            registered = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM raffle")
            total_chances = cursor.fetchone()[0]

            await update.message.reply_text(
                f"📊 آمار:\n\n👥 کاربران: {total_users}\n🎰 شرکت‌کنندگان: {registered}\n🎟️ شانس‌ها: {total_chances}"
            )

        elif text == "🔄 ریست قرعه‌کشی":
            cursor.execute("DELETE FROM raffle")
            cursor.execute("UPDATE users SET is_registered = 0, chances = 0")
            conn.commit()
            await update.message.reply_text("✅ قرعه‌کشی ریست شد. کاربران حذف نشدند ولی آمار صفر شد.")

        elif text == "📋 لیست کاربران":
            cursor.execute("SELECT user_id, username FROM users")
            users = cursor.fetchall()
            user_list = "\n".join([f"{u[1] or 'بدون‌نام'} ({u[0]})" for u in users]) or "هیچ کاربری وجود ندارد."
            await update.message.reply_text(f"📋 لیست کاربران:\n\n{user_list[:3500]}")

        elif text == "📢 ارسال پیام به همه":
            context.user_data["broadcast"] = True
            await update.message.reply_text("📢 پیام (متن/عکس/ویدیو) خود را ارسال کنید.")

        elif context.user_data.get("broadcast"):
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()
            for (uid,) in users:
                try:
                    if update.message.text:
                        await context.bot.send_message(uid, f"📢 پیام مدیر:\n{update.message.text}")
                    elif update.message.photo:
                        photo_id = update.message.photo[-1].file_id
                        await context.bot.send_photo(uid, photo_id, caption=update.message.caption or "")
                    elif update.message.video:
                        video_id = update.message.video.file_id
                        await context.bot.send_video(uid, video_id, caption=update.message.caption or "")
                except:
                    pass
            context.user_data["broadcast"] = False
            await update.message.reply_text("✅ پیام به همه ارسال شد.")
    else:  # بخش کاربران
        if not await is_member(user_id, context):
            await update.message.reply_text("🔒 برای استفاده از ربات باید در کانال‌های تعیین شده عضو شوید.")
            return

        if text == "🎰 ثبت نام در قرعه‌کشی":
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
                f"📊 اطلاعات شما:\n\n👤 کاربر: @{username}\n🎯 وضعیت: {status}\n💎 امتیاز: {points}\n🎟️ شانس: {chances}"
            )


# اجرای ربات
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.ALL, handle_message))

print("🤖 ربات در حال اجراست (Polling)...")
app.run_polling()

