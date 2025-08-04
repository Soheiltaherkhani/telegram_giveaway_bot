import os
import sqlite3
import random
import threading
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ChatMemberStatus

BOT_TOKEN = "توکن_ربات"
CHANNEL_ID = "@fcxter"

conn = sqlite3.connect("raffle.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    chances INTEGER DEFAULT 0
)""")
conn.commit()

flask_app = Flask(__name__)

def main_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("💎 افزایش امتیاز"), KeyboardButton("👤 اطلاعات حساب")],
            [KeyboardButton("💳 تبدیل امتیاز به شانس")],
            [KeyboardButton("🎰 ثبت نام در قرعه کشی")]
        ],
        resize_keyboard=True
    )

async def is_member(user_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username or user.first_name))
    conn.commit()

    await update.message.reply_text("🎉 به ربات خوش آمدید!", reply_markup=main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_member(user_id, context):
        await update.message.reply_text(f"🔒 لطفاً ابتدا در {CHANNEL_ID} عضو شوید و سپس دوباره تلاش کنید.")
        return

    text = update.message.text
    if text == "🎰 ثبت نام در قرعه کشی":
        cursor.execute("UPDATE users SET chances = chances + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        await update.message.reply_text("✅ شما ثبت‌نام شدید!")

telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

def run_bot():
    telegram_app.run_polling()  # بدون استفاده از asyncio.run()

if __name__ == "__main__":
    print("[DEBUG] ربات در حال راه‌اندازی است...")
    threading.Thread(target=run_bot).start()
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
