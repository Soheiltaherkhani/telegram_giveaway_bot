import sqlite3
import random
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ChatMemberStatus

# ========================= تنظیمات =========================
BOT_TOKEN   = "8227817016:AAHL4vYIAOBmBHun6iWhezZdyXSwJBzY8"
CHANNEL_ID  = "@fcxter"
ADMIN_IDS   = [6181430071, 5944937406]

# ========================= لاگ‌ گیری =========================
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ========================= دیتابیس =========================
conn   = sqlite3.connect("raffle.db", check_same_thread=False)
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

# ========================= منوها =========================
def user_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💎 افزایش امتیاز"), KeyboardButton("👤 اطلاعات حساب")],
        [KeyboardButton("💳 تبدیل امتیاز به شانس")],
        [KeyboardButton("🎰 ثبت نام در قرعه کشی")],
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎯 انتخاب برنده"), KeyboardButton("📊 آمار کاربران")],
        [KeyboardButton("🔄 ریست قرعه‌کشی")],
        # می‌تونیم گزینه‌های کاربری رو هم اینجا بیاوریم
        [KeyboardButton("💎 افزایش امتیاز"), KeyboardButton("👤 اطلاعات حساب")],
    ], resize_keyboard=True)

# ========================= چک عضویت =========================
async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        logger.debug(f"[is_member] user={user_id} status={member.status}")
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        )
    except Exception as e:
        logger.warning(f"[is_member] error for {user_id}: {e}")
        return False

# ========================= هندلر /start با Referral =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    user_id = user.id
    username= user.username or user.first_name

    logger.info(f"[start] called by {user_id}")

    # ذخیره کاربر اولیه
    cursor.execute(
      "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
      (user_id, username)
    )
    conn.commit()

    # سیستم Referral
    if context.args:
        try:
            ref_id = int(context.args[0])
            if ref_id != user_id:
                cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (ref_id,))
                if cursor.fetchone():
                    cursor.execute(
                      "UPDATE users SET points = points + 1 WHERE user_id = ?",
                      (ref_id,)
                    )
                    conn.commit()
                    logger.info(f"[referral] +1 point to {ref_id} (invited by {user_id})")
                    # پیام به معرف
                    try:
                        await context.bot.send_message(
                            ref_id,
                            "🎉 یک کاربر جدید با لینک شما وارد ربات شد! +1 امتیاز"
                        )
                    except:
                        pass
        except ValueError:
            pass

    # نمایش منو بر اساس نقش
    if user_id in ADMIN_IDS:
        await update.message.reply_text("👑 پنل مدیریت فعال شد!", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 خوش آمدید!", reply_markup=user_menu())

# ========================= هندل پیام‌ها =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text    = update.message.text
    user_id = update.effective_user.id
    logger.info(f"[msg] {user_id}: {text}")

    # بررسی عضویت
    if not await is_member(user_id, context):
        kb = [[InlineKeyboardButton("🔗 عضویت در کانال", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
        await update.message.reply_text(
            "🔒 لطفاً ابتدا در کانال عضو شوید.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # کاربر عادی
    if user_id not in ADMIN_IDS:
        if text == "🎰 ثبت نام در قرعه کشی":
            cursor.execute(
              "UPDATE users SET is_registered = 1 WHERE user_id = ?",
              (user_id,)
            )
            cursor.execute(
              "INSERT INTO raffle (user_id) VALUES (?)",
              (user_id,)
            )
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
                await update.message.reply_text(f"✅ {pts} امتیاز به شانس تبدیل شد.")
            else:
                await update.message.reply_text("⚠️ شما امتیازی ندارید.")

        elif text == "👤 اطلاعات حساب":
            cursor.execute(
              "SELECT points, chances, is_registered FROM users WHERE user_id = ?",
              (user_id,)
            )
            pts, ch, reg = cursor.fetchone()
            await update.message.reply_text(
                f"📊 ثبت‌نام: {'✅' if reg else '❌'}\n"
                f"امتیاز: {pts}\nشانس: {ch}"
            )

    # دستورات مدیر
    else:
        if text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            parts = [r[0] for r in cursor.fetchall()]
            if parts:
                w = random.choice(parts)
                cursor.execute("SELECT username FROM users WHERE user_id = ?", (w,))
                uname = cursor.fetchone()[0]
                await update.message.reply_text(f"🎉 برنده: @{uname} (ID: {w})")
            else:
                await update.message.reply_text("⚠️ هیچ شرکت‌کننده‌ای نیست.")

        elif text == "📊 آمار کاربران":
            cursor.execute("SELECT COUNT(*) FROM users")
            total_u = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM raffle")
            total_r = cursor.fetchone()[0]
            await update.message.reply_text(
                f"📊 کاربران: {total_u}\n"
                f"شرکت‌کنندگان: {total_r}"
            )

        elif text == "🔄 ریست قرعه کشی":
            cursor.execute("DELETE FROM raffle")
            cursor.execute("UPDATE users SET is_registered = 0, chances = 0")
            conn.commit()
            await update.message.reply_text("✅ قرعه‌کشی ریست شد!")

# ========================= اجرای Polling =========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("ربات در حال اجراست (Polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()
