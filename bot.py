import sqlite3
import random
import requests
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8227817016:AAFaI1J3KPn-8WCrXl2MsvPtKTYoDL4TINo"
ADMIN_IDS = [6181430071, 5944937406]  # آیدی مدیرها

# حذف وبهوک قبلی (در صورت استفاده)
requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")

# اتصال به دیتابیس
conn = sqlite3.connect("raffle.db", check_same_thread=False)
cursor = conn.cursor()

# جداول
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    chances INTEGER DEFAULT 0,
    is_registered INTEGER DEFAULT 0,
    ref_by INTEGER
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
    username TEXT UNIQUE
)
""")
conn.commit()

# اگر کانالی ثبت نشده، دو کانال نمونه اضافه کن
cursor.execute("SELECT COUNT(*) FROM channels")
if cursor.fetchone()[0] == 0:
    cursor.execute("INSERT INTO channels (username) VALUES (?)", ("@fcxter",))
    cursor.execute("INSERT INTO channels (username) VALUES (?)", ("@FCXTERGP",))
    conn.commit()

# منوها
def main_menu():
    return ReplyKeyboardMarkup([
        ["💎 افزایش امتیاز", "👤 اطلاعات حساب"],
        ["💳 تبدیل امتیاز به شانس", "🎰 ثبت نام در قرعه کشی"],
        ["🏆 لیدربورد کاربران"]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        ["🎯 انتخاب برنده", "📊 آمار"],
        ["📢 ارسال پیام به همه", "📋 لیست کاربران"],
        ["🏆 لیدربورد کاربران", "🏆 لیدربورد مدیران"],
        ["➕ افزودن کانال", "📋 لیست کانال‌های جوین اجباری"],
        ["❌ حذف کانال جوین اجباری", "🔄 ریست قرعه‌کشی"]
    ], resize_keyboard=True)

# بررسی عضویت در کانال‌ها
async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT username FROM channels")
    for (ch,) in cursor.fetchall():
        try:
            m = await context.bot.get_chat_member(ch, user_id)
            if m.status not in ("member", "administrator", "creator"):
                return False
        except:
            return False
    return True

# هندلر /start با سیستم رفرال محدودشده
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    ref = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user.id else None

    # ثبت یا بروزرسانی کاربر
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                   (user.id, user.username or user.first_name))
    if ref:
        # بررسی سقف مجموع points + chances
        cursor.execute("SELECT points, chances FROM users WHERE user_id = ?", (ref,))
        row = cursor.fetchone()
        if row:
            total = row[0] + row[1]
            if total < 50:
                # یک امتیاز اضافه کن
                cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (ref,))
                try:
                    await context.bot.send_message(ref, "🎉 با دعوت یک کاربر جدید، ۱ امتیاز گرفتید!")
                except:
                    pass
    conn.commit()

    # نمایش منو
    if user.id in ADMIN_IDS:
        await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 خوش آمدید!", reply_markup=main_menu())

# هندلر کلی پیام‌ها
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id

    # بخش مدیر
    if uid in ADMIN_IDS:
        if text == "📊 آمار":
            cursor.execute("SELECT COUNT(*) FROM users"); total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered=1"); reg = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM raffle"); ch = cursor.fetchone()[0]
            await update.message.reply_text(f"👥 کاربران: {total}\n✅ ثبت‌نام: {reg}\n🎟 شانس: {ch}")

        elif text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            parts = [r[0] for r in cursor.fetchall()]
            if not parts:
                await update.message.reply_text("❌ شرکت‌کننده نیست.")
            else:
                win = random.choice(parts)
                cursor.execute("SELECT username FROM users WHERE user_id = ?", (win,))
                name = cursor.fetchone()[0] or ""
                await update.message.reply_text(f"🏆 برنده: @{name}")

        elif text == "📢 ارسال پیام به همه":
            await update.message.reply_text("✉️ پیام را ارسال کنید:")
            context.user_data["bcast"] = True

        elif context.user_data.get("bcast"):
            cnt = 0
            cursor.execute("SELECT user_id FROM users")
            for (x,) in cursor.fetchall():
                try:
                    await context.bot.send_message(x, text)
                    cnt += 1
                except: pass
            await update.message.reply_text(f"✅ به {cnt} نفر ارسال شد.")
            context.user_data["bcast"] = False

        elif text == "📋 لیست کاربران":
            cursor.execute("SELECT username FROM users")
            names = "\n".join(f"@{u[0]}" for u in cursor.fetchall())
            await update.message.reply_text(names or "—")

        elif text == "➕ افزودن کانال":
            await update.message.reply_text("آیدی کانال با @ را ارسال کنید:")
            context.user_data["add_ch"] = True

        elif context.user_data.get("add_ch"):
            if text.startswith("@"):
                cursor.execute("INSERT OR IGNORE INTO channels (username) VALUES (?)", (text,))
                conn.commit()
                await update.message.reply_text("✅ اضافه شد.")
            else:
                await update.message.reply_text("❌ باید با @ شروع شود.")
            context.user_data["add_ch"] = False

        elif text == "📋 لیست کانال‌های جوین اجباری":
            cursor.execute("SELECT username FROM channels")
            lst = "\n".join(c[0] for c in cursor.fetchall())
            await update.message.reply_text(lst or "—")

        elif text == "❌ حذف کانال جوین اجباری":
            await update.message.reply_text("آیدی کانال را ارسال کنید:")
            context.user_data["del_ch"] = True

        elif context.user_data.get("del_ch"):
            cursor.execute("DELETE FROM channels WHERE username = ?", (text,))
            conn.commit()
            await update.message.reply_text("✅ حذف شد.")
            context.user_data["del_ch"] = False

        elif text == "🔄 ریست قرعه‌کشی":
            cursor.execute("DELETE FROM raffle")
            cursor.execute("UPDATE users SET is_registered=0, chances=0")
            conn.commit()
            await update.message.reply_text("♻️ ریست شد.")

        elif text == "🏆 لیدربورد کاربران":
            cursor.execute("SELECT username, chances FROM users ORDER BY chances DESC LIMIT 10")
            lines = [f"{i+1}. @{u} – {c} شانس" for i,(u,c) in enumerate(cursor.fetchall())]
            await update.message.reply_text("🏆 برترین کاربران:\n\n" + "\n".join(lines))

        elif text == "🏆 لیدربورد مدیران":
            cursor.execute("SELECT ref_by, COUNT(*) FROM users WHERE ref_by IS NOT NULL GROUP BY ref_by ORDER BY COUNT(*) DESC LIMIT 10")
            lines = []
            for i,(rid,cnt) in enumerate(cursor.fetchall(),1):
                cursor.execute("SELECT username FROM users WHERE user_id=?", (rid,))
                nm = cursor.fetchone()[0] or f"User{rid}"
                lines.append(f"{i}. @{nm} – {cnt} دعوت")
            await update.message.reply_text("🏆 برترین معرف‌ها:\n\n" + "\n".join(lines))

        else:
            await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_menu())

    # بخش کاربران عادی
    else:
        if not await is_member(uid, context):
            cursor.execute("SELECT username FROM channels")
            btns = [[InlineKeyboardButton(f"عضویت در {c[0]}", url=f"https://t.me/{c[0][1:]}")] for c in cursor.fetchall()]
            await update.message.reply_text("🔒 لطفاً عضو شوید:", reply_markup=InlineKeyboardMarkup(btns))
            return

        if text == "🎰 ثبت نام در قرعه کشی":
            cursor.execute("SELECT is_registered FROM users WHERE user_id=?", (uid,))
            if cursor.fetchone()[0]:
                await update.message.reply_text("⚠️ قبلاً ثبت نام کردی.")
            else:
                cursor.execute("UPDATE users SET is_registered=1 WHERE user_id=?", (uid,))
                cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (uid,))
                cursor.execute("UPDATE users SET chances=chances+1 WHERE user_id=?", (uid,))
                conn.commit()
                await update.message.reply_text("✅ ثبت شد!")

        elif text == "💎 افزایش امتیاز":
            link = f"https://t.me/{context.bot.username}?start={uid}"
            await update.message.reply_text("🔗 لینک دعوت:\n" + link)

        elif text == "💳 تبدیل امتیاز به شانس":
            cursor.execute("SELECT points FROM users WHERE user_id=?", (uid,))
            pts = cursor.fetchone()[0]
            if pts>0:
                cursor.execute("UPDATE users SET points=0, chances=chances+? WHERE user_id=?", (pts,uid))
                for _ in range(pts):
                    cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (uid,))
                conn.commit()
                await update.message.reply_text(f"✅ {pts} امتیاز تبدیل شد!")
            else:
                await update.message.reply_text("⚠️ امتیازی نداری.")

        elif text == "👤 اطلاعات حساب":
            cursor.execute("SELECT username, points, chances, is_registered FROM users WHERE user_id=?", (uid,))
            u,pts,chs,reg = cursor.fetchone()
            st = "✅ ثبت‌نام شده" if reg else "❌ ثبت‌نام نشده"
            await update.message.reply_text(f"👤 @{u}\n💎 امتیاز:{pts}\n🎟 شانس:{chs}\n{st}")

# اجرا
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
print("🤖 Bot is running...")
app.run_polling()
