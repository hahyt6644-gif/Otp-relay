from telethon import TelegramClient, events, Button, functions
from telethon.sessions import StringSession
from telethon.errors import MessageNotModifiedError, InviteHashExpiredError, UserAlreadyParticipantError
from flask import Flask
import threading, asyncio, os, re, requests

# --- FLASK KEEP-ALIVE ---
app = Flask(__name__)
@app.route('/')
def home(): return "🟢 OTP RELAY AI-PRO IS ONLINE"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# --- CONFIGURATION ---
API_ID = 25240346
API_HASH = 'b8849fd945ed9225a002fda96591b6ee'
BOT_TOKEN = '7610030035:AAEJf2HX7lSg9H9QyS1Y1a8o_586qhvGmkg'
STRING_SESSION = '1BVtsOLQBu1sWLUjy9O3WhRUoNkCwOcalVvxCOMrjYfFrUezu0qaZrlBK1CUHZE0cm4dnq4V58LhDxyat4qcpkQmCgyD65gCKoxGGc-ZVpMgPLLfg1BD235emPa_y3g3eyoBmCDXd9q01rKcQaacp174qxlomjy_rXM4xBiblwCWNhoztyIGBFERNDnkiKz3EztZAHd64nb4kK4NSN49BDl1hgxMfqaeIs2lIkRCUMHLyrYzrAZ4DY6biOsNakeaoHGrQJEecnn9V4xQEtm9zvfddkuVn6IiLMTDGjA4mBYbdjB6AaU-FubFhKRqjVhwU0mk5Aih2cqPrQ8nUHwMvrYp6HekIo8s='
ADMIN_ID = 6357920694

config = {
    "TARGET_BOT": "UxOtpBOT",
    "SOURCE_ID": None,       
    "DEST_ID": None,         
    "SOURCE_LINK": None,     
    "DEST_LINK": None,       
    "CHANNEL_LINK": "https://t.me/YourChannel"
}

user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
bot = TelegramClient('bot_session', API_ID, API_HASH)

pending_numbers = {}

# --- AI API INTEGRATION ---
def get_ai_response(prompt):
    try:
        url = f"https://apis.prexzyvilla.site/ai/ai4chat?prompt={prompt}"
        res = requests.get(url).json()
        if res.get("status"):
            return res["data"]["response"]
    except Exception as e:
        return f"AI Error: {e}"
    return "Sorry, I couldn't process that request."

# --- HELPER: AUTO-JOIN LOGIC ---
async def ensure_joined(invite_link):
    if not invite_link or "t.me/+" not in invite_link:
        return False
    try:
        hash_part = invite_link.split('+')[-1]
        await user_client(functions.messages.ImportChatInviteRequest(hash=hash_part))
        return True
    except UserAlreadyParticipantError:
        return True
    except Exception as e:
        print(f"Join Error: {e}")
        return False

# --- ADMIN COMMANDS ---

@bot.on(events.NewMessage(pattern='/adhelp', from_users=ADMIN_ID))
async def admin_help(event):
    await event.reply(
        "🛠️ **Admin AI-Pro Panel**\n\n"
        "**Commands:**\n"
        "`/setsrc ID LINK` - Set Source Group\n"
        "`/setdest ID LINK` - Set Dest Group\n"
        "`/setchan LINK` - Set Channel link\n"
        "`/ask prompt` - Get a response from the integrated AI"
    )

@bot.on(events.NewMessage(pattern=r'/setsrc (.*) (.*)', from_users=ADMIN_ID))
async def set_src(event):
    config["SOURCE_ID"], config["SOURCE_LINK"] = event.pattern_match.group(1), event.pattern_match.group(2)
    joined = await ensure_joined(config["SOURCE_LINK"])
    status = "✅ Joined" if joined else "❌ Failed to Join"
    await event.reply(f"Source Configured. Status: {status}")

@bot.on(events.NewMessage(pattern=r'/setdest (.*) (.*)', from_users=ADMIN_ID))
async def set_dest(event):
    config["DEST_ID"], config["DEST_LINK"] = event.pattern_match.group(1), event.pattern_match.group(2)
    joined = await ensure_joined(config["DEST_LINK"])
    status = "✅ Joined" if joined else "❌ Failed to Join"
    await event.reply(f"Dest Configured. Status: {status}")

@bot.on(events.NewMessage(pattern=r'/ask (.*)', from_users=ADMIN_ID))
async def ai_ask(event):
    prompt = event.pattern_match.group(1)
    response = get_ai_response(prompt)
    await event.reply(f"🤖 **AI Response:**\n\n{response}")

# --- BOT LOGIC (NUMBER REQUEST) ---

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    # Auto-attempt join if links exist but IDs are missing
    if config["SOURCE_LINK"]: await ensure_joined(config["SOURCE_LINK"])
    if config["DEST_LINK"]: await ensure_joined(config["DEST_LINK"])
    
    await event.reply("🇻🇪 **Venezuela Service Selection**", 
                     buttons=[Button.inline("🚀 Request Numbers", b"get_ven")])

@bot.on(events.CallbackQuery(data=b"get_ven"))
async def callback_handler(event):
    try:
        await event.edit("⏳ Contacting Provider...")
        await user_client.send_message(config['TARGET_BOT'], '/start')
        await asyncio.sleep(3)
        
        msgs = await user_client.get_messages(config['TARGET_BOT'], limit=1)
        if msgs and msgs[0].reply_markup:
            for r_idx, row in enumerate(msgs[0].reply_markup.rows):
                for c_idx, btn in enumerate(row.buttons):
                    if "Venezuela" in btn.text:
                        await msgs[0].click(r_idx, c_idx)
                        await asyncio.sleep(4)
                        
                        list_msgs = await user_client.get_messages(config['TARGET_BOT'], limit=1)
                        found_nums = re.findall(r'(58\d{10})', list_msgs[0].text)
                        
                        if found_nums:
                            for n in found_nums: pending_numbers[n] = event.chat_id
                            num_list_str = "\n".join([f"• `{n}`" for n in found_nums])
                            await event.edit(f"✅ **Numbers Active:**\n{num_list_str}\n\n⏳ Waiting for OTPs...", 
                                           buttons=[Button.inline("🔄 Refresh List", b"get_ven")])
                        else:
                            await event.edit("❌ Provider list empty. Try again in a minute.")
                        return
    except Exception as e:
        print(f"Error: {e}")
        await event.edit("⚠️ Connection Error. Ensure user account is active.")

# --- OTP FORWARDER (Visual Screenshot Format) ---

@user_client.on(events.NewMessage)
async def otp_forwarder(event):
    text = event.message.text or ""
    if config["SOURCE_ID"] and str(event.chat_id) != str(config["SOURCE_ID"]): return

    if "New" in text or "OTP" in text:
        otp_match = re.search(r'(\d{4,8})', text) # Matches 4-8 digit OTPs
        masked_match = re.search(r'Number:.*?([\d\*]+)', text)
        
        if otp_match and masked_match:
            otp_code = otp_match.group(1)
            m_num = masked_match.group(1)
            f4 = m_num.split('*')[0][:4]
            l4 = m_num.split('*')[-1][-4:]
            
            bot_user = (await bot.get_me()).username
            buttons = [
                [Button.inline(f"{otp_code}", b"none")],
                [Button.url("🚀 Panel", f"https://t.me/{bot_user}")],
                [Button.url("📱 Channel", config["CHANNEL_LINK"])]
            ]

            # Forwarding Logic
            for p_num, c_id in list(pending_numbers.items()):
                if p_num.startswith(f4) and p_num.endswith(l4):
                    # To the User
                    await bot.send_message(c_id, f"🇻🇪 VE | {f4}••{l4} | FB", buttons=buttons)
                    # To the Admin's Dest Group
                    if config["DEST_ID"]:
                        await bot.send_message(config["DEST_ID"], f"🇻🇪 VE | {f4}••{l4} | FB", buttons=buttons)
                    del pending_numbers[p_num]
                    break

# --- STARTUP ---
async def start_main():
    await user_client.start()
    await bot.start(bot_token=BOT_TOKEN)
    print("✅ System Online.")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    threading.Thread(target=run_server, daemon=True).start()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_main())
