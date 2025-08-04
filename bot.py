import sqlite3
import random
import logging
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

# ========================= تنظیمات =========================
BOT_TOKEN  = "8227817016:AAHL4vYIAOBmBHun6iWhezZdyXSwJBzY8"
CHANNEL_ID = "@fcxter"
ADMIN_IDS  = [6181430071, 5944937406]

# ========================= لاگ‌گیری =========================
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ========================= دیتابیس =========================
conn   = sqlite3.connect("raffle.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
  user_id      INTEGER PRIMARY KEY,
  username     TEXT,
  points       INTEGER DEFAULT 0,
  chances      INTEGER DEFAULT 0,
  is_registered INTEGER DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS raffle (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER
)
""")
conn.commit()

# ========================= منوها =========================
def user_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎰 ثبت نام در قرعه کشی")],
        [KeyboardButton("💎 افزایش امتیاز"), KeyboardButton("💳 تبدیل امتیاز به شانس")],
        [KeyboardButton("👤 اطلاعات حساب")],
    ], resize_keyboard=True)

def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎯 انتخاب برنده"), KeyboardButton("📊 آمار کاربران")],
        [KeyboardButton("🔄 ریست قرعه کشی")],
    ], resize_keyboard=True)

# ========================= بررسی عضویت =========================
async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        logger.debug(f"[is_member] {user_id=} status={member.status}")
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception as e:
        logger.warning(f"[is_member] error for {user_id}: {e}")
        return False

# ========================= هندلر /start با Referral =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    user_id = user.id
    uname   = user.username or user.first_name

    logger.info(f"[start] from {user_id}")

    # ثبت کاربر
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, uname)
    )
    conn.commit()

    # Referral
    if context.args:
        try:
            ref_id = int(context.args[0])
            if ref_id != user_id:
                cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (ref_id,))
                if cursor.fetchone():
                    cursor.execute(
                        "UPDATE users SET points = points + 1 WHERE user_id = ?", (ref_id,)
                    )
                    conn.commit()
                    logger.info(f"[referral] +1 point to {ref_id} invited_by {user_id}")
                    # پیام فقط به معرف
                    await context.bot.send_message(
                        ref_id,
                        "🎉 یک کاربر جدید با لینک شما وارد شد! +1 امتیاز"
                    )
        except ValueError:
            pass

    # نمایش منوی مناسب
    if user_id in ADMIN_IDS:
        await update.message.reply_text("👑 پنل مدیریت فعال شد!", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات خوش آمدید!", reply_markup=user_menu())

# ========================= هندلر پیام‌ها =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text    = update.message.text
    logger.info(f"[msg] {user_id=} text={text!r}")

    # ۱) چک عضویت
    if not await is_member(user_id, context):
        kb = [[InlineKeyboardButton("🔗 عضویت در کانال", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
        await update.message.reply_text(
            "🔒 برای استفاده ابتدا در کانال عضو شوید.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # ۲) مسیر ادمین
    if user_id in ADMIN_IDS:
        if text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            parts = [r[0] for r in cursor.fetchall()]
            if not parts:
                await update.message.reply_text("⚠️ هیچ شرکت‌کننده‌ای نیست.")
            else:
                winner = random.choice(parts)
                cursor.execute("SELECT username FROM users WHERE user_id = ?", (winner,))
                uname = cursor.fetchone()[0]
                await update.message.reply_text(f"🎉 برنده: @{uname} (ID: {winner})")

        elif text == "📊 آمار کاربران":
            cursor.execute("SELECT COUNT(*) FROM users")
            total_u = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM raffle")
            total_r = cursor.fetchone()[0]
            await update.message.reply_text(
                f"📊 آمار:\n"
                f"👥 کل کاربران: {total_u}\n"
                f"🎟️ شانس‌های ثبت‌شده: {total_r}"
            )

        elif text == "🔄 ریست قرعه کشی":
            cursor.execute("DELETE FROM raffle")
            cursor.execute("UPDATE users SET is_registered = 0, chances = 0")
            conn.commit()
            await update.message.reply_text("✅ قرعه‌کشی ریست شد!")

        else:
            # برای دکمه‌های کاربری هم نمایش بده
            await update.message.reply_text("🚫 دستور نامعتبر برای ادمین.", reply_markup=admin_menu())

        return  # ادمین مسیرش پایان

    # ۳) مسیر کاربر عادی
    if text == "🎰 ثبت نام در قرعه کشی":
        cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,))
        cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
        conn.commit()
        await update.message.reply_text("✅ شما در قرعه‌کشی ثبت‌نام شدید!")

    elif text == "💎 افزایش امتیاز":
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        await update.message.reply_text(f"🔗 لینک دعوت شما:\n{link}")

    elif text == "💳 تبدیل امتیاز به شانس":
        cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
        pts = cursor.fetchone()[0]
        if pts > 0:
            cursor.execute(
                "UPDATE users SET points = 0, chances = chances + ? WHERE user_id = ?",
                (pts, user_id)
            )
            for _ in range(pts):
                cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
            conn.commit()
            await update.message.reply_text(f"✅ {pts} امتیاز به شانس تبدیل شد!")
        else:
            await update.message.reply_text("⚠️ شما هیچ امتیازی ندارید.")

    elif text == "👤 اطلاعات حساب":
        cursor.execute(
            "SELECT points, chances, is_registered FROM users WHERE user_id = ?",
            (user_id,)
        )
        pts, ch, reg = cursor.fetchone()
        await update.message.reply_text(
            f"📊 وضعیت ثبت‌نام: {'✅' if reg else '❌'}\n"
            f"🏅 امتیاز: {pts}\n"
            f"🎟️ شانس: {ch}"
        )

    else:
        await update.message.reply_text("🚫 دستور نامعتبر.", reply_markup=user_menu())

# ========================= اجرای ربات (Polling) =========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("ربات در حال اجراست (Polling)")
    app.run_polling()

if __name__ == "__main__":
    main()
