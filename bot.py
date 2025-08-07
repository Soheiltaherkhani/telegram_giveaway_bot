import sqlite3
import random
import requests
from telegram import (
    Update, 
    ReplyKeyboardMarkup, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes
)

# ==================== تنظیمات ====================
BOT_TOKEN = "8227817016:AAGwqzCfx6abijss3ksZyju1ifXHLJ1lNCw"
ADMIN_IDS = [6181430071, 5944937406]

# حذف وب‌هوک قبلی (در صورت وجود)
requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")

# ==================== دیتابیس ====================
conn = sqlite3.connect("raffle.db", check_same_thread=False)
cursor = conn.cursor()

# جدول کاربران
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    chances INTEGER DEFAULT 0,
    is_registered INTEGER DEFAULT 0,
    referred_by INTEGER
)
""")
# جدول قرعه‌کشی
cursor.execute("""
CREATE TABLE IF NOT EXISTS raffle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER
)
""")
# جدول کانال‌های اجباری
cursor.execute("""
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE
)
""")
conn.commit()

# اگر هنوز کانالی در جدول نیست، نمونه اولیه اضافه می‌کند
cursor.execute("SELECT COUNT(*) FROM channels")
if cursor.fetchone()[0] == 0:
    cursor.execute("INSERT INTO channels (username) VALUES (?)", ("@fcxter",))
    cursor.execute("INSERT INTO channels (username) VALUES (?)", ("@FCXTERGP",))
    conn.commit()

# ==================== منوها ====================
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
        ["➕ افزودن کانال", "📋 لیست کانال‌های جوین اجباری"],
        ["❌ حذف کانال جوین اجباری", "🔄 ریست قرعه‌کشی"],
        ["🏆 لیدربورد"]
    ], resize_keyboard=True)

# ==================== کمک‌کننده‌ها ====================
async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """بررسی عضویت در همه‌ی کانال‌های اجباری"""
    cursor.execute("SELECT username FROM channels")
    for (ch,) in cursor.fetchall():
        try:
            m = await context.bot.get_chat_member(ch, user_id)
            if m.status not in ("member", "administrator", "creator"):
                return False
        except:
            return False
    return True

# ==================== هندلر /start ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    ref = int(args[0]) if args and args[0].isdigit() else None

    # ثبت اولیه کاربر
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user.id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
            (user.id, user.username or user.first_name, ref)
        )
        # امتیاز دادن به معرف (یک‌بار)
        if ref and ref != user.id:
            cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (ref,))
            try:
                await context.bot.send_message(ref, "🎉 یک نفر با لینک شما عضو شد و 1 امتیاز گرفتید!")
            except:
                pass
    conn.commit()

    # منوی مناسب را نشان بده
    if user.id in ADMIN_IDS:
        await update.message.reply_text("👑 به پنل مدیریت خوش آمدید!", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید!", reply_markup=main_menu())

# ==================== هندلر پیام‌ها ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # ----- بخش ادمین -----
    if user_id in ADMIN_IDS:

        if text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            parts = [r[0] for r in cursor.fetchall()]
            if not parts:
                await update.message.reply_text("❌ هیچ شرکت‌کننده‌ای نیست.")
            else:
                win = random.choice(parts)
                cursor.execute("SELECT username FROM users WHERE user_id = ?", (win,))
                uname = cursor.fetchone()[0] or ""
                await update.message.reply_text(f"🏆 برنده: @{uname}")
                try:
                    await context.bot.send_message(win, "🎉 تبریک! شما برنده شدید!")
                except: pass

        elif text == "📊 آمار":
            cursor.execute("SELECT COUNT(*) FROM users"); total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered=1"); reg = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM raffle"); ch = cursor.fetchone()[0]
            await update.message.reply_text(f"👥 کل کاربران: {total}\n✅ ثبت‌نام: {reg}\n🎟️ شانس‌ها: {ch}")

        elif text == "📋 لیست کاربران":
            cursor.execute("SELECT username FROM users")
            lst = "\n".join(f"@{u[0]}" for u in cursor.fetchall())
            await update.message.reply_text("📋 کاربران:\n" + (lst or "—"))

        elif text == "📢 ارسال پیام به همه":
            await update.message.reply_text("✉️ پیام به همه را ارسال کنید:")
            context.user_data["broadcast"] = True

        elif context.user_data.get("broadcast"):
            cnt = 0
            cursor.execute("SELECT user_id FROM users")
            for (uid,) in cursor.fetchall():
                try:
                    await context.bot.send_message(uid, text)
                    cnt += 1
                except: pass
            context.user_data["broadcast"] = False
            await update.message.reply_text(f"✅ پیام به {cnt} کاربر ارسال شد.")

        elif text == "➕ افزودن کانال":
            await update.message.reply_text("🔗 آیدی کانال (با @) را ارسال کنید:")
            context.user_data["add_chan"] = True

        elif context.user_data.get("add_chan"):
            if text.startswith("@"):
                cursor.execute("INSERT OR IGNORE INTO channels (username) VALUES (?)", (text,))
                conn.commit()
                await update.message.reply_text("✅ کانال اضافه شد.")
            else:
                await update.message.reply_text("❌ باید با @ شروع شود.")
            context.user_data["add_chan"] = False

        elif text == "📋 لیست کانال‌های جوین اجباری":
            cursor.execute("SELECT username FROM channels")
            cl = "\n".join(f"– {c[0]}" for c in cursor.fetchall())
            await update.message.reply_text("📋 لیست کانال‌ها:\n" + (cl or "—"))

        elif text == "❌ حذف کانال جوین اجباری":
            await update.message.reply_text("❌ آیدی کانال را ارسال کنید:")
            context.user_data["del_chan"] = True

        elif context.user_data.get("del_chan"):
            cursor.execute("DELETE FROM channels WHERE username = ?", (text,))
            conn.commit()
            await update.message.reply_text("✅ کانال حذف شد.")
            context.user_data["del_chan"] = False

        elif text == "🔄 ریست قرعه‌کشی":
            cursor.execute("DELETE FROM raffle")
            cursor.execute("UPDATE users SET is_registered=0, chances=0")
            conn.commit()
            await update.message.reply_text("♻️ ریست شد.")

        elif text == "🏆 لیدربورد":
            cursor.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT 10")
            lines = [f"{i+1}. @{u} – {p} امتیاز" for i,(u,p) in enumerate(cursor.fetchall())]
            await update.message.reply_text("🏆 لیدربورد معرف‌ها:\n" + "\n".join(lines))

        else:
            await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_menu())

    # ----- بخش کاربر معمولی -----
    else:
        # چک عضویت
        if not await is_member(user_id, context):
            cursor.execute("SELECT username FROM channels")
            buttons = [
                [InlineKeyboardButton(f"عضویت در {c[0]}", url=f"https://t.me/{c[0][1:]}")]
                for c in cursor.fetchall()
            ]
            await update.message.reply_text(
                "🔒 برای استفاده باید عضو کانال‌ها باشید:", 
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return

        # دکمه‌های عادی
        if text == "🎰 ثبت نام در قرعه کشی":
            cursor.execute("SELECT is_registered FROM users WHERE user_id = ?", (user_id,))
            if cursor.fetchone()[0]:
                await update.message.reply_text("⚠️ قبلاً ثبت‌نام کرده‌اید.")
            else:
                cursor.execute("UPDATE users SET is_registered=1 WHERE user_id=?", (user_id,))
                cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
                conn.commit()
                await update.message.reply_text("✅ ثبت‌نام شدید!")

        elif text == "💎 افزایش امتیاز":
            ln = f"https://t.me/{context.bot.username}?start={user_id}"
            await update.message.reply_text("🔗 لینک دعوت شما:\n" + ln)

        elif text == "💳 تبدیل امتیاز به شانس":
            cursor.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
            pts = cursor.fetchone()[0]
            if pts>0:
                cursor.execute("UPDATE users SET points=0, chances=chances+? WHERE user_id=?", (pts,user_id))
                for _ in range(pts):
                    cursor.execute("INSERT INTO raffle (user_id) VALUES (?)",(user_id,))
                conn.commit()
                await update.message.reply_text(f"✅ {pts} امتیاز تبدیل شد!")
            else:
                await update.message.reply_text("⚠️ امتیازی ندارید.")

        elif text == "👤 اطلاعات حساب":
            cursor.execute("SELECT username, points, chances, is_registered FROM users WHERE user_id=?", (user_id,))
            u,pts,ch,reg = cursor.fetchone()
            st = "✅ ثبت‌نام شده" if reg else "❌ ثبت‌نام نشده"
            await update.message.reply_text(
                f"👤 @{u}\n💎 امتیاز: {pts}\n🎟️ شانس: {ch}\n📌 وضعیت: {st}"
            )

        elif text == "🏆 لیدربورد":
            cursor.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT 10")
            lb = "\n".join(f"{i+1}. @{u} – {p} امتیاز" for i,(u,p) in enumerate(cursor.fetchall()))
            await update.message.reply_text("🏆 لیدربورد کاربران:\n" + lb)

# ==================== اجرای ربات ====================
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🤖 ربات فعال است...")
app.run_polling()
