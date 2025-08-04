import sqlite3
import random
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ChatMemberStatus

# --- تنظیمات ---
BOT_TOKEN = "8227817016:AAHL4vVYIAOBmBHun6iWhezZdyXSwJBzY8"
CHANNEL_ID = "@fcxter"
ADMIN_IDS = [6181430071, 5944937406]

# --- لاگ‌ گیری ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

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
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS raffle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER
)
""")
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
        [KeyboardButton("🎯 انتخاب برنده"), KeyboardButton("📊 آمار")],
        [KeyboardButton("🔄 ریست قرعه‌کشی")]
    ], resize_keyboard=True)

# --- بررسی عضویت ---
async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        logger.debug(f"عضویت {user_id} در کانال: {member.status}")
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        )
    except Exception as e:
        logger.error(f"خطا در بررسی عضویت {user_id}: {e}")
        return False

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# --- هندلر /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uname = update.effective_user.username or update.effective_user.first_name
    logger.info(f"دستور /start توسط {uid}")

    # ثبت در دیتابیس
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (uid, uname)
    )
    conn.commit()

    # نمایش منو
    if is_admin(uid):
        logger.debug("ارسال منوی ادمین")
        await update.message.reply_text("👑 پنل مدیریت فعال شد!", reply_markup=admin_menu())
    else:
        logger.debug("ارسال منوی کاربر عادی")
        await update.message.reply_text("🎉 به ربات خوش آمدید!", reply_markup=main_menu())

    # بررسی عضویت و نمایش پیام در صورت عدم عضویت
    if not await is_member(uid, context):
        logger.debug("کاربر عضو کانال نیست")
        kb = [[InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
        await update.message.reply_text(
            "🔒 برای استفاده از ربات باید در کانال عضو شوید.",
            reply_markup=InlineKeyboardMarkup(kb)
        )

# --- هندلر پیام‌ها ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    logger.info(f"پیام '{text}' از {uid}")

    # ابتدا بررسی عضویت
    if not await is_member(uid, context):
        logger.debug("عدم عضویت، ارسال پیام عضویت")
        kb = [[InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
        await update.message.reply_text(
            "❌ ابتدا در کانال عضو شوید.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # منطق دکمه‌ها
    if text == "🎰 ثبت نام در قرعه کشی":
        cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (uid,))
        cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (uid,))
        conn.commit()
        await update.message.reply_text("✅ ثبت‌نام شما انجام شد!")

    elif text == "💎 افزایش امتیاز":
        link = f"https://t.me/{context.bot.username}?start={uid}"
        await update.message.reply_text(f"🔗 لینک معرفی شما:\n{link}")

    elif text == "💳 تبدیل امتیاز به شانس":
        cursor.execute("SELECT points FROM users WHERE user_id = ?", (uid,))
        pts = cursor.fetchone()[0]
        if pts > 0:
            cursor.execute(
                "UPDATE users SET points = 0, chances = chances + ? WHERE user_id = ?",
                (pts, uid)
            )
            for _ in range(pts):
                cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (uid,))
            conn.commit()
            await update.message.reply_text(f"✅ {pts} امتیاز شما به شانس تبدیل شد!")
        else:
            await update.message.reply_text("⚠️ شما امتیازی ندارید.")

    elif text == "👤 اطلاعات حساب":
        cursor.execute(
            "SELECT username, points, chances, is_registered FROM users WHERE user_id = ?",
            (uid,)
        )
        username, points, chances, reg = cursor.fetchone()
        status = "✅ ثبت‌نام شده" if reg else "❌ ثبت‌نام نشده"
        await update.message.reply_text(
            f"📊 اطلاعات حساب:\n\n"
            f"یوزرنیم: @{username}\n"
            f"وضعیت ثبت‌نام: {status}\n"
            f"امتیاز: {points}\n"
            f"شانس: {chances}"
        )

    elif text == "🎯 انتخاب برنده" and is_admin(uid):
        cursor.execute("SELECT user_id FROM raffle")
        parts = [r[0] for r in cursor.fetchall()]
        if parts:
            winner = random.choice(parts)
            cursor.execute("SELECT username FROM users WHERE user_id = ?", (winner,))
            win_name = cursor.fetchone()[0]
            await update.message.reply_text(f"🎉 برنده: @{win_name}")
        else:
            await update.message.reply_text("⚠️ هیچ شرکت‌کننده‌ای نیست.")

    elif text == "🔄 ریست قرعه‌کشی" and is_admin(uid):
        cursor.execute("DELETE FROM raffle")
        cursor.execute("UPDATE users SET is_registered = 0, chances = 0")
        conn.commit()
        await update.message.reply_text("✅ قرعه‌کشی ریست شد!")

# --- اجرای Polling ---
async def main():
    logger.info("راه‌اندازی ربات (polling)...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
