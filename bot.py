import sqlite3
import random
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==================== تنظیمات ربات ====================
BOT_TOKEN = "8227817016:AAGwqzCfx6abijss3ksZyju1ifXHLJ1lNCw"
ADMIN_IDS = [6181430071, 5944937406]  # آیدی ادمین‌ها

# ==================== وبهوک ====================
# حذف وبهوک قبل از اجرای Polling برای جلوگیری از تداخل
delete_webhook_url = f"https://api.telegram.org/bot8227817016:AAGwqzCfx6abijss3ksZyju1ifXHLJ1lNCw/deleteWebhook"
print(requests.get(delete_webhook_url).json())

# ==================== اتصال به دیتابیس ====================
conn = sqlite3.connect("raffle.db", check_same_thread=False)
cursor = conn.cursor()

# جدول کاربران
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        points INTEGER DEFAULT 0,
        chances INTEGER DEFAULT 0,
        is_registered INTEGER DEFAULT 0
    )
    """
)

# جدول قرعه‌کشی
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS raffle (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER
    )
    """
)

# جدول کانال‌های جوین اجباری
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE
    )
    """
)
conn.commit()

# ==================== منوها ====================
def main_menu():
    """کیبورد اصلی برای کاربران"""
    return ReplyKeyboardMarkup(
        [
            ["💎 افزایش امتیاز", "👤 اطلاعات حساب"],
            ["💳 تبدیل امتیاز به شانس", "🎰 ثبت نام در قرعه کشی"]
        ],
        resize_keyboard=True
    )

def admin_menu():
    """کیبورد پنل مدیریت"""
    return ReplyKeyboardMarkup(
        [
            ["🎯 انتخاب برنده", "📊 آمار"],
            ["📢 ارسال پیام به همه", "📋 لیست کاربران"],
            ["➕ اضافه کردن کانال جوین اجباری", "🔄 ریست قرعه‌کشی"]
        ],
        resize_keyboard=True
    )

# ==================== توابع کمکی ====================
def get_channels():
    """بازگرداندن لیست کانال‌های جوین اجباری از دیتابیس"""
    cursor.execute("SELECT username FROM channels")
    return [row[0] for row in cursor.fetchall()]

async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """بررسی عضویت کاربر در تمام کانال‌های ذخیره‌شده"""
    for channel in get_channels():
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

# ==================== هندلرها ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دستور /start: ثبت کاربر و نمایش منو مناسب"""
    user = update.effective_user
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user.id, user.username or user.first_name)
    )
    conn.commit()

    if user.id in ADMIN_IDS:
        await update.message.reply_text(
            "👑 به پنل مدیریت خوش آمدید!",
            reply_markup=admin_menu()
        )
    else:
        await update.message.reply_text(
            "🎉 به ربات قرعه‌کشی خوش آمدید!",
            reply_markup=main_menu()
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پردازش پیام کاربر یا ادمین بر اساس متن دریافتی"""
    text = update.message.text
    user_id = update.effective_user.id

    # ===== پنل مدیریت =====
    if user_id in ADMIN_IDS:
        # نمایش آمار
        if text == "📊 آمار":
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered = 1")
            registered = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM raffle")
            total_chances = cursor.fetchone()[0]
            await update.message.reply_text(
                f"📊 آمار:\n👥 کاربران: {total_users}\n✅ ثبت‌نام: {registered}\n🎟️ شانس‌ها: {total_chances}"
            )

        # ریست قرعه‌کشی
        elif text == "🔄 ریست قرعه‌کشی":
            cursor.execute("DELETE FROM raffle")
            cursor.execute("UPDATE users SET is_registered = 0, chances = 0")
            conn.commit()
            await update.message.reply_text(
                "✅ قرعه‌کشی ریست شد. کاربران حذف نشدند ولی همه وضعیت‌ها صفر شدند."
            )

        # لیست کاربران
        elif text == "📋 لیست کاربران":
            cursor.execute("SELECT username FROM users")
            users = cursor.fetchall()
            if not users:
                await update.message.reply_text("📋 هیچ کاربری وجود ندارد.")
            else:
                user_list = "\n".join(
                    [f"@{u[0]}" if u[0] else "بدون نام" for u in users]
                )
                await update.message.reply_text(f"📋 لیست کاربران:\n{user_list[:3500]}")

        # ارسال پیام به همه
        elif text == "📢 ارسال پیام به همه":
            context.user_data["broadcast"] = True
            await update.message.reply_text("📢 پیام خود را (متن/عکس/ویدیو) ارسال کنید.")
        elif context.user_data.get("broadcast"):
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()
            for (uid,) in users:
                try:
                    if update.message.text:
                        await context.bot.send_message(uid, update.message.text)
                    elif update.message.photo:
                        await context.bot.send_photo(uid, update.message.photo[-1].file_id, caption=update.message.caption or "")
                    elif update.message.video:
                        await context.bot.send_video(uid, update.message.video.file_id, caption=update.message.caption or "")
                except:
                    pass
            context.user_data["broadcast"] = False
            await update.message.reply_text("✅ پیام به همه ارسال شد.")

        # اضافه کردن کانال جوین اجباری
        elif text == "➕ اضافه کردن کانال جوین اجباری":
            context.user_data["adding_channel"] = True
            await update.message.reply_text(
                "🔗 لطفاً یوزرنیم کانال را وارد کنید (مثلاً @channel)"
            )
        elif context.user_data.get("adding_channel"):
            channel = text.strip()
            if not channel.startswith("@"):
                await update.message.reply_text(
                    "❌ یوزرنیم باید با @ شروع شود. لطفاً دوباره وارد کنید."
                )
            else:
                try:
                    cursor.execute(
                        "INSERT OR IGNORE INTO channels (username) VALUES (?)",
                        (channel,)
                    )
                    conn.commit()
                    await update.message.reply_text(f"✅ کانال {channel} اضافه شد.")
                except:
                    await update.message.reply_text("❌ خطا در افزودن کانال.")
                context.user_data["adding_channel"] = False

        # انتخاب برنده
        elif text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            participants = [r[0] for r in cursor.fetchall()]
            if not participants:
                await update.message.reply_text("⚠️ هیچ شرکت‌کننده‌ای وجود ندارد.")
            else:
                winner_id = random.choice(participants)
                cursor.execute(
                    "SELECT username FROM users WHERE user_id = ?", (winner_id,)
                )
                winner = cursor.fetchone()
                winner_name = f"@{winner[0]}" if winner and winner[0] else f"User {winner_id}"
                await update.message.reply_text(f"🏆 برنده قرعه‌کشی: {winner_name}")
                try:
                    await context.bot.send_message(winner_id, "🎉 تبریک! شما برنده قرعه‌کشی شدید!")
                except:
                    await update.message.reply_text("⚠️ نتوانستیم به برنده پیام بدهیم.")

    # ===== بخش کاربران =====
    else:
        if not await is_member(user_id, context):
            await update.message.reply_text(
                "🔒 برای استفاده از ربات باید در کانال‌های تعیین شده عضو شوید."
            )
            return
        if text == "🎰 ثبت نام در قرعه کشی":
            cursor.execute(
                "SELECT is_registered FROM users WHERE user_id = ?", (user_id,)
            )
            registered = cursor.fetchone()[0]
            if registered:
                await update.message.reply_text("⚠️ شما قبلاً در قرعه‌کشی ثبت‌نام کرده‌اید.")
            else:
                cursor.execute(
                    "UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,)
                )
                cursor.execute(
                    "INSERT INTO raffle (user_id) VALUES (?)", (user_id,)
                )
                conn.commit()
                await update.message.reply_text("✅ شما در قرعه‌کشی ثبت‌نام شدید!")
        elif text == "💎 افزایش امتیاز":
            link = f"https://t.me/{context.bot.username}?start={user_id}"
            await update.message.reply_text(f"🔗 لینک دعوت شما:\n{link}")
        elif text == "💳 تبدیل امتیاز به شانس":
            cursor.execute(
                "SELECT points FROM users WHERE user_id = ?", (user_id,)
            )
            points = cursor.fetchone()[0]
            if points > 0:
                cursor.execute(
                    "UPDATE users SET points = 0, chances = chances + ? WHERE user_id = ?", (points, user_id)
                )
                for _ in range(points):
                    cursor.execute(
                        "INSERT INTO raffle (user_id) VALUES (?)", (user_id,)
                    )
                conn.commit()
                await update.message.reply_text(f"✅ {points} امتیاز شما به شانس تبدیل شد!")
            else:
                await update.message.reply_text("⚠️ شما امتیازی ندارید.")
        elif text == "👤 اطلاعات حساب":
            cursor.execute(
                "SELECT username, points, chances, is_registered FROM users WHERE user_id = ?", (user_id,)
            )
            username, points, chances, is_registered = cursor.fetchone()
            status = "✅ ثبت‌نام شده" if is_registered else "❌ ثبت‌نام نشده"
            await update.message.reply_text(
                f"📊 اطلاعات شما:\n\n👤 کاربر: @{username}\n🎯 وضعیت: {status}\n💎 امتیاز: {points}\n🎟️ شانس: {chances}"
            )

# ============== اجرای ربات ==============
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.ALL, handle_message))

print("🤖 ربات در حال اجراست...")
app.run_po
