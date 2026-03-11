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
    port = int(os.environ.get("PORT", 10000)) # Render uses 10000 by default
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# --- BOT CONFIGURATION ---
API_ID = 25240346
API_HASH = 'b8849fd945ed9225a002fda96591b6ee'
BOT_TOKEN = '7610030035:AAEJf2HX7lSg9H9QyS1Y1a8o_586qhvGmkg'

# ⚠️ ENSURE THIS IS A VALID, NEW STRING SESSION
STRING_SESSION = '1BVtsOLQBu1sWLUjy9O3WhRUoNkCwOcalVvxCOMrjYfFrUezu0qaZrlBK1CUHZE0cm4dnq4V58LhDxyat4qcpkQmCgyD65gCKoxGGc-ZVpMgPLLfg1BD235emPa_y3g3eyoBmCDXd9q01rKcQaacp174qxlomjy_rXM4xBiblwCWNhoztyIGBFERNDnkiKz3EztZAHd64nb4kK4NSN49BDl1hgxMfqaeIs2lIkRCUMHLyrYzrAZ4DY6biOsNakeaoHGrQJEecnn9V4xQEtm9zvfddkuVn6IiLMTDGjA4mBYbdjB6AaU-FubFhKRqjVhwU0mk5Aih2cqPrQ8nUHwMvrYp6HekIo8s='

ADMIN_ID = 6357920694

config = {
    "TARGET_BOT": "UxOtpBOT",  
    "SOURCE_GROUP": None,      
    "DEST_GROUP": None         
}

user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
bot = TelegramClient('bot_session', API_ID, API_HASH)

pending_numbers = {}

# --- ADMIN COMMANDS ---

@bot.on(events.NewMessage(pattern='/adhelp', from_users=ADMIN_ID))
async def admin_help(event):
    help_text = (
        "🛠️ **Admin Control Panel**\n\n"
        f"**Target Bot:** `{config['TARGET_BOT']}`\n"
        f"**Source Group:** `{config['SOURCE_GROUP'] or 'Global'}`\n"
        f"**Dest Group:** `{config['DEST_GROUP'] or 'None'}`\n\n"
        "**Commands:**\n"
        "`/setbot username` | `/setsrc id` | `/setdest id` | `/status`"
    )
    await event.reply(help_text)

@bot.on(events.NewMessage(pattern=r'/setbot (.*)', from_users=ADMIN_ID))
async def set_target_bot(event):
    config["TARGET_BOT"] = event.pattern_match.group(1).strip().replace("@", "")
    await event.reply(f"✅ Target Bot: `{config['TARGET_BOT']}`")

@bot.on(events.NewMessage(pattern=r'/setsrc (.*)', from_users=ADMIN_ID))
async def set_source_group(event):
    config["SOURCE_GROUP"] = event.pattern_match.group(1).strip()
    await event.reply(f"✅ Source ID: `{config['SOURCE_GROUP']}`")

@bot.on(events.NewMessage(pattern=r'/setdest (.*)', from_users=ADMIN_ID))
async def set_dest_group(event):
    config["DEST_GROUP"] = event.pattern_match.group(1).strip()
    await event.reply(f"✅ Dest ID: `{config['DEST_GROUP']}`")

# --- BOT LOGIC ---

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.reply("👋 Click to request service.", buttons=[Button.inline("🚀 Request Service", b"get_ven")])

@bot.on(events.CallbackQuery(data=b"get_ven"))
async def callback_handler(event):
    try: await event.edit("⏳ Connecting...")
    except MessageNotModifiedError: pass
    
    try:
        await user_client.send_message(config['TARGET_BOT'], '/start')
        await asyncio.sleep(3) 
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
                if clicked: break 
            
            if clicked:
                await asyncio.sleep(4)
                reply_msgs = await user_client.get_messages(config['TARGET_BOT'], limit=1)
                if reply_msgs:
                    num_match = re.search(r'(\d{8,15})', reply_msgs[0].text)
                    if num_match:
                        full_num = num_match.group(1)
                        pending_numbers[full_num] = event.chat_id
                        await event.edit(f"📩 **Number:** `{full_num}`", buttons=[Button.inline("🔄 New Number", b"get_ven")])
                    else:
                        await event.edit("❌ Number extraction failed.", buttons=[Button.inline("🔄 Try Again", b"get_ven")])
    except Exception as e:
        print(f"Error: {e}")

# --- LISTENER ---

@user_client.on(events.NewMessage)
async def otp_listener(event):
    text = event.message.text or ""
    if "OTP Received" in text and "Number:" in text:
        if config["DEST_GROUP"]:
            try: await bot.send_message(config["DEST_GROUP"], text)
            except: pass

        masked_match = re.search(r'Number:.*?([\d\*]+)', text)
        if masked_match:
            masked_number = masked_match.group(1)
            parts = re.split(r'\*+', masked_number)
            if len(parts) == 2:
                f4, l4 = parts[0][:4], parts[1][-4:]
                for p_num, c_id in list(pending_numbers.items()):
                    if p_num.startswith(f4) and p_num.endswith(l4):
                        await bot.send_message(c_id, f"🎉 **OTP!**\n\n{text}")
                        del pending_numbers[p_num]
                        break

# --- ASYNC MAIN ---
async def start_clients():
    print("--- Starting Clients ---")
    await user_client.start()
    await bot.start(bot_token=BOT_TOKEN)
    print("✅ All systems online.")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    # Start Web Server
    threading.Thread(target=run_server, daemon=True).start()
    
    # Start Telegram Clients
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_clients())
