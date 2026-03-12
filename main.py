import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import threading
import time
from flask import Flask
import os

# --- CONFIGURATION ---
TOKEN = "7610030035:AAEJf2HX7lSg9H9QyS1Y1a8o_586qhvGmkg"
ADMIN_ID = 6357920694
GROUP_ID = "-1003824856633"
API_BASE = "https://weak-deloris-nothing672434-fe85179d.koyeb.app/api"

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# Fetch bot username dynamically for the group buttons
try:
    BOT_USERNAME = bot.get_me().username
except Exception:
    BOT_USERNAME = ""

# --- STATE MANAGEMENT ---
APPROVED_USERS = {ADMIN_ID} 
USER_TRACKED_NUMBERS = {}  # {user_id: [number1, number2, ...]}
SEEN_OTPS = set()          # Stores processed OTP IDs
OTP_GROUP_LINK = ""        # Set via /setotp

# --- FLASK SERVER (For Render Hosting) ---
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
        # Extracts the link after the command
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

# --- USER COMMANDS ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # Check Approval
    if user_id not in APPROVED_USERS:
        bot.send_message(user_id, f"🚫 <b>Access Denied</b>\nYou are not approved to use this bot.\nYour ID: <code>{user_id}</code>")
        # Notify Admin
        admin_msg = f"⚠️ <b>New Access Request</b>\nUser ID: <code>{user_id}</code>\nUsername: @{message.from_user.username}\n\nTo approve, send:\n<code>/approve {user_id}</code>"
        bot.send_message(ADMIN_ID, admin_msg)
        return

    # Fetch Countries
    try:
        res = requests.get(f"{API_BASE}/numbers").json()
        if res.get('success'):
            countries = {}
            for n in res['numbers']:
                if n['country'] not in countries:
                    countries[n['country']] = n['flag']
            
            markup = InlineKeyboardMarkup()
            markup.row_width = 2
            buttons = [
                InlineKeyboardButton(f"{flag} {country}", callback_data=f"ctry_{country}") 
                for country, flag in countries.items()
            ]
            markup.add(*buttons)
            
            bot.send_message(user_id, "🌍 <b>Select a Country to generate 10 numbers:</b>", reply_markup=markup)
        else:
            bot.send_message(user_id, "❌ Failed to fetch countries from API.")
    except Exception as e:
        bot.send_message(user_id, f"❌ Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('ctry_'))
def handle_country_selection(call):
    user_id = call.from_user.id
    country_name = call.data.split('ctry_')[1]
    
    bot.answer_callback_query(call.id, "Fetching numbers...")
    
    try:
        res = requests.get(f"{API_BASE}/numbers").json()
        if res.get('success'):
            # Grab up to 10 numbers for this country
            country_numbers = [n['number'] for n in res['numbers'] if n['country'] == country_name][:10]
            
            if not country_numbers:
                bot.edit_message_text("❌ No numbers available for this country.", chat_id=user_id, message_id=call.message.message_id)
                return
            
            # Save to user's tracked list
            USER_TRACKED_NUMBERS[user_id] = country_numbers
            
            # Formats the list of numbers so the user actually sees them
            num_list_str = "\n".join([f"• <code>{n}</code>" for n in country_numbers])
            
            msg = f"✅ <b>Now listening to {len(country_numbers)} numbers in {country_name}</b>:\n\n{num_list_str}\n\n<i>I will send you a DM instantly when an OTP arrives for any of these numbers.</i>"
            
            bot.edit_message_text(msg, chat_id=user_id, message_id=call.message.message_id)
            
    except Exception as e:
        bot.send_message(user_id, f"❌ Error setting up listener: {str(e)}")


# --- BACKGROUND OTP MONITOR ---

def format_personal_msg(data):
    flag = data.get('flag', '🌍')
    country = data.get('country', 'Unknown')
    masked = data.get('masked_number', '•••')
    sender = data.get('sender', 'Unknown')
    num = data.get('number', '')
    otp = data.get('otp', 'No code')
    msg = data.get('message', '').replace('<', '&lt;').replace('>', '&gt;')
    
    return f"""{flag} {country} | {masked} | {sender}

Full Number: <code>{num}</code>

Service: {sender}

OTP : <code>{otp}</code>

Message:
<code>{msg}</code>"""

def format_group_msg(data):
    flag = data.get('flag', '🌍')
    country = data.get('country', 'Unknown')
    sender = data.get('sender', 'Unknown')
    time_str = data.get('time', 'Just now')
    masked = data.get('masked_number', '•••')
    otp = data.get('otp', 'No code')
    msg = data.get('message', '').replace('<', '&lt;').replace('>', '&gt;')
    
    # Uses Telegram's <blockquote> tags to match your screenshot exactly
    return f"""{flag} <b>New {country} {sender} OTP Received</b>

<blockquote>🕒 Time: {time_str}</blockquote>
<blockquote>🌍 Country: {country} {flag}</blockquote>
<blockquote>📲 Service: {sender}</blockquote>
<blockquote>📞 Number: {masked}</blockquote>
<blockquote>🔑 OTP: <code>{otp}</code></blockquote>
<blockquote>{msg}</blockquote>"""

def monitor_otps():
    while True:
        try:
            res = requests.get(f"{API_BASE}/otps?limit=100", timeout=10).json()
            if res.get('success'):
                # Process oldest to newest
                for data in reversed(res['otps']):
                    otp_id = data.get('id')
                    
                    if otp_id and otp_id not in SEEN_OTPS:
                        SEEN_OTPS.add(otp_id)
                        if len(SEEN_OTPS) > 5000:
                            SEEN_OTPS.clear()
                        
                        # 1. SEND TO GLOBAL GROUP WITH BUTTONS
                        try:
                            group_msg = format_group_msg(data)
                            markup = InlineKeyboardMarkup()
                            
                            # Add the Bot button
                            markup.add(InlineKeyboardButton("📲 Get Numbers From Bot", url=f"https://t.me/{BOT_USERNAME}?start=true"))
                            
                            # Add the Group button ONLY if the admin has set it
                            if OTP_GROUP_LINK:
                                markup.add(InlineKeyboardButton("💬 Join OTP Group", url=OTP_GROUP_LINK))
                                
                            bot.send_message(GROUP_ID, group_msg, reply_markup=markup)
                        except Exception as e:
                            print(f"Group send error: {e}")
                        
                        # 2. SEND TO PERSONAL CHAT IF TRACKING
                        num = data.get('number')
                        for user_id, tracked_nums in USER_TRACKED_NUMBERS.items():
                            if num in tracked_nums:
                                try:
                                    personal_msg = format_personal_msg(data)
                                    bot.send_message(user_id, personal_msg)
                                except Exception as e:
                                    print(f"Personal send error for {user_id}: {e}")
                                    
        except Exception as e:
            print(f"API Monitor Error: {e}")
            
        time.sleep(5) 

# --- STARTUP ---
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    monitor_thread = threading.Thread(target=monitor_otps)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    print("Bot is running...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
