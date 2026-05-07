import logging
import os
import json
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ================= CONFIG =================
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
SHEET_NAME = "FundedBeast_Campaign"

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key("YOUR_SHEET_ID").sheet1

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# ================= HELPERS =================

def get_all_users():
    return sheet.get_all_records()

def find_user(user_id):
    users = get_all_users()
    for i, u in enumerate(users):
        if str(u["user_id"]) == str(user_id):
            return i + 2, u   # +2 because header row
    return None, None

def create_user(user_id, username):
    sheet.append_row([
        user_id, username, "", "", "", "", 0, False,
        str(datetime.now()), "name", "new"
    ])

def update_user(row, col, value):
    sheet.update_cell(row, col, value)

# Column mapping
COL = {
    "user_id": 1,
    "username": 2,
    "name": 3,
    "email": 4,
    "phone": 5,
    "uid": 6,
    "referrals": 7,
    "proof": 8,
    "last_active": 9,
    "step": 10,
    "status": 11
}

# ================= KEYBOARD =================
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add("🔥 Start Mission", "📊 Beast Status")
main_menu.add("👥 Invite Pack", "🏆 Leaderboard")
main_menu.add("📤 Submit Proof")

# ================= START =================
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    user_id = msg.from_user.id
    username = msg.from_user.username or f"user{user_id}"

    row, user = find_user(user_id)

    if not user:
        create_user(user_id, username)

    await msg.answer(f"""
🐉 Welcome to FundedBeast

💰 Up to $100K funded accounts
🔥 Leaderboard battles live

🎯 Your Code:
@{username}
""", reply_markup=main_menu)

# ================= START FLOW =================
@dp.message_handler(lambda m: m.text == "🔥 Start Mission")
async def start_flow(msg: types.Message):
    row, user = find_user(msg.from_user.id)
    update_user(row, COL["step"], "name")
    await msg.answer("👤 Enter your Full Name:")

# ================= INPUT FLOW =================
@dp.message_handler()
async def input_handler(msg: types.Message):
    row, user = find_user(msg.from_user.id)
    if not user:
        return

    step = user["step"]

    update_user(row, COL["last_active"], str(datetime.now()))

    if step == "name":
        update_user(row, COL["name"], msg.text)
        update_user(row, COL["step"], "email")
        await msg.answer("📧 Enter your Email:")

    elif step == "email":
        update_user(row, COL["email"], msg.text)
        update_user(row, COL["step"], "phone")
        await msg.answer("📱 Enter your Phone:")

    elif step == "phone":
        update_user(row, COL["phone"], msg.text)
        update_user(row, COL["step"], "uid")
        await msg.answer("🆔 Enter Bitunix UID:")

    elif step == "uid":
        update_user(row, COL["uid"], msg.text)
        update_user(row, COL["step"], "done")
        update_user(row, COL["status"], "registered")

        await msg.answer("""
🐉 Mission Started

Complete tasks:
1. Register
2. KYC
3. Deposit
4. Follow socials

👉 Submit proof
""", reply_markup=main_menu)

# ================= PROOF =================
@dp.message_handler(lambda m: m.text == "📤 Submit Proof")
async def ask_proof(msg: types.Message):
    await msg.answer("📸 Upload screenshots")

@dp.message_handler(content_types=['photo'])
async def proof(msg: types.Message):
    row, user = find_user(msg.from_user.id)
    update_user(row, COL["proof"], True)

    await msg.answer("✅ Proof submitted")

# ================= STATUS =================
@dp.message_handler(lambda m: m.text == "📊 Beast Status")
async def status(msg: types.Message):
    row, user = find_user(msg.from_user.id)

    await msg.answer(f"""
📊 Status

👤 {user['name']}
🆔 {user['uid']}
👥 Referrals: {user['referrals']}
📸 Proof: {"✅" if user['proof'] else "❌"}
""")

# ================= LEADERBOARD =================
@dp.message_handler(lambda m: m.text == "🏆 Leaderboard")
async def leaderboard(msg: types.Message):
    users = get_all_users()
    users = sorted(users, key=lambda x: int(x["referrals"]), reverse=True)[:5]

    text = "🏆 Top Beasts:\n"
    for i, u in enumerate(users):
        text += f"{i+1}. @{u['username']} — {u['referrals']}\n"

    await msg.answer(text)

# ================= FOMO =================
async def fomo_check():
    users = get_all_users()
    for u in users:
        try:
            last = datetime.fromisoformat(u["last_active"])
            if datetime.now() - last > timedelta(hours=12):
                await bot.send_message(u["user_id"], """
🐉 FundedBeast Alert

Someone just won 💰

You're still in…
Act now.
""")
        except:
            pass

scheduler = AsyncIOScheduler()

async def on_startup(dp):
    scheduler.add_job(fomo_check, "interval", hours=6)
    scheduler.start()

# ================= RUN =================
if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)
