import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import threading
import time
import random
from flask import Flask
import os
import json

# --- CONFIGURATION ---
TOKEN = "7610030035:AAEJf2HX7lSg9H9QyS1Y1a8o_586qhvGmkg"
ADMIN_ID = 6357920694
GROUP_ID = "-1003824856633"
API_BASE = "https://weak-deloris-nothing672434-fe85179d.koyeb.app/api"
DB_FILE = "approved_users.json"

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# --- PERSISTENCE HELPERS ---
def load_users():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return {ADMIN_ID}
    return {ADMIN_ID}

def save_users():
    try:
        with open(DB_FILE, "w") as f:
            json.dump(list(APPROVED_USERS), f)
    except Exception as e:
        print(f"Error saving database: {e}")

# --- STATE MANAGEMENT ---
APPROVED_USERS = load_users() 
USER_TRACKED_NUMBERS = {}
USER_SEEN_NUMBERS = {}
SEEN_OTPS = set()          
OTP_GROUP_LINK = ""        

try:
    BOT_USERNAME = bot.get_me().username
except Exception:
    BOT_USERNAME = "OTP_Linker_Bot"

# --- FLASK SERVER (Keep-Alive) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "🟢 OTP Bot is running and healthy."

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- ADMIN COMMANDS ---
@bot.message_handler(commands=['adhelp'])
def admin_help(message):
    if message.from_user.id != ADMIN_ID:
        return
    help_text = """🛠 <b>Admin Commands</b>
/approve [ID] - Grant user access
/deny [ID] - Revoke user access
/list - Show all approved users
/setotp [link] - Set OTP Group link
/adhelp - Show this menu
"""
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['approve'])
def approve_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        uid = int(message.text.split()[1])
        APPROVED_USERS.add(uid)
        save_users()
        bot.send_message(ADMIN_ID, f"✅ User <code>{uid}</code> approved.")
        bot.send_message(uid, "🎉 <b>You have been approved!</b>\nSend /start to begin.")
    except (IndexError, ValueError):
        bot.reply_to(message, "⚠️ <b>Usage:</b> <code>/approve USER_ID</code>")

@bot.message_handler(commands=['deny'])
def deny_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        uid = int(message.text.split()[1])
        if uid == ADMIN_ID:
            return bot.reply_to(message, "❌ You cannot deny yourself!")
        
        if uid in APPROVED_USERS:
            APPROVED_USERS.remove(uid)
            save_users()
            bot.send_message(ADMIN_ID, f"❌ User <code>{uid}</code> access revoked.")
            bot.send_message(uid, "🚫 <b>Your access has been revoked by the admin.</b>")
        else:
            bot.reply_to(message, "❓ User is not in the approved list.")
    except (IndexError, ValueError):
        bot.reply_to(message, "⚠️ <b>Usage:</b> <code>/deny USER_ID</code>")

@bot.message_handler(commands=['list'])
def list_users(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_list = "\n".join([f"• <code>{u}</code>" for u in APPROVED_USERS])
    bot.reply_to(message, f"👥 <b>Approved Users:</b>\n\n{user_list}")

@bot.message_handler(commands=['setotp'])
def set_otp_link(message):
    if message.from_user.id != ADMIN_ID:
        return
    global OTP_GROUP_LINK
    try:
        OTP_GROUP_LINK = message.text.split(" ", 1)[1].strip()
        bot.reply_to(message, f"✅ <b>OTP Group link updated to:</b>\n{OTP_GROUP_LINK}")
    except IndexError:
        bot.reply_to(message, "⚠️ <b>Usage:</b> <code>/setotp https://t.me/link</code>")

# --- UI HELPERS ---
def get_countries_markup():
    try:
        res = requests.get(f"{API_BASE}/numbers").json()
        if not res.get('success'):
            return None
        
        countries = {}
        for n in res['numbers']:
            if n['country'] not in countries:
                countries[n['country']] = n['flag']
        
        markup = InlineKeyboardMarkup(row_width=2)
        buttons = [
            InlineKeyboardButton(f"{flag} {country}", callback_data=f"ctry_{country[:30]}") 
            for country, flag in countries.items()
        ]
        markup.add(*buttons)
        return markup
    except Exception:
        return None

# --- USER COMMANDS ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    if user_id not in APPROVED_USERS:
        bot.send_message(user_id, f"🚫 <b>Access Denied</b>\nYou are not approved.\nYour ID: <code>{user_id}</code>")
        bot.send_message(ADMIN_ID, f"⚠️ <b>Request from:</b> <code>{user_id}</code>\n/approve {user_id}")
        return

    markup = get_countries_markup()
    if markup:
        bot.send_message(user_id, "🌍 <b>Select a Country to get numbers:</b>", reply_markup=markup)
    else:
        bot.send_message(user_id, "❌ Failed to fetch countries.")

@bot.callback_query_handler(func=lambda call: call.data == 'back_countries')
def back_to_countries(call):
    markup = get_countries_markup()
    if markup:
        bot.edit_message_text("🌍 <b>Select a Country:</b>", chat_id=call.from_user.id, message_id=call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ctry_') or call.data.startswith('new_'))
def handle_number_selection(call):
    user_id = call.from_user.id
    if user_id not in APPROVED_USERS:
        return bot.answer_callback_query(call.id, "Access Denied.")

    data_parts = call.data.split('_', 1)
    country_name = data_parts[1]
        
    bot.answer_callback_query(call.id, "Fetching unique numbers...")
    
    try:
        res = requests.get(f"{API_BASE}/numbers").json()
        if res.get('success'):
            if user_id not in USER_SEEN_NUMBERS:
                USER_SEEN_NUMBERS[user_id] = set()
                
            all_matches = [n['number'] for n in res['numbers'] if n['country'].startswith(country_name)]
            flag = next((n['flag'] for n in res['numbers'] if n['country'].startswith(country_name)), "🌍")
            
            available_numbers = [n for n in all_matches if n not in USER_SEEN_NUMBERS[user_id]]
            
            if not available_numbers:
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🔙 Back", callback_data="back_countries"))
                bot.edit_message_text("❌ <b>Out of Numbers!</b>", chat_id=user_id, message_id=call.message.message_id, reply_markup=markup)
                return
            
            picked_numbers = random.sample(available_numbers, min(len(available_numbers), 5))
            USER_SEEN_NUMBERS[user_id].update(picked_numbers)
            USER_TRACKED_NUMBERS[user_id] = picked_numbers 
            
            num_list_str = "\n".join([f"• <code>{n}</code>" for n in picked_numbers])
            msg = f"{flag} <b>Country: {country_name}</b>\n\n✅ <b>Tracking Numbers:</b>\n{num_list_str}"
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔄 Refresh", callback_data=f"new_{country_name}"))
            markup.add(InlineKeyboardButton("🔙 Back", callback_data="back_countries"))
            
            bot.edit_message_text(msg, chat_id=user_id, message_id=call.message.message_id, reply_markup=markup)
            
    except Exception as e:
        bot.send_message(user_id, f"❌ Error: {str(e)}")

# --- BACKGROUND MONITOR ---
def format_personal_msg(data):
    return f"📩 <b>OTP Received!</b>\n\nNumber: <code>{data.get('number')}</code>\nService: {data.get('sender')}\nOTP: <code>{data.get('otp')}</code>"

def format_group_msg(data):
    return f"🔥 <b>OTP Received</b>\n\n📞 {data.get('masked_number')}\n🔑 Code: <code>{data.get('otp')}</code>\n🌍 {data.get('country')}"

def monitor_otps():
    while True:
        try:
            res = requests.get(f"{API_BASE}/otps?limit=50", timeout=10).json()
            if res.get('success'):
                for data in reversed(res['otps']):
                    otp_id = data.get('id')
                    if otp_id and otp_id not in SEEN_OTPS:
                        SEEN_OTPS.add(otp_id)
                        
                        # Post to Group
                        try:
                            markup = InlineKeyboardMarkup()
                            markup.add(InlineKeyboardButton("📲 Start Bot", url=f"https://t.me/{BOT_USERNAME}?start=true"))
                            bot.send_message(GROUP_ID, format_group_msg(data), reply_markup=markup)
                        except: pass
                        
                        # Direct message to user
                        num = data.get('number')
                        for uid, tracked in USER_TRACKED_NUMBERS.items():
                            if num in tracked:
                                try: bot.send_message(uid, format_personal_msg(data))
                                except: pass
        except: pass
        time.sleep(5) 

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=monitor_otps, daemon=True).start()
    print("Bot is starting...")
    bot.infinity_polling()
