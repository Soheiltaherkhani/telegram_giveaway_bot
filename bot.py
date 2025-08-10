import sqlite3
import random
import requests
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ————— تنظیمات —————
BOT_TOKEN = "8227817016:AAFfUpgf2u2xpj2unEtl6h4gEqVGdAxxzm8"
ADMIN_IDS = [6181430071, 5944937406]  # آیدی مدیرها

# حذف وب‌هوک قبلی (در صورت نیاز)
requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")

# ————— اتصال به دیتابیس —————
conn = sqlite3.connect("raffle.db", check_same_thread=False)
cursor = conn.cursor()

# جدول کاربران
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY,
    username      TEXT,
    points        INTEGER DEFAULT 0,
    chances       INTEGER DEFAULT 0,
    is_registered INTEGER DEFAULT 0
)
"""
)

# جدول قرعه‌کشی
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS raffle (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER
)
"""
)

# جدول کانال‌های اجباری
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS channels (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE
)
"""
)

conn.commit()

# ————— منوها —————
def main_menu():
    return ReplyKeyboardMarkup(
        [
            ["💎 افزایش امتیاز", "👤 اطلاعات حساب"],
            ["💳 تبدیل امتیاز به شانس", "🎰 ثبت نام در قرعه کشی"],
        ],
        resize_keyboard=True,
    )


def admin_menu():
    return ReplyKeyboardMarkup(
        [
            ["🎯 انتخاب برنده", "📊 آمار"],
            ["📢 ارسال پیام به همه", "📋 لیست کاربران"],
            ["➕ افزودن کانال", "📋 لیست کانال‌های جوین اجباری"],
            ["❌ حذف کانال جوین اجباری", "🔄 ریست قرعه‌کشی"],
            ["🏆 لیدربورد کاربران"],
        ],
        resize_keyboard=True,
    )


# ————— بررسی عضویت در کانال‌های اجباری —————
async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    cursor.execute("SELECT username FROM channels")
    rows = cursor.fetchall()
    # اگر هیچ کانالی تعریف نشده باشه، نیازی به ممبر بودن نیست
    if not rows:
        return True
    for (ch,) in rows:
        try:
            # ch باید چیزی مثل "@channel" باشه یا "channel"؛ get_chat_member با username هم کار می‌کنه
            member = await context.bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except Exception:
            # در صورتی که بررسی کانال با خطا مواجه شد، فرض می‌کنیم کاربر عضو نیست
            return False
    return True


# ————— هندلر /start —————
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    # ثبت اولیه کاربر
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user.id, user.username or user.first_name),
    )
    conn.commit()

    # سیستم رفرال با محدودیت سقف ۵۰
    if args:
        try:
            ref_id = int(args[0])
            if ref_id != user.id:
                cursor.execute("SELECT points, chances FROM users WHERE user_id=?", (ref_id,))
                row = cursor.fetchone()
                if row:
                    pts = row[0] or 0
                    ch = row[1] or 0
                    if pts + ch < 50:
                        cursor.execute("UPDATE users SET points = points + 1 WHERE user_id=?", (ref_id,))
                        conn.commit()
                        try:
                            await context.bot.send_message(ref_id, "🎉 با دعوت یک کاربر، ۱ امتیاز گرفتید!")
                        except Exception:
                            pass
        except Exception:
            pass

    # نمایش منو بر اساس نقش
    if user.id in ADMIN_IDS:
        await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 خوش آمدید!", reply_markup=main_menu())


# ————— هندلر پیام‌های متنی —————
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = (msg.text or "").strip()
    uid = update.effective_user.id

    # === بخش مدیر ===
    if uid in ADMIN_IDS:

        # آمار کلی
        if text == "📊 آمار":
            cursor.execute("SELECT COUNT(*) FROM users")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered=1")
            reg = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM raffle")
            chances = cursor.fetchone()[0]
            await msg.reply_text(f"👥 کاربران: {total}\n✅ ثبت‌نام: {reg}\n🎟 شانس‌ها: {chances}")

        # انتخاب برنده
        elif text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            parts = [r[0] for r in cursor.fetchall()]
            if not parts:
                await msg.reply_text("⚠️ شرکت‌کننده‌ای نیست.")
            else:
                winner = random.choice(parts)
                cursor.execute("SELECT username FROM users WHERE user_id=?", (winner,))
                name_row = cursor.fetchone()
                name = name_row[0] if name_row and name_row[0] else str(winner)
                # اگر اسم با @ شروع نشده، قبلش @ بذار
                if not name.startswith("@"):
                    await msg.reply_text(f"🏆 برنده: @{name}")
                else:
                    await msg.reply_text(f"🏆 برنده: {name}")

        # شروع حالت ارسال همگانی
        elif text == "📢 ارسال پیام به همه":
            await msg.reply_text("📤 لطفاً پیام خود را (متن/عکس/ویدیو) ارسال کنید.")
            context.user_data["broadcast"] = True

        # لیست کاربران
        elif text == "📋 لیست کاربران":
            rows = cursor.execute("SELECT username, user_id FROM users").fetchall()
            lines = [f"@{u or 'ناشناس'} ({i})" for u, i in rows]
            preview = "\n".join(lines[:100]) or "—"
            await msg.reply_text("👥 لیست کاربران:\n" + preview)

        # افزودن کانال
        elif text == "➕ افزودن کانال":
            await msg.reply_text("🔗 لطفاً یوزرنیم کانال را با @ ارسال کنید.")
            context.user_data["add_ch"] = True

        elif context.user_data.get("add_ch"):
            ch = text.strip()
            if ch.startswith("@"):
                cursor.execute("INSERT OR IGNORE INTO channels (username) VALUES (?)", (ch,))
                conn.commit()
                await msg.reply_text(f"✅ کانال {ch} اضافه شد.")
            else:
                await msg.reply_text("⚠️ یوزرنیم باید با @ شروع شود.")
            context.user_data["add_ch"] = False

        # لیست کانال‌های جوین اجباری
        elif text == "📋 لیست کانال‌های جوین اجباری":
            cursor.execute("SELECT username FROM channels")
            ch_rows = [c[0] for c in cursor.fetchall()]
            await msg.reply_text("📢 کانال‌های اجباری:\n" + ("\n".join(ch_rows) or "—"))

        # حذف کانال
        elif text == "❌ حذف کانال جوین اجباری":
            await msg.reply_text("🔗 لطفاً یوزرنیم کانال برای حذف را با @ ارسال کنید.")
            context.user_data["del_ch"] = True

        elif context.user_data.get("del_ch"):
            ch = text.strip()
            cursor.execute("DELETE FROM channels WHERE username=?", (ch,))
            conn.commit()
            await msg.reply_text(f"✅ اگر کانال {ch} وجود داشت، حذف شد.")
            context.user_data["del_ch"] = False

        # ریست قرعه‌کشی
        elif text == "🔄 ریست قرعه‌کشی":
            cursor.execute("DELETE FROM raffle")
            cursor.execute("UPDATE users SET is_registered=0, chances=0")
            conn.commit()
            await msg.reply_text("♻️ قرعه‌کشی ریست شد.")

        # لیدربورد کاربران
        elif text == "🏆 لیدربورد کاربران":
            top = cursor.execute(
                "SELECT username, chances FROM users ORDER BY chances DESC LIMIT 10"
            ).fetchall()
            if top:
                lines = [f"{i+1}. @{u or 'ناشناس'} - {c} شانس" for i, (u, c) in enumerate(top)]
                await msg.reply_text("🏆 لیدربورد بر اساس شانس:\n" + "\n".join(lines))
            else:
                await msg.reply_text("⚠️ هیچ داده‌ای برای نمایش نیست.")

    # === بخش کاربر ===
    else:

        # بررسی عضویت
        if not await is_member(uid, context):
            cursor.execute("SELECT username FROM channels")
            chs = [c[0] for c in cursor.fetchall()]
            btns = [
                [InlineKeyboardButton(f"عضویت در {c}", url=f"https://t.me/{c[1:]}")]
                for c in chs
            ]
            await msg.reply_text("🔒 لطفاً عضو شوید:", reply_markup=InlineKeyboardMarkup(btns))
            return

        # ثبت‌نام در قرعه‌کشی
        if text == "🎰 ثبت نام در قرعه کشی":
            row = cursor.execute("SELECT is_registered FROM users WHERE user_id=?", (uid,)).fetchone()
            reg = row[0] if row else 0
            if reg:
                await msg.reply_text("✅ شما از قبل ثبت‌نام کرده‌اید.")
            else:
                cursor.execute(
                    "UPDATE users SET is_registered=1, chances=chances+1 WHERE user_id=?",
                    (uid,),
                )
                cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (uid,))
                conn.commit()
                await msg.reply_text("🎉 ثبت‌نام شما انجام شد.")

        # افزایش امتیاز (لینک رفرال)
        elif text == "💎 افزایش امتیاز":
            bot_username = getattr(context.bot, "username", None) or ""
            link = f"https://t.me/{bot_username}?start={uid}"
            await msg.reply_text("🔗 لینک دعوت شما:\n" + link)

        # تبدیل امتیاز به شانس
        elif text == "💳 تبدیل امتیاز به شانس":
            row = cursor.execute("SELECT points FROM users WHERE user_id=?", (uid,)).fetchone()
            pts = row[0] if row and row[0] else 0
            if pts > 0:
                cursor.execute(
                    "UPDATE users SET chances=chances+?, points=0 WHERE user_id=?",
                    (pts, uid),
                )
                for _ in range(pts):
                    cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (uid,))
                conn.commit()
                await msg.reply_text(f"✅ {pts} امتیاز تبدیل شد.")
            else:
                await msg.reply_text("⚠️ شما امتیازی ندارید.")

        # اطلاعات حساب
        elif text == "👤 اطلاعات حساب":
            row = cursor.execute(
                "SELECT username, points, chances, is_registered FROM users WHERE user_id=?",
                (uid,),
            ).fetchone()
            if row:
                u, pts, chs, reg = row
                st = "✅ ثبت‌نام شده" if reg else "❌ ثبت‌نام نشده"
                await msg.reply_text(f"👤 @{u}\n💎 امتیاز: {pts}\n🎟 شانس: {chs}\nوضعیت: {st}")
            else:
                await msg.reply_text("⚠️ حساب پیدا نشد. لطفاً /start را بزنید.")


# ————— هندلر ارسال رسانه در حالت همگانی —————
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    uid = msg.from_user.id

    if uid in ADMIN_IDS and context.user_data.get("broadcast"):
        users = cursor.execute("SELECT user_id FROM users").fetchall()
        cnt = 0
        for (u,) in users:
            try:
                if msg.photo:
                    # photo لیست فایل‌آی‌دی‌ها داره؛ آخرین را می‌گیریم
                    await context.bot.send_photo(u, photo=msg.photo[-1].file_id, caption=msg.caption or "")
                elif msg.video:
                    await context.bot.send_video(u, video=msg.video.file_id, caption=msg.caption or "")
                else:
                    # اگر نوع رسانه دیگه‌ای بود، پیام متنی رو بفرست
                    if msg.text:
                        await context.bot.send_message(u, msg.text)
                cnt += 1
            except Exception:
                pass
        await msg.reply_text(f"✅ پیام رسانه‌ای برای {cnt} نفر ارسال شد.")
        context.user_data["broadcast"] = False


# ————— اجرای ربات —————
if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))

    print("🤖 Bot is running...")
    app.run_polling()

