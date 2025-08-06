import sqlite3
import random
import requests
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ====== تنظیمات ======
BOT_TOKEN = "8227817016:AAGwqzCfx6abijss3ksZyju1ifXHLJ1lNCw"
CHANNEL_IDS = ["@fcxter", "@FCXTERGP"]
ADMIN_IDS = [6181430071, 5944937406]

# حذف وبهوک برای اجتناب از تداخل
requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")

# لاگ‌گیری
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ====== دیتابیس ======
conn = sqlite3.connect("raffle.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    chances INTEGER DEFAULT 0,
    is_registered INTEGER DEFAULT 0,
    referrer_id INTEGER
)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS raffle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER
)""")
conn.commit()

# ====== منوها ======
def main_menu():
    return ReplyKeyboardMarkup([
        ["💎 افزایش امتیاز", "👤 اطلاعات حساب"],
        ["💳 تبدیل امتیاز به شانس", "🎰 ثبت نام در قرعه کشی"],
        ["🏆 لیدربورد"]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        ["🎯 انتخاب برنده", "📊 آمار"],
        ["📢 ارسال پیام به همه", "📋 لیست کاربران"],
        ["🏆 لیدربورد", "🔄 ریست قرعه‌کشی"]
    ], resize_keyboard=True)

# ====== چک عضویت ======
async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE):
    for ch in CHANNEL_IDS:
        try:
            member = await context.bot.get_chat_member(ch, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

# ====== استارت ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"/start from {user.id}")
    ref = None
    if context.args:
        try:
            ref = int(context.args[0])
        except:
            pass

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                   (user.id, user.username or user.first_name))
    conn.commit()

    # رفرال
    if ref and ref != user.id:
        cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user.id,))
        if cursor.fetchone()[0] is None:
            cursor.execute("UPDATE users SET referrer_id = ? WHERE user_id = ?", (ref, user.id))
            cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (ref,))
            conn.commit()
            logger.info(f"Referral: {ref} got +1 point")
            try:
                await context.bot.send_message(ref, "🎉 یک کاربر جدید با لینک شما وارد شد و ۱ امتیاز گرفتید!")
            except:
                pass

    # منو
    if user.id in ADMIN_IDS:
        await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 خوش آمدید!", reply_markup=main_menu())

# ====== هندل پیام ======
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    logger.info(f"Message from {uid}: {text}")

    # ====== بخش مدیر ======
    if uid in ADMIN_IDS:
        # آمار
        if text == "📊 آمار":
            cursor.execute("SELECT COUNT(*) FROM users"); total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered = 1"); reg = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM raffle"); chance = cursor.fetchone()[0]
            await update.message.reply_text(f"📊 کاربران: {total}\n✅ ثبت‌نام: {reg}\n🎟️ شانس: {chance}")

        # ریست
        elif text == "🔄 ریست قرعه‌کشی":
            cursor.execute("DELETE FROM raffle")
            cursor.execute("UPDATE users SET is_registered=0, chances=0")
            conn.commit()
            await update.message.reply_text("✅ ریست شد.")

        # لیست کاربران
        elif text == "📋 لیست کاربران":
            cursor.execute("SELECT user_id, username FROM users")
            lst = cursor.fetchall()
            txt = "\n".join([f"{u[1]} ({u[0]})" for u in lst]) or "هیچ کاربری"
            await update.message.reply_text(f"📋 کاربران:\n{txt}")

        # ارسال به همه
        elif text == "📢 ارسال پیام به همه":
            context.user_data["bc"] = True
            await update.message.reply_text("📢 پیام خود را ارسال کنید.")

        elif context.user_data.get("bc"):
            cursor.execute("SELECT user_id FROM users"); users = cursor.fetchall()
            cnt = 0
            for (to_id,) in users:
                try:
                    if update.message.text:
                        await context.bot.send_message(to_id, update.message.text)
                    elif update.message.photo:
                        await context.bot.send_photo(to_id, update.message.photo[-1].file_id, caption=update.message.caption or "")
                    elif update.message.video:
                        await context.bot.send_video(to_id, update.message.video.file_id, caption=update.message.caption or "")
                    cnt += 1
                except:
                    pass
            context.user_data["bc"] = False
            await update.message.reply_text(f"✅ به {cnt} ارسال شد.")

        # انتخاب برنده
        elif text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            part = [r[0] for r in cursor.fetchall()]
            if not part:
                await update.message.reply_text("⚠️ هیچ شرکت‌کننده‌ای نیست!")
            else:
                win = random.choice(part)
                await update.message.reply_text(f"🏆 برنده: {win}")
                try:
                    await context.bot.send_message(win, "🎉 تبریک! شما برنده شدید!")
                except:
                    await update.message.reply_text("⚠️ نتوانست به برنده پیام دهد.")
        # لیدربورد
        elif text == "🏆 لیدربورد":
            cursor.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT 10")
            top = cursor.fetchall()
            lb = "\n".join([f"{i+1}. @{u} — {p}" for i,(u,p) in enumerate(top)])
            await update.message.reply_text("🏆 لیدربورد:\n"+lb)

        return  # پایان مدیر

    # ====== بخش کاربر ======
    if not await is_member(uid, context):
        await update.message.reply_text("🔒 ابتدا در کانال‌ها عضو شوید.")
        return

    # ثبت‌نام
    if text == "🎰 ثبت نام در قرعه کشی":
        cursor.execute("SELECT is_registered FROM users WHERE user_id = ?", (uid,))
        if cursor.fetchone()[0] == 1:
            await update.message.reply_text("⚠️ شما قبلاً ثبت‌نام کردید.")
        else:
            cursor.execute("UPDATE users SET is_registered=1 WHERE user_id = ?", (uid,))
            cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (uid,))
            conn.commit()
            await update.message.reply_text("✅ ثبت‌نام شد!")

    # تبدیل امتیاز
    elif text == "💳 تبدیل امتیاز به شانس":
        cursor.execute("SELECT points FROM users WHERE user_id = ?", (uid,))
        pts = cursor.fetchone()[0]
        if pts > 0:
            cursor.execute("UPDATE users SET points=0, chances=chances+? WHERE user_id=?", (pts,uid))
            for _ in range(pts):
                cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (uid,))
            conn.commit()
            await update.message.reply_text(f"✅ تبدیل {pts} امتیاز به شانس!")
        else:
            await update.message.reply_text("⚠️ امتیازی ندارید.")

    # افزایش امتیاز (لینک)
    elif text == "💎 افزایش امتیاز":
        link = f"https://t.me/{context.bot.username}?start={uid}"
        await update.message.reply_text(f"🔗 لینک دعوت:\n{link}")

    # اطلاعات حساب
    elif text == "👤 اطلاعات حساب":
        cursor.execute("SELECT username, points, chances, is_registered FROM users WHERE user_id = ?", (uid,))
        u,p,c,reg = cursor.fetchone()
        await update.message.reply_text(f"👤 @{u}\n💎 {p} امتیاز\n🎟️ {c} شانس\n📌 {'ثبت‌نام شده' if reg else 'ثبت‌نام‌نشده'}")

    # لیدربورد
    elif text == "🏆 لیدربورد":
        cursor.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT 10")
        top = cursor.fetchall()
        lb = "\n".join([f"{i+1}. @{u} — {p}" for i,(u,p) in enumerate(top)])
        await update.message.reply_text("🏆 لیدربورد:\n"+lb)

# ====== error handler ======
async def error_handler(update, context):
    logger.error(f"Exception: {context.error}")
    if update.effective_message:
        await update.effective_message.reply_text("⚠️ مشکلی پیش اومد، بعداً امتحان کنید.")

# ====== اجرا ======
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.ALL, handle_message))
app.add_error_handler(error_handler)

logger.info("ربات در حال اجراست...")
app.run_polling()
