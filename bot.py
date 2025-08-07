import sqlite3
import random
import requests
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8227817016:AAFaI1J3KPn-8WCrXl2MsvPtKTYoDL4TINo"
ADMIN_IDS = [6181430071, 5944937406]  # آیدی مدیرها

requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")

# اتصال به دیتابیس
conn = sqlite3.connect("raffle.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    chances INTEGER DEFAULT 0,
    is_registered INTEGER DEFAULT 0
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

# منوها
def main_menu():
    return ReplyKeyboardMarkup([
        ["💎 افزایش امتیاز", "👤 اطلاعات حساب"],
        ["💳 تبدیل امتیاز به شانس", "🎰 ثبت نام در قرعه کشی"],
            ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        ["🎯 انتخاب برنده", "📊 آمار"],
        ["📢 ارسال پیام به همه", "📋 لیست کاربران"],
        ["➕ افزودن کانال", "📋 لیست کانال‌های جوین اجباری"],
        ["❌ حذف کانال جوین اجباری", "🔄 ریست قرعه‌کشی"],
        ["🏆 لیدربورد کاربران"]
    ], resize_keyboard=True)

# بررسی عضویت
async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE):
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

# استارت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                   (user.id, user.username or user.first_name))
    conn.commit()

    if args:
        try:
            ref_id = int(args[0])
            if ref_id != user.id:
                cursor.execute("SELECT points, chances FROM users WHERE user_id = ?", (ref_id,))
                ref_data = cursor.fetchone()
                if ref_data:
                    total = ref_data[0] + ref_data[1]
                    if total < 50:
                        cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (ref_id,))
                        conn.commit()
                        try:
                            await context.bot.send_message(ref_id, f"🎉 با دعوت یک کاربر، ۱ امتیاز گرفتی!")
                        except:
                            pass
        except:
            pass

    if user.id in ADMIN_IDS:
        await update.message.reply_text("👑 به پنل مدیریت خوش آمدید!", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید!", reply_markup=main_menu())

# مدیریت پیام‌ها
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

        elif text == "🏆 لیدربورد کاربران":
            cursor.execute("SELECT username, chances FROM users ORDER BY chances DESC LIMIT 10")
            top = cursor.fetchall()
            if top:
                msg = "🏆 لیدربورد کاربران بر اساس شانس:\n\n"
                for i, (u, c) in enumerate(top, start=1):
                    msg += f"{i}. @{u or 'ناشناس'} - {c} شانس\n"
                await update.message.reply_text(msg)
            else:
                await update.message.reply_text("⛔ هیچ داده‌ای برای نمایش وجود ندارد.")

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

        elif text == "🔄 ریست قرعه‌کشی":
            cursor.execute("DELETE FROM raffle")
            cursor.execute("UPDATE users SET is_registered = 0, chances = 0")
            conn.commit()
            await update.message.reply_text("✅ قرعه‌کشی ریست شد.")
        elif text == "📋 لیست کاربران":
            cursor.execute("SELECT username, user_id FROM users")
            users = cursor.fetchall()
            if users:
                msg = "👥 لیست کاربران:\n"
                for u, uid in users:
                    msg += f"@{u or 'ناشناس'} ({uid})\n"
                await update.message.reply_text(msg[:4000])  # محدودیت تلگرام
            else:
                await update.message.reply_text("❌ هیچ کاربری ثبت نشده.")

        elif text == "➕ افزودن کانال":
            await update.message.reply_text("📥 لطفاً آیدی کانال را با @ ارسال کنید.")
            context.user_data["awaiting_channel"] = True

        elif context.user_data.get("awaiting_channel"):
            if text.startswith("@"):
                cursor.execute("INSERT INTO channels (username) VALUES (?)", (text,))
                conn.commit()
                await update.message.reply_text(f"✅ کانال {text} اضافه شد.")
            else:
                await update.message.reply_text("⚠️ آیدی کانال باید با @ شروع شود. لطفاً دوباره ارسال کنید.")
            context.user_data["awaiting_channel"] = False

        elif text == "📋 لیست کانال‌های جوین اجباری":
            cursor.execute("SELECT username FROM channels")
            channels = cursor.fetchall()
            if channels:
                msg = "📢 کانال‌های اجباری:\n"
                for ch in channels:
                    msg += f"{ch[0]}\n"
                await update.message.reply_text(msg)
            else:
                await update.message.reply_text("⛔ هیچ کانالی ثبت نشده.")

        elif text == "❌ حذف کانال جوین اجباری":
            cursor.execute("SELECT username FROM channels")
            channels = cursor.fetchall()
            if channels:
                msg = "📛 برای حذف، آیدی کانال را با @ ارسال کنید:\n"
                for ch in channels:
                    msg += f"{ch[0]}\n"
                await update.message.reply_text(msg)
                context.user_data["awaiting_delete_channel"] = True
            else:
                await update.message.reply_text("⛔ کانالی برای حذف وجود ندارد.")

        elif context.user_data.get("awaiting_delete_channel"):
            cursor.execute("DELETE FROM channels WHERE username = ?", (text,))
            conn.commit()
            await update.message.reply_text(f"✅ اگر کانال {text} موجود بود، حذف شد.")
            context.user_data["awaiting_delete_channel"] = False

        elif text == "📢 ارسال پیام به همه":
            await update.message.reply_text("📝 لطفاً پیام خود را ارسال کنید.")
            context.user_data["awaiting_broadcast"] = True

        elif context.user_data.get("awaiting_broadcast"):
            cursor.execute("SELECT user_id FROM users")
            all_users = cursor.fetchall()
            success = 0
            for uid in all_users:
                try:
                    await context.bot.send_message(uid[0], text)
                    success += 1
                except:
                    continue
            await update.message.reply_text(f"✅ پیام برای {success} نفر ارسال شد.")
            context.user_data["awaiting_broadcast"] = False

    else:
        if not await is_member(user_id, context):
            cursor.execute("SELECT username FROM channels")
            channels = cursor.fetchall()
            buttons = [[InlineKeyboardButton(f"عضویت در {ch[0]}", url=f"https://t.me/{ch[0][1:]}")] for ch in channels]
            markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text("🔒 برای استفاده از ربات باید در کانال‌های زیر عضو شوید:", reply_markup=markup)
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

 

# اجرای ربات
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🤖 ربات در حال اجراست...")
app.run_polling()
