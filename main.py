import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import threading
import time
from flask import Flask

# --- CONFIGURATION ---
TOKEN = "7610030035:AAEJf2HX7lSg9H9QyS1Y1a8o_586qhvGmkg"
ADMIN_ID = 6357920694
GROUP_ID = "-1003824856633"
API_BASE = "https://weak-deloris-nothing672434-fe85179d.koyeb.app/api"

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# --- STATE MANAGEMENT ---
# In a production app, move APPROVED_USERS to a database (like SQLite or MongoDB)
APPROVED_USERS = {ADMIN_ID} 
USER_TRACKED_NUMBERS = {}  # {user_id: [number1, number2, ...]}
SEEN_OTPS = set()          # Stores processed OTP IDs

# --- FLASK SERVER (For Render Hosting) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "OTP Bot is running."

def run_flask():
    # Render assigns a dynamic port via the PORT environment variable
    import os
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- BOT COMMANDS ---

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
            # Extract unique countries
            countries = {}
            for n in res['numbers']:
                if n['country'] not in countries:
                    countries[n['country']] = n['flag']
            
            # Build Keyboard
            markup = InlineKeyboardMarkup()
            markup.row_width = 2
            buttons = [
                InlineKeyboardButton(f"{flag} {country}", callback_data=f"ctry_{country}") 
                for country, flag in countries.items()
            ]
            markup.add(*buttons)
            
            bot.send_message(user_id, "🌍 <b>Select a Country to track 10 numbers:</b>", reply_markup=markup)
        else:
            bot.send_message(user_id, "❌ Failed to fetch countries from API.")
    except Exception as e:
        bot.send_message(user_id, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['approve'])
def approve_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        user_to_approve = int(message.text.split()[1])
        APPROVED_USERS.add(user_to_approve)
        bot.send_message(ADMIN_ID, f"✅ User <code>{user_to_approve}</code> approved.")
        bot.send_message(user_to_approve, "🎉 <b>You have been approved!</b>\nSend /start to begin.")
    except (IndexError, ValueError):
        bot.send_message(ADMIN_ID, "⚠️ Format: <code>/approve USER_ID</code>")

@bot.callback_query_handler(func=lambda call: call.data.startswith('ctry_'))
def handle_country_selection(call):
    user_id = call.from_user.id
    country_name = call.data.split('ctry_')[1]
    
    bot.answer_callback_query(call.id, "Fetching numbers...")
    
    try:
        res = requests.get(f"{API_BASE}/numbers").json()
        if res.get('success'):
            # Filter numbers by selected country and grab up to 10
            country_numbers = [n['number'] for n in res['numbers'] if n['country'] == country_name][:10]
            
            if not country_numbers:
                bot.edit_message_text("❌ No numbers available for this country.", chat_id=user_id, message_id=call.message.message_id)
                return
            
            # Save to user's tracked list
            USER_TRACKED_NUMBERS[user_id] = country_numbers
            
            msg = f"✅ <b>Now listening to {len(country_numbers)} numbers in {country_name}.</b>\n\nI will send you a DM when an OTP arrives for these numbers."
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
    
    return f"""{flag} New {country} {sender} OTP Received

🕒 Time: {time_str}
🌍 Country: {country} {flag}

📲 Service: {sender}

📞 Number: {masked}

🔑 OTP: <code>{otp}</code>

{msg}"""

def monitor_otps():
    while True:
        try:
            res = requests.get(f"{API_BASE}/otps?limit=100", timeout=10).json()
            if res.get('success'):
                # Process from oldest to newest so they appear in correct order
                for data in reversed(res['otps']):
                    otp_id = data.get('id')
                    
                    if otp_id and otp_id not in SEEN_OTPS:
                        SEEN_OTPS.add(otp_id)
                        
                        # Prevent memory leak by keeping SEEN_OTPS manageable
                        if len(SEEN_OTPS) > 5000:
                            SEEN_OTPS.clear()
                        
                        # 1. Send to Global Group
                        try:
                            group_msg = format_group_msg(data)
                            bot.send_message(GROUP_ID, group_msg)
                        except Exception as e:
                            print(f"Group send error: {e}")
                        
                        # 2. Check if any user is tracking this specific number
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
            
        time.sleep(5) # Poll every 5 seconds

# --- STARTUP SCRIPT ---
if __name__ == "__main__":
    # Start Flask Server in background
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start OTP Monitor in background
    monitor_thread = threading.Thread(target=monitor_otps)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    print("Bot is running...")
    # Start Bot polling
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
