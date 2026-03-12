import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import threading
import time
import random
from flask import Flask
import os

# --- CONFIGURATION ---
TOKEN = "7610030035:AAEJf2HX7lSg9H9QyS1Y1a8o_586qhvGmkg"
ADMIN_ID = 6357920694
GROUP_ID = "-1003824856633"
API_BASE = "https://weak-deloris-nothing672434-fe85179d.koyeb.app/api"

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

try:
    BOT_USERNAME = bot.get_me().username
except Exception:
    BOT_USERNAME = ""

# --- STATE MANAGEMENT ---
APPROVED_USERS = {ADMIN_ID} 
USER_TRACKED_NUMBERS = {}  # {user_id: [num1, num2, num3, num4, num5]}
USER_SEEN_NUMBERS = {}     # {user_id: set(seen_numbers)} - Ensures uniqueness
SEEN_OTPS = set()          
OTP_GROUP_LINK = ""        

# --- FLASK SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "OTP Bot is running."

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- ADMIN COMMANDS ---
@bot.message_handler(commands=['adhelp'])
def admin_help(message):
    if message.from_user.id != ADMIN_ID:
        return
    help_text = """🛠 <b>Admin Commands</b>
/approve [user_id] - Approve a user to use the bot
/setotp [link] - Set the official OTP Group link for the buttons
/adhelp - Show this menu
"""
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['setotp'])
def set_otp_link(message):
    if message.from_user.id != ADMIN_ID:
        return
    global OTP_GROUP_LINK
    try:
        OTP_GROUP_LINK = message.text.split(" ", 1)[1].strip()
        bot.reply_to(message, f"✅ <b>OTP Group link updated to:</b>\n{OTP_GROUP_LINK}")
    except IndexError:
        bot.reply_to(message, "⚠️ <b>Usage:</b>\n<code>/setotp https://t.me/yourgroup</code>")

@bot.message_handler(commands=['approve'])
def approve_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        user_to_approve = int(message.text.split()[1])
        APPROVED_USERS.add(user_to_approve)
        bot.send_message(ADMIN_ID, f"✅ User <code>{user_to_approve}</code> approved.")
        bot.send_message(user_to_approve, "🎉 <b>You have been approved!</b>\nSend /start to begin getting numbers.")
    except (IndexError, ValueError):
        bot.send_message(ADMIN_ID, "⚠️ <b>Format:</b> <code>/approve USER_ID</code>")

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
            # Slicing country name to 30 chars to avoid Telegram's 64-byte callback limit
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
        bot.send_message(user_id, f"🚫 <b>Access Denied</b>\nYou are not approved to use this bot.\nYour ID: <code>{user_id}</code>")
        admin_msg = f"⚠️ <b>New Access Request</b>\nUser ID: <code>{user_id}</code>\nUsername: @{message.from_user.username}\n\nTo approve, send:\n<code>/approve {user_id}</code>"
        bot.send_message(ADMIN_ID, admin_msg)
        return

    markup = get_countries_markup()
    if markup:
        bot.send_message(user_id, "🌍 <b>Select a Country to get numbers:</b>", reply_markup=markup)
    else:
        bot.send_message(user_id, "❌ Failed to fetch countries from API.")

@bot.callback_query_handler(func=lambda call: call.data == 'back_countries')
def back_to_countries(call):
    user_id = call.from_user.id
    markup = get_countries_markup()
    if markup:
        bot.edit_message_text("🌍 <b>Select a Country to get numbers:</b>", chat_id=user_id, message_id=call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ctry_') or call.data.startswith('new_'))
def handle_number_selection(call):
    user_id = call.from_user.id
    
    # Safely extract the action and country name
    action, country_name = call.data.split('_', 1)
        
    bot.answer_callback_query(call.id, "Fetching fresh unique numbers...")
    
    try:
        res = requests.get(f"{API_BASE}/numbers").json()
        if res.get('success'):
            if user_id not in USER_SEEN_NUMBERS:
                USER_SEEN_NUMBERS[user_id] = set()
                
            # Find all matching numbers and the correct flag
            all_matches = []
            flag = "🌍"
            full_country_name = country_name
            
            for n in res['numbers']:
                if n['country'].startswith(country_name):
                    all_matches.append(n['number'])
                    flag = n['flag']
                    full_country_name = n['country']
            
            # Filter out numbers the user has already seen
            available_numbers = [n for n in all_matches if n not in USER_SEEN_NUMBERS[user_id]]
            
            if not available_numbers:
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🔙 Back to Countries", callback_data="back_countries"))
                bot.edit_message_text(f"❌ <b>Out of Numbers!</b>\nYou have used all available unique numbers for {full_country_name}.", chat_id=user_id, message_id=call.message.message_id, reply_markup=markup)
                return
            
            # Pick up to 5 Random Unique Numbers
            amount_to_pick = min(len(available_numbers), 5)
            picked_numbers = random.sample(available_numbers, amount_to_pick)
            
            # Update memory
            USER_SEEN_NUMBERS[user_id].update(picked_numbers)
            USER_TRACKED_NUMBERS[user_id] = picked_numbers # Track all 5
            
            # Build the list string
            num_list_str = "\n".join([f"• <code>{n}</code>" for n in picked_numbers])
            
            msg = f"{flag} <b>Country: {full_country_name}</b>\n\n✅ <b>Listening to {len(picked_numbers)} Virtual Numbers:</b>\n\n{num_list_str}\n\n<i>⏳ Waiting for SMS... I will DM you instantly when an OTP arrives.</i>"
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔄 Get New Numbers", callback_data=f"new_{country_name}"))
            markup.add(InlineKeyboardButton("🔙 Change Country", callback_data="back_countries"))
            
            bot.edit_message_text(msg, chat_id=user_id, message_id=call.message.message_id, reply_markup=markup)
            
    except Exception as e:
        bot.send_message(user_id, f"❌ Error: {str(e)}")

# --- BACKGROUND OTP MONITOR ---
def format_personal_msg(data):
    flag, country, masked, sender, num, otp, msg = data.get('flag','🌍'), data.get('country','Unknown'), data.get('masked_number','•••'), data.get('sender','Unknown'), data.get('number',''), data.get('otp','No code'), data.get('message','').replace('<','&lt;').replace('>','&gt;')
    return f"""{flag} {country} | {masked} | {sender}\n\nFull Number: <code>{num}</code>\n\nService: {sender}\n\nOTP : <code>{otp}</code>\n\nMessage:\n<code>{msg}</code>"""

def format_group_msg(data):
    flag, country, sender, time_str, masked, otp, msg = data.get('flag','🌍'), data.get('country','Unknown'), data.get('sender','Unknown'), data.get('time','Just now'), data.get('masked_number','•••'), data.get('otp','No code'), data.get('message','').replace('<','&lt;').replace('>','&gt;')
    return f"""{flag} <b>New {country} {sender} OTP Received</b>\n\n<blockquote>🕒 Time: {time_str}</blockquote>\n<blockquote>🌍 Country: {country} {flag}</blockquote>\n<blockquote>📲 Service: {sender}</blockquote>\n<blockquote>📞 Number: {masked}</blockquote>\n<blockquote>🔑 OTP: <code>{otp}</code></blockquote>\n<blockquote>{msg}</blockquote>"""

def monitor_otps():
    while True:
        try:
            res = requests.get(f"{API_BASE}/otps?limit=100", timeout=10).json()
            if res.get('success'):
                for data in reversed(res['otps']):
                    otp_id = data.get('id')
                    
                    if otp_id and otp_id not in SEEN_OTPS:
                        SEEN_OTPS.add(otp_id)
                        if len(SEEN_OTPS) > 5000:
                            SEEN_OTPS.clear()
                        
                        # GLOBAL GROUP
                        try:
                            group_msg = format_group_msg(data)
                            markup = InlineKeyboardMarkup()
                            markup.add(InlineKeyboardButton("📲 Get Numbers From Bot", url=f"https://t.me/{BOT_USERNAME}?start=true"))
                            if OTP_GROUP_LINK:
                                markup.add(InlineKeyboardButton("💬 Join OTP Group", url=OTP_GROUP_LINK))
                            bot.send_message(GROUP_ID, group_msg, reply_markup=markup)
                        except Exception:
                            pass
                        
                        # PERSONAL CHAT
                        num = data.get('number')
                        for user_id, tracked_nums in USER_TRACKED_NUMBERS.items():
                            if num in tracked_nums:
                                try:
                                    bot.send_message(user_id, format_personal_msg(data))
                                except Exception:
                                    pass
        except Exception:
            pass
        time.sleep(5) 

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=monitor_otps, daemon=True).start()
    print("Bot is running...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
