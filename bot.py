import os
import sqlite3
import random
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ChatMemberStatus

# ========================= تنظیمات =========================
BOT_TOKEN = "8227817016:AAHL4vVYIAOBmBHun6iWhezZdyXSwJBjzY8"
CHANNEL_ID = "@fcxter"
ADMIN_IDS = [6181430071, 5944937406]  # آیدی عددی ادمین‌ها

# ========================= دیتابیس =========================
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

# ========================= توابع =========================
def user_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💎 افزایش امتیاز"), KeyboardButton("👤 اطلاعات حساب")],
        [KeyboardButton("💳 تبدیل امتیاز به شانس")],
        [KeyboardButton("🎰 ثبت نام در قرعه کشی")]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎯 انتخاب برنده"), KeyboardButton("📊 آمار کاربران")],
        [KeyboardButton("💎 افزایش امتیاز"), KeyboardButton("👤 اطلاعات حساب")],
        [KeyboardButton("💳 تبدیل امتیاز به شانس"), KeyboardButton("🎰 ثبت نام در قرعه کشی")]
    ], resize_keyboard=True)

async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE):
    """ بررسی عضویت در کانال """
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        print(f"[DEBUG] وضعیت کاربر {user_id}: {member.status}")  # دیباگ
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception as e:
        print(f"[ERROR] بررسی عضویت کاربر {user_id} با خطا مواجه شد: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, user.username or user.first_name))
    conn.commit()

    # Referral
    if context.args:
        try:
            ref_id = int(context.args[0])
            if ref_id != user_id:
                cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (ref_id,))
                if cursor.fetchone():
                    cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (ref_id,))
                    conn.commit()
                    try:
                        await context.bot.send_message(ref_id, "🎉 یک کاربر جدید با لینک شما وارد شد! 1 امتیاز به شما اضافه شد.")
                    except:
                        pass
        except:
            pass

    # منوی ادمین یا کاربر عادی
    if user_id in ADMIN_IDS:
        await update.message.reply_text("👑 به پنل مدیریت خوش آمدید", reply_markup=admin_menu())
    else:
        await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید!", reply_markup=user_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # بررسی عضویت
    if not await is_member(user_id, context):
        keyboard = [[InlineKeyboardButton("🔗 عضویت در کانال", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
        await update.message.reply_text("🔒 ابتدا در کانال عضو شوید!", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # کاربر عادی یا ادمین
    if text == "🎰 ثبت نام در قرعه کشی":
        cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,))
        cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
        conn.commit()
        await update.message.reply_text("✅ شما در قرعه‌کشی ثبت‌نام شدید!")

    elif text == "💎 افزایش امتیاز":
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        await update.message.reply_text(f"🔗 لینک اختصاصی شما:\n{link}")

    elif text == "💳 تبدیل امتیاز به شانس":
        cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
        points = cursor.fetchone()[0]
        if points > 0:
            cursor.execute("UPDATE users SET points = 0, chances = chances + ? WHERE user_id = ?", (points, user_id))
            for _ in range(points):
                cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
            conn.commit()
            await update.message.reply_text("✅ امتیازها به شانس تبدیل شد!")
        else:
            await update.message.reply_text("⚠️ شما امتیازی ندارید.")

    elif text == "👤 اطلاعات حساب":
        cursor.execute("SELECT points, chances, is_registered FROM users WHERE user_id = ?", (user_id,))
        points, chances, registered = cursor.fetchone()
        status = "بله" if registered else "خیر"
        await update.message.reply_text(f"📊 اطلاعات حساب:\n\nثبت‌نام: {status}\nامتیاز: {points}\nشانس: {chances}")

    if user_id in ADMIN_IDS:
        if text == "🎯 انتخاب برنده":
            cursor.execute("SELECT user_id FROM raffle")
            participants = [row[0] for row in cursor.fetchall()]
            if participants:
                winner = random.choice(participants)
                cursor.execute("SELECT username FROM users WHERE user_id = ?", (winner,))
                username = cursor.fetchone()[0]
                await update.message.reply_text(f"🎉 برنده: @{username} (ID: {winner})")
            else:
                await update.message.reply_text("⚠️ هنوز کسی ثبت‌نام نکرده است.")

        elif text == "📊 آمار کاربران":
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM raffle")
            total_raffle = cursor.fetchone()[0]
            await update.message.reply_text(f"📊 آمار:\nکاربران: {total_users}\nشرکت‌کنندگان قرعه‌کشی: {total_raffle}")

def run_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("[DEBUG] ربات در حال اجرا است...")
    app.run_polling()

if __name__ == "__main__":
    run_bot()
