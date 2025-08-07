import sqlite3
import random
import requests
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8227817016:AAGwqzCfx6abijss3ksZyju1ifXHLJ1lNCw"

# حذف وبهوک قبل از شروع Polling
requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")

ADMIN_IDS = [6181430071, 5944937406]

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

cursor.execute("""CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT
)""")

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
        ["➕ افزودن کانال", "📋 لیست کانال‌های جوین اجباری"],
        ["❌ حذف کانال جوین اجباری", "🔄 ریست قرعه‌کشی"]
    ], resize_keyboard=True)


async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT username FROM channels")
    channels = cursor.fetchall()
    for ch in channels:
        channel = ch[0]
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                   (user.id, user.username or user.first_name))
    conn.commit()

    if user.id in ADMIN_IDS:
        await update.message.reply_text("👑 به پنل مدیریت خوش آمدید!", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید!", reply_markup=main_menu())


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if user_id in ADMIN_IDS:
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
            await update.message.reply_text("✅ قرعه‌کشی ریست شد.")

        elif text == "📋 لیست کاربران":
            cursor.execute("SELECT username FROM users")
            users = cursor.fetchall()
            user_list = "\n".join([f"@{u[0]}" if u[0] else "بدون نام" for u in users])
            await update.message.reply_text(f"📋 لیست کاربران:\n\n{user_list[:3500]}" or "📋 هیچ کاربری ثبت نشده.")

        elif text == "📢 ارسال پیام به همه":
            context.user_data["broadcast"] = True
            await update.message.reply_text("📢 پیام خود را ارسال کنید.")
        elif context.user_data.get("broadcast"):
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()
            for (uid,) in users:
                try:
                    if update.message.text:
                        await context.bot.send_message(uid, f"📢 پیام مدیر:\n{update.message.text}")
                except:
                    pass
            context.user_data["broadcast"] = False
            await update.message.reply_text("✅ پیام به همه ارسال شد.")

        elif text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            participants = [r[0] for r in cursor.fetchall()]
            if not participants:
                await update.message.reply_text("⚠️ هیچ شرکت‌کننده‌ای وجود ندارد.")
            else:
                winner_id = random.choice(participants)
                cursor.execute("SELECT username FROM users WHERE user_id = ?", (winner_id,))
                winner = cursor.fetchone()
                winner_name = f"@{winner[0]}" if winner and winner[0] else f"User {winner_id}"
                await update.message.reply_text(f"🏆 برنده قرعه‌کشی: {winner_name}")
                try:
                    await context.bot.send_message(winner_id, "🎉 تبریک! شما برنده قرعه‌کشی شدید!")
                except:
                    pass

        elif text == "➕ افزودن کانال":
            context.user_data["adding_channel"] = True
            await update.message.reply_text("🔗 آیدی کانال را با @ وارد کنید.")

        elif context.user_data.get("adding_channel"):
            if not text.startswith("@"):
                await update.message.reply_text("❌ آیدی کانال باید با @ شروع شود.")
            else:
                cursor.execute("INSERT INTO channels (username) VALUES (?)", (text,))
                conn.commit()
                await update.message.reply_text("✅ کانال اضافه شد.")
            context.user_data["adding_channel"] = False

        elif text == "📋 لیست کانال‌های جوین اجباری":
            cursor.execute("SELECT username FROM channels")
            channels = cursor.fetchall()
            if not channels:
                await update.message.reply_text("⚠️ هیچ کانالی ثبت نشده.")
            else:
                ch_list = "\n".join([f"- {ch[0]}" for ch in channels])
                await update.message.reply_text(f"📋 لیست کانال‌ها:\n\n{ch_list}")

        elif text == "❌ حذف کانال جوین اجباری":
            cursor.execute("SELECT username FROM channels")
            channels = cursor.fetchall()
            if not channels:
                await update.message.reply_text("⚠️ هیچ کانالی برای حذف وجود ندارد.")
            else:
                context.user_data["removing_channel"] = True
                await update.message.reply_text("❌ آیدی کانالی که می‌خواهید حذف کنید را وارد کنید.")

        elif context.user_data.get("removing_channel"):
            cursor.execute("DELETE FROM channels WHERE username = ?", (text,))
            conn.commit()
            await update.message.reply_text("✅ کانال حذف شد.")
            context.user_data["removing_channel"] = False

    else:
        if not await is_member(user_id, context):
            cursor.execute("SELECT username FROM channels")
            channels = cursor.fetchall()
            buttons = [[InlineKeyboardButton(f"عضویت در {ch[0]}", url=f"https://t.me/{ch[0][1:]}")] for ch in channels]
            markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(
                "🔒 برای استفاده از ربات باید در کانال‌های زیر عضو شوید:",
                reply_markup=markup
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
                f"📊 اطلاعات شما:\n\n👤 کاربر: @{username}\n🎯 وضعیت: {status}\n💎 امتیاز: {points}\n🎟️ شانس: {chances}"
            )


app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🤖 ربات در حال اجراست...")
app.run_polling()
