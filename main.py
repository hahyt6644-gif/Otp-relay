from telethon import TelegramClient, events, Button, functions
from telethon.sessions import StringSession
from telethon.errors import MessageNotModifiedError, InviteHashExpiredError, UserAlreadyParticipantError
from flask import Flask
import threading, asyncio, os, re, requests, traceback

# --- FLASK WEB SERVER ---
app = Flask(name)
@app.route('/')
def home(): return "🟢 SYSTEM ONLINE: AI-HEALING ACTIVE"

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
    "SOURCE_ID": -1003633481131, # Replace with your Source Group ID (Integer)
    "DEST_ID": -1003824856633,   # Replace with your Dest Group ID (Integer)
    "SOURCE_LINK": "https://t.me/+ZxBeMVFToXEzNDFh",     
    "DEST_LINK": "https://t.me/+6gHllUFSnBBmYzc1",       
    "CHANNEL_LINK": "https://t.me/YourChannel" 
}

user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
bot = TelegramClient('bot_session', API_ID, API_HASH)
pending_numbers = {}

# --- HIGH-INTEL AI ERROR HANDLER ---
async def ai_self_fix(error_trace):
    try:
        # We read our own code to send it to the AI for a better fix
        with open(file, 'r') as f:
            code_snippet = f.read()[-1000:] # Last 1000 chars of code
            
        prompt = f"Fix this Python Telethon Error: {error_trace}. Here is the relevant code: {code_snippet}"
        ai_url = f"https://apis.prexzyvilla.site/ai/ai4chat?prompt={prompt}"
        
        res = requests.get(ai_url).json()
        advice = res["data"]["response"] if res.get("status") else "AI could not generate a fix."
        
        await bot.send_message(ADMIN_ID, f"⚠️ CRITICAL ERROR DETECTED\n\nError:\n{error_trace[:500]}\n\n🤖 AI FIX SUGGESTION:\n{advice}")
    except Exception as e:
        print(f"Failed to notify admin: {e}")

# --- AUTO-JOINER ---
async def auto_join():
    for link in [config["SOURCE_LINK"], config["DEST_LINK"]]:
        if link and "t.me/+" in link:
            try:
                hash_part = link.split('+')[-1]
                await user_client(functions.messages.ImportChatInviteRequest(hash=hash_part))
            except (UserAlreadyParticipantError, InviteHashExpiredError): continue
            except Exception as e: await ai_self_fix(f"Join Error: {e}")

# --- BOT LOGIC ---

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await auto_join()
    await event.reply("🇻🇪 Venezuela OTP Relay\nMode: Active", 
                     buttons=[Button.inline("🚀 Request Numbers", b"get_ven")])

@bot.on(events.CallbackQuery(data=b"get_ven"))
async def callback_handler(event):
    try:
        await event.edit("⏳ Contacting Provider Bot...")
    except MessageNotModifiedError: pass
    
    try:
        await user_client.send_message(config['TARGET_BOT'], '/start')
        await asyncio.sleep(3)
        
        # Click Venezuela and extract numbers
        msgs = await user_client.get_messages(config['TARGET_BOT'], limit=1)
        if msgs and msgs[0].reply_markup:
            for r_idx, row in enumerate(msgs[0].reply_markup.rows):
                for c_idx, btn in enumerate(row.buttons):
                    if "Venezuela" in btn.text:
                        await msgs[0].click(r_idx, c_idx)
                        await asyncio.sleep(5)
                        
                        list_msgs = await user_client.get_messages(config['TARGET_BOT'], limit=1)
                        # Bulletproof Digit Extraction
                        found_nums = re.findall(r'(\d{10,15})', list_msgs[0].text)
                        
                        if found_nums:
                            for n in found_nums: pending_numbers[n] = event.chat_id
                            num_str = "\n".join([f"• {n}" for n in found_nums])
                            
                            btns = [
                                [Button.inline("🔄 Refresh List", b"get_ven")],
                                [Button.url("💬 Join OTP Group", config["SOURCE_LINK"])]
                            ]
                            await event.edit(f"✅ Numbers Active:\n{num_str}", buttons=btns)
                        return
    except Exception:
        await ai_self_fix(traceback.format_exc())

# --- THE FORWARDER (mimics your screenshot) ---

@user_client.on(events.NewMessage)
async def otp_forwarder(event):
    try:
        text = event.message.text or ""
        # Check if the message is from your Source ID
        if config["SOURCE_ID"] and event.chat_id != int(config["SOURCE_ID"]): return

        if "OTP" in text or "New" in text:
            otp_match = re.search(r'(\d{4,8})', text)
            num_match = re.search(r'Number:.*?([\d\*]+)', text)
            
            if otp_match and num_match:
                otp = otp_match.group(1)
                m_num = num_match.group(1)
                f4, l4 = m_num.split('*')[0][:4], m_num.split('*')[-1][-4:]
                
                # Fetch bot username dynamically
                bot_user = (await bot.get_me()).username
                
                buttons = [
                    [Button.inline(f"{otp}", b"none")],
                    [Button.url("🚀 Panel", f"https://t.me/{bot_user}")],
                    [Button.url("📱 Channel", config["CHANNEL_LINK"])]
                ]

                caption = f"🇻🇪 VE | {f4}••{l4} | FB"

                # Match against pending numbers
                for p_num, c_id in list(pending_numbers.items()):
                    if p_num.startswith(f4) and p_num.endswith(l4):
                        # 1. Send to User
                        await bot.send_message(c_id, caption, buttons=buttons)
                        # 2. Forward to your Dest Group
                        if config["DEST_ID"]:
                            await bot.send_message(config["DEST_ID"], caption, buttons=buttons)
                        
                        del pending_numbers[p_num]
                        break
    except Exception:
        await ai_self_fix(traceback.format_exc())

# --- STARTUP ---
async def start_all():
    await user_client.start()
    await bot.start(bot_token=BOT_TOKEN)
    await auto_join()
    print("✅ System Ready.")
    await bot.run_until_disconnected()

if name == 'main':
    threading.Thread(target=run_server, daemon=True).start()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_all())
