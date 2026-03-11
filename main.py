from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import MessageNotModifiedError
from flask import Flask
import threading
import asyncio
import os
import re

# --- FLASK WEB SERVER (For Render Keep-Alive) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "🟢 OTP Linker Bot is Running!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    # Disable debug and use threaded=True to prevent loop conflicts
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

# --- BOT CONFIGURATION ---
API_ID = 25240346
API_HASH = 'b8849fd945ed9225a002fda96591b6ee'
BOT_TOKEN = '7610030035:AAEJf2HX7lSg9H9QyS1Y1a8o_586qhvGmkg'

# ⚠️ PASTE YOUR ACTIVE STRING SESSION HERE
STRING_SESSION = '1BVtsOLQBu1sWLUjy9O3WhRUoNkCwOcalVvxCOMrjYfFrUezu0qaZrlBK1CUHZE0cm4dnq4V58LhDxyat4qcpkQmCgyD65gCKoxGGc-ZVpMgPLLfg1BD235emPa_y3g3eyoBmCDXd9q01rKcQaacp174qxlomjy_rXM4xBiblwCWNhoztyIGBFERNDnkiKz3EztZAHd64nb4kK4NSN49BDl1hgxMfqaeIs2lIkRCUMHLyrYzrAZ4DY6biOsNakeaoHGrQJEecnn9V4xQEtm9zvfddkuVn6IiLMTDGjA4mBYbdjB6AaU-FubFhKRqjVhwU0mk5Aih2cqPrQ8nUHwMvrYp6HekIo8s='

ADMIN_ID = 6357920694

# Dynamic Settings
config = {
    "TARGET_BOT": "UxOtpBOT",  
    "SOURCE_GROUP": None,      
    "DEST_GROUP": None         
}

user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
bot = TelegramClient('bot_session', API_ID, API_HASH)

pending_numbers = {}

print("--- Starting OTP Linker with Admin Controls ---")

# --- ADMIN COMMANDS ---

@bot.on(events.NewMessage(pattern='/adhelp', from_users=ADMIN_ID))
async def admin_help(event):
    help_text = (
        "🛠️ **Admin Control Panel**\n\n"
        f"**Current Target Bot:** `{config['TARGET_BOT']}`\n"
        f"**Current Source Group:** `{config['SOURCE_GROUP'] or 'Any (Global Listener)'}`\n"
        f"**Current Dest Group:** `{config['DEST_GROUP'] or 'Not Set'}`\n\n"
        "**Commands:**\n"
        "`/setbot username` - Change the bot we request numbers from (e.g., /setbot @UxOtpBOT)\n"
        "`/setsrc chat_id` - Set the specific group to listen for OTPs\n"
        "`/setdest chat_id` - Set the group where ALL OTPs will be forwarded\n"
        "`/status` - View active pending numbers"
    )
    await event.reply(help_text)

@bot.on(events.NewMessage(pattern=r'/setbot (.*)', from_users=ADMIN_ID))
async def set_target_bot(event):
    new_bot = event.pattern_match.group(1).strip()
    config["TARGET_BOT"] = new_bot.replace("@", "")
    await event.reply(f"✅ Target Provider Bot updated to: `{config['TARGET_BOT']}`")

@bot.on(events.NewMessage(pattern=r'/setsrc (.*)', from_users=ADMIN_ID))
async def set_source_group(event):
    new_src = event.pattern_match.group(1).strip()
    config["SOURCE_GROUP"] = new_src
    await event.reply(f"✅ Source OTP Group updated to: `{config['SOURCE_GROUP']}`")

@bot.on(events.NewMessage(pattern=r'/setdest (.*)', from_users=ADMIN_ID))
async def set_dest_group(event):
    new_dest = event.pattern_match.group(1).strip()
    config["DEST_GROUP"] = new_dest
    await event.reply(f"✅ Destination Group updated to: `{config['DEST_GROUP']}`")

@bot.on(events.NewMessage(pattern='/status', from_users=ADMIN_ID))
async def show_status(event):
    if not pending_numbers:
        await event.reply("📊 Currently waiting on: **0 numbers**")
    else:
        text = "📊 **Pending OTP Requests:**\n"
        for num, chat_id in pending_numbers.items():
            text += f"- `{num}` (Requested by ID: {chat_id})\n"
        await event.reply(text)

# --- BOT LOGIC (USER FACING) ---

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if event.sender_id == ADMIN_ID:
        await event.reply("👋 Welcome Admin! Use /adhelp to configure the bot.", buttons=[Button.inline("🚀 Request Service", b"get_ven")])
    else:
        await event.reply("👋 Welcome to the OTP Linker!\n\nClick below to fetch the service.", buttons=[Button.inline("🚀 Request Service", b"get_ven")])

@bot.on(events.CallbackQuery(data=b"get_ven"))
async def callback_handler(event):
    try:
        await event.edit(f"⏳ Connecting to `{config['TARGET_BOT']}`... Please wait.")
    except MessageNotModifiedError:
        pass
    
    try:
        await user_client.send_message(config['TARGET_BOT'], '/start')
        await asyncio.sleep(2.5) 
        
        messages = await user_client.get_messages(config['TARGET_BOT'], limit=1)
        
        if messages and messages[0].reply_markup:
            msg = messages[0]
            clicked = False
            
            for r_idx, row in enumerate(msg.reply_markup.rows):
                for c_idx, button in enumerate(row.buttons):
                    if hasattr(button, 'text') and "Venezuela" in button.text:
                        await msg.click(r_idx, c_idx)
                        clicked = True
                        break
                if clicked: 
                    break 
            
            if clicked:
                try:
                    await event.edit("✅ **Service Selected!**\nWaiting for OTP generation...")
                except MessageNotModifiedError:
                    pass
                
                await asyncio.sleep(3.5)
                reply_msgs = await user_client.get_messages(config['TARGET_BOT'], limit=1)
                
                if reply_msgs:
                    provider_text = reply_msgs[0].text
                    
                    number_match = re.search(r'(\d{8,15})', provider_text)
                    
                    if number_match:
                        full_number = number_match.group(1)
                        pending_numbers[full_number] = event.chat_id
                        
                        try:
                            await event.edit(
                                f"📩 **Response:**\n\n{provider_text}",
                                buttons=[Button.inline("🔄 Get New Number", b"get_ven")]
                            )
                        except MessageNotModifiedError:
                            pass
                    else:
                        try:
                            await event.edit(
                                f"📩 **Response:**\n\n{provider_text}\n\n❌ Could not extract number.",
                                buttons=[Button.inline("🔄 Try Again", b"get_ven")]
                            )
                        except MessageNotModifiedError:
                            pass
            else:
                try:
                    await event.edit("❌ Could not find the option in the menu.", buttons=[Button.inline("🔄 Try Again", b"get_ven")])
                except MessageNotModifiedError:
                    pass
    except Exception as e:
        print(f"Callback Error: {e}")

# --- GROUP LISTENER & FORWARDER ---

@user_client.on(events.NewMessage)
async def otp_group_listener(event):
    text = event.message.text or ""
    
    if config["SOURCE_GROUP"]:
        chat = await event.get_chat()
        if str(chat.id) != config["SOURCE_GROUP"] and getattr(chat, 'username', '') != config["SOURCE_GROUP"].replace("@", ""):
            return

    if "OTP Received" in text and "Number:" in text:
        if config["DEST_GROUP"]:
            try:
                await bot.send_message(config["DEST_GROUP"], f"📢 **New OTP Broadcast:**\n\n{text}")
            except Exception as e:
                print(f"Failed to forward to Dest Group: {e}")

        masked_match = re.search(r'Number:\s*([\d\*]+)', text)
        if masked_match:
            masked_number = masked_match.group(1)
            parts = re.split(r'\*+', masked_number)
            
            if len(parts) == 2:
                first_4 = parts[0][:4]
                last_4 = parts[1][-4:]
                
                for pending_num, chat_id in list(pending_numbers.items()):
                    if pending_num.startswith(first_4) and pending_num.endswith(last_4):
                        await bot.send_message(chat_id, f"🎉 **YOUR OTP ARRIVED!**\n\n{text}")
                        del pending_numbers[pending_num]
                        break

# --- ASYNC EXECUTION BLOCK ---
async def main():
    print("Initializing Telegram Clients...")
    # Explicitly await the start of both clients
    await user_client.start()
    await bot.start(bot_token=BOT_TOKEN)
    print("✅ Web Server and Telegram Clients are Online!")
    # Keep the bot running
    await bot.run_until_disconnected()

if __name__ == '__main__':
    # Start Flask in a background thread
    threading.Thread(target=run_server, daemon=True).start()
    
    # Safely run the asyncio event loop
    bot.loop.run_until_complete(main())
