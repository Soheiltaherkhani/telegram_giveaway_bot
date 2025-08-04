import sqlite3
import random
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ChatMemberStatus

# ==================== تنظیمات اصلی ====================
BOT_TOKEN = "8227817016:AAHL4vVYIAOBmBHun6iWhezZdyXSwJBjzY8"
CHANNEL_IDS = ["@fcxter", "@your_second_channel"]  # کانال‌های اجباری
ADMIN_IDS = [6181430071, 5944937406]  # آیدی ادمین‌ها

# ==================== پایگاه داده ====================
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

# ==================== منوها ====================
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

# ==================== توابع کمکی ====================
async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        for channel in CHANNEL_IDS:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                return False
        return True
    except:
        return False

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ==================== دستورات اصلی ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                   (user.id, user.username or user.first_name))
    conn.commit()

    if is_admin(user.id):
        await update.message.reply_text("👑 پنل مدیریت فعال شد", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید!", reply_markup=main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # بررسی عضویت در کانال
    if not await is_member(user_id, context):
        keyboard = [[InlineKeyboardButton(f"عضویت در {ch}", url=f"https://t.me/{ch[1:]}")] for ch in CHANNEL_IDS]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🔒 برای استفاده از ربات باید در کانال‌های زیر عضو شوید:", reply_markup=reply_markup)
        return

    if is_admin(user_id):
        # =================== دکمه‌های ادمین ===================
        if text == "📊 آمار":
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered = 1")
            registered_users = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM raffle")
            total_chances = cursor.fetchone()[0]

            await update.message.reply_text(
                f"📊 آمار:\n\n"
                f"👥 کاربران: {total_users}\n"
                f"✅ ثبت‌نام کرده: {registered_users}\n"
                f"🎟 کل شانس‌ها: {total_chances}"
            )

        elif text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            participants = [row[0] for row in cursor.fetchall()]
            if participants:
                winner_id = random.choice(participants)
                cursor.execute("SELECT username FROM users WHERE user_id = ?", (winner_id,))
                username = cursor.fetchone()[0]
                await update.message.reply_text(f"🎉 برنده: @{username} (ID: {winner_id})")
            else:
                await update.message.reply_text("⚠️ کسی ثبت‌نام نکرده!")

        elif text == "📢 ارسال پیام به همه":
            await update.message.reply_text("لطفاً پیام موردنظر خود را ارسال کنید.")
            context.user_data["broadcast_mode"] = True

        elif text == "🔄 ریست قرعه‌کشی":
            cursor.execute("DELETE FROM raffle")
            cursor.execute("UPDATE users SET is_registered = 0, chances = 0, points = 0")
            conn.commit()
            await update.message.reply_text("✅ قرعه‌کشی و آمار کاربران ریست شد!")

    else:
        # =================== دکمه‌های کاربر ===================
        if text == "🎰 ثبت نام در قرعه کشی":
            cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,))
            cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
            conn.commit()
            await update.message.reply_text("✅ شما ثبت‌نام شدید!")

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
                await update.message.reply_text(f"✅ {points} امتیاز شما به شانس تبدیل شد!")
            else:
                await update.message.reply_text("⚠️ امتیازی برای تبدیل ندارید!")

        elif text == "👤 اطلاعات حساب":
            cursor.execute("SELECT username, points, chances, is_registered FROM users WHERE user_id = ?", (user_id,))
            username, points, chances, is_registered = cursor.fetchone()
            status = "✅ ثبت‌نام کرده" if is_registered else "❌ ثبت‌نام نکرده"
            await update.message.reply_text(
                f"👤 اطلاعات شما:\n\n"
                f"🆔 @{username}\n"
                f"📍 وضعیت: {status}\n"
                f"💎 امتیاز: {points}\n"
                f"🎟 شانس: {chances}"
            )

    # حالت ارسال پیام به همه
    if context.user_data.get("broadcast_mode"):
        context.user_data["broadcast_mode"] = False
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        for (uid,) in users:
            try:
                await context.bot.send_message(uid, text)
            except:
                pass
        await update.message.reply_text("✅ پیام به همه ارسال شد.")

async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    if args and args[0].isdigit():
        ref_id = int(args[0])
        if ref_id != user.id:
            cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                           (user.id, user.username or user.first_name))
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (ref_id,))
            if cursor.fetchone():
                cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (ref_id,))
                conn.commit()
                try:
                    await context.bot.send_message(ref_id, "🎉 یک کاربر جدید با لینک شما وارد شد!")
                except:
                    pass
    await start(update, context)

# ==================== اجرای ربات ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_referral))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ ربات در حال اجراست (Polling)")
    app.run_polling()

if __name__ == "__main__":
    main()
