from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import MessageNotModifiedError
from flask import Flask
import threading, asyncio, os, re

# --- FLASK KEEP-ALIVE ---
app = Flask(__name__)
@app.route('/')
def home(): return "🟢 OTP RELAY PRO IS ONLINE"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# --- CONFIGURATION ---
API_ID = 25240346
API_HASH = 'b8849fd945ed9225a002fda96591b6ee'
BOT_TOKEN = '7610030035:AAEJf2HX7lSg9H9QyS1Y1a8o_586qhvGmkg'
STRING_SESSION = '1BVtsOLQBu1sWLUjy9O3WhRUoNkCwOcalVvxCOMrjYfFrUezu0qaZrlBK1CUHZE0cm4dnq4V58LhDxyat4qcpkQmCgyD65gCKoxGGc-ZVpMgPLLfg1BD235emPa_y3g3eyoBmCDXd9q01rKcQaacp174qxlomjy_rXM4xBiblwCWNhoztyIGBFERNDnkiKz3EztZAHd64nb4kK4NSN49BDl1hgxMfqaeIs2lIkRCUMHLyrYzrAZ4DY6biOsNakeaoHGrQJEecnn9V4xQEtm9zvfddkuVn6IiLMTDGjA4mBYbdjB6AaU-FubFhKRqjVhwU0mk5Aih2cqPrQ8nUHwMvrYp6HekIo8s='
ADMIN_ID = 6357920694

# Admin Settings
config = {
    "TARGET_BOT": "UxOtpBOT",
    "SOURCE_ID": None,       # ID of the OTP group
    "DEST_ID": None,         # ID of your forward group
    "SOURCE_LINK": None,     # Invite link for Source
    "DEST_LINK": None,       # Invite link for Dest
    "CHANNEL_LINK": "https://t.me/YourChannel" # Admin setup
}

user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
bot = TelegramClient('bot_session', API_ID, API_HASH)

# Tracks all active numbers for all users
# Format: {"58416...": chat_id}
pending_numbers = {}

# --- HELPER: JOIN CHECK ---
async def check_joins():
    try:
        if config["SOURCE_ID"]: await user_client.get_entity(config["SOURCE_ID"])
        if config["DEST_ID"]: await user_client.get_entity(config["DEST_ID"])
        return True
    except Exception:
        return False

# --- ADMIN COMMANDS ---

@bot.on(events.NewMessage(pattern='/adhelp', from_users=ADMIN_ID))
async def admin_help(event):
    await event.reply(
        "🛠️ **Admin Pro Panel**\n\n"
        f"**Source:** `{config['SOURCE_ID']}` | **Dest:** `{config['DEST_ID']}`\n"
        "**Commands:**\n"
        "`/setsrc ID LINK` - Set Source ID and Invite Link\n"
        "`/setdest ID LINK` - Set Dest ID and Invite Link\n"
        "`/setchan LINK` - Set Channel button link\n"
        "`/status` - View all active numbers"
    )

@bot.on(events.NewMessage(pattern=r'/setsrc (.*) (.*)', from_users=ADMIN_ID))
async def set_src(event):
    config["SOURCE_ID"], config["SOURCE_LINK"] = event.pattern_match.group(1), event.pattern_match.group(2)
    await event.reply("✅ Source Group Configured.")

@bot.on(events.NewMessage(pattern=r'/setdest (.*) (.*)', from_users=ADMIN_ID))
async def set_dest(event):
    config["DEST_ID"], config["DEST_LINK"] = event.pattern_match.group(1), event.pattern_match.group(2)
    await event.reply("✅ Destination Group Configured.")

# --- BOT LOGIC (NUMBER REQUEST) ---

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    # Check if user account is joined
    if not await check_joins() and event.sender_id == ADMIN_ID:
        return await event.reply(f"⚠️ **Account not in groups!**\nJoin here:\nSource: {config['SOURCE_LINK']}\nDest: {config['DEST_LINK']}")
    
    await event.reply("🇻🇪 **Venezuela Service Selection**", buttons=[Button.inline("🚀 Request Numbers", b"get_ven")])

@bot.on(events.CallbackQuery(data=b"get_ven"))
async def callback_handler(event):
    await event.edit("⏳ Fetching list from provider...")
    await user_client.send_message(config['TARGET_BOT'], '/start')
    await asyncio.sleep(3)
    
    msgs = await user_client.get_messages(config['TARGET_BOT'], limit=1)
    if msgs and msgs[0].reply_markup:
        # 1. Click Venezuela
        for r_idx, row in enumerate(msgs[0].reply_markup.rows):
            for c_idx, btn in enumerate(row.buttons):
                if "Venezuela" in btn.text:
                    await msgs[0].click(r_idx, c_idx)
                    await asyncio.sleep(4)
                    
                    # 2. Get the Number List
                    list_msgs = await user_client.get_messages(config['TARGET_BOT'], limit=1)
                    raw_text = list_msgs[0].text
                    
                    # Extract ALL numbers (looking for 58xxxxxxxxxx)
                    found_nums = re.findall(r'(58\d{10})', raw_text)
                    
                    if found_nums:
                        for n in found_nums: pending_numbers[n] = event.chat_id
                        num_list_str = "\n".join([f"• `{n}`" for n in found_nums])
                        await event.edit(f"✅ **Numbers Received:**\n{num_list_str}\n\n⏳ Waiting for OTPs...", 
                                       buttons=[Button.inline("🔄 Refresh List", b"get_ven")])
                    else:
                        await event.edit("❌ No numbers available currently.")
                    return

# --- OTP LISTENER (The Forwarder) ---

@user_client.on(events.NewMessage)
async def otp_forwarder(event):
    text = event.message.text or ""
    # Only listen to configured source
    if config["SOURCE_ID"] and str(event.chat_id) != str(config["SOURCE_ID"]): return

    if "New" in text and "OTP" in text:
        # Extract OTP (usually 6 digits) and the masked number
        otp_match = re.search(r'(\d{6})', text)
        masked_match = re.search(r'Number:.*?([\d\*]+)', text)
        
        if otp_match and masked_match:
            otp_code = otp_match.group(1)
            m_num = masked_match.group(1)
            f4, l4 = m_num.split('*')[0][:4], m_num.split('*')[-1][-4:]
            
            # Find the user
            for p_num, c_id in list(pending_numbers.items()):
                if p_num.startswith(f4) and p_num.endswith(l4):
                    # Format as per screenshot
                    bot_user = (await bot.get_me()).username
                    buttons = [
                        [Button.inline(f"{otp_code}", b"none")],
                        [Button.url("🚀 Panel", f"https://t.me/{bot_user}")],
                        [Button.url("📱 Channel", config["CHANNEL_LINK"])]
                    ]
                    
                    # Send to User
                    await bot.send_message(c_id, f"🇻🇪 VE | {f4}••{l4} | FB", buttons=buttons)
                    
                    # Forward to Dest Group
                    if config["DEST_ID"]:
                        await bot.send_message(config["DEST_ID"], f"🇻🇪 VE | {f4}••{l4} | FB", buttons=buttons)
                    
                    del pending_numbers[p_num]
                    break

# --- STARTUP ---
async def start_main():
    await user_client.start()
    await bot.start(bot_token=BOT_TOKEN)
    print("✅ All systems go.")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    threading.Thread(target=run_server, daemon=True).start()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_main())
