import os
import sqlite3
import random
import threading
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ========================= تنظیمات =========================
BOT_TOKEN = "8227817016:AAHL4vVYIAOBmBHun6iWhezZdyXSwJBjzY8"
CHANNEL_ID = "@fcxter"
ADMIN_IDS = [6181430071, 5944937406]

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
def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💎 افزایش امتیاز"), KeyboardButton("👤 اطلاعات حساب")],
        [KeyboardButton("💳 تبدیل امتیاز به شانس")],
        [KeyboardButton("🎰 ثبت نام در قرعه کشی")]
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, user.username or user.first_name))
    conn.commit()

    await update.message.reply_text("🎉 به ربات قرعه‌کشی خوش آمدید!", reply_markup=main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🎰 ثبت نام در قرعه کشی":
        cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,))
        cursor.execute("INSERT INTO raffle (user_id) VALUES (?)", (user_id,))
        conn.commit()
        await update.message.reply_text("✅ شما در قرعه‌کشی ثبت نام شدید!")

    elif text == "💎 افزایش امتیاز":
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        await update.message.reply_text(f"🔗 لینک اختصاصی شما:\n{link}")

    elif text == "💳 تبدیل امتیاز به شانس":
        cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        points = row[0] if row else 0
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
        row = cursor.fetchone()
        if row:
            points, chances, registered = row
            status = "بله" if registered else "خیر"
            await update.message.reply_text(f"📊 اطلاعات حساب:\n\nثبت‌نام: {status}\nامتیاز: {points}\nشانس: {chances}")

# ========================= اجرای ربات =========================
def run_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())  # ساخت حلقه جدید برای thread
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("[DEBUG] ربات در حال اجرا است...")
    app.run_polling()

if __name__ == "__main__":
    run_bot()
