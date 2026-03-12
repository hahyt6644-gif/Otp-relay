from telethon import TelegramClient, events, Button, functions
from telethon.sessions import StringSession
from telethon.errors import MessageNotModifiedError, InviteHashExpiredError, UserAlreadyParticipantError
from flask import Flask
import threading, asyncio, os, re, requests, traceback

# --- FLASK KEEP-ALIVE ---
app = Flask(__name__)
@app.route('/')
def home(): return "🟢 OTP SELF-HEALING SYSTEM ONLINE"

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
    "SOURCE_ID": 3633481131,       
    "DEST_ID": 5274614337,         
    "SOURCE_LINK": "https://t.me/+ZxBeMVFToXEzNDFh",     
    "DEST_LINK": "https://t.me/+6gHllUFSnBBmYzc1",       
    "CHANNEL_LINK": "https://t.me/YourChannel"
}

user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
bot = TelegramClient('bot_session', API_ID, API_HASH)
pending_numbers = {}

# --- AI ERROR FIXER ---
async def notify_admin_of_error(error_trace):
    try:
        # Get AI's take on the error
        ai_url = f"https://apis.prexzyvilla.site/ai/ai4chat?prompt=Fix this Python Telethon error: {error_trace[:500]}"
        ai_res = requests.get(ai_url).json()
        ai_advice = ai_res["data"]["response"] if ai_res.get("status") else "AI failed to analyze."
        
        error_msg = (
            "⚠️ **CRITICAL BOT ERROR**\n\n"
            f"**Raw Error:**\n`{error_trace[:1000]}`\n\n"
            f"🤖 **AI Suggestion:**\n{ai_advice}"
        )
        await bot.send_message(ADMIN_ID, error_msg)
    except Exception as e:
        print(f"Error in error handler: {e}")

# --- AUTO-JOIN HANDLER ---
async def ensure_groups_joined():
    for link in [config["SOURCE_LINK"], config["DEST_LINK"]]:
        if link and "t.me/+" in link:
            try:
                hash_part = link.split('+')[-1]
                await user_client(functions.messages.ImportChatInviteRequest(hash=hash_part))
            except (UserAlreadyParticipantError, InviteHashExpiredError):
                continue
            except Exception as e:
                await notify_admin_of_error(f"Join Failure: {e}")

# --- BOT LOGIC ---

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await ensure_groups_joined()
    await event.reply("🇻🇪 **Venezuela Service**\nStatus: Connected", 
                     buttons=[Button.inline("🚀 Request Numbers", b"get_ven")])

@bot.on(events.CallbackQuery(data=b"get_ven"))
async def callback_handler(event):
    try:
        await event.edit("⏳ Fetching list...")
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
                            
                            # Buttons including the OTP Group link
                            btns = [
                                [Button.inline("🔄 Refresh List", b"get_ven")],
                                [Button.url("💬 View OTP Group", config["SOURCE_LINK"])]
                            ]
                            await event.edit(f"✅ **Numbers Active:**\n{num_list_str}", buttons=btns)
                        return
    except Exception:
        await notify_admin_of_error(traceback.format_exc())
        await event.edit("❌ System Error. Admin has been notified.")

# --- OTP LISTENER ---

@user_client.on(events.NewMessage)
async def otp_forwarder(event):
    try:
        text = event.message.text or ""
        # The script is smart: it listens to the source and forwards to dest
        if "New" in text or "OTP" in text:
            otp_match = re.search(r'(\d{4,8})', text)
            masked_match = re.search(r'Number:.*?([\d\*]+)', text)
            
            if otp_match and masked_match:
                otp_code = otp_match.group(1)
                m_num = masked_match.group(1)
                f4, l4 = m_num.split('*')[0][:4], m_num.split('*')[-1][-4:]
                
                bot_me = await bot.get_me()
                buttons = [
                    [Button.inline(f"{otp_code}", b"none")],
                    [Button.url("🚀 Panel", f"https://t.me/{bot_me.username}")],
                    [Button.url("📱 Channel", config["CHANNEL_LINK"])]
                ]

                for p_num, c_id in list(pending_numbers.items()):
                    if p_num.startswith(f4) and p_num.endswith(l4):
                        # Send to User
                        await bot.send_message(c_id, f"🇻🇪 VE | {f4}••{l4} | FB", buttons=buttons)
                        # Post to Dest Group
                        if config["DEST_LINK"]:
                            await bot.send_message(config["DEST_ID"] or ADMIN_ID, f"🇻🇪 VE | {f4}••{l4} | FB", buttons=buttons)
                        del pending_numbers[p_num]
                        break
    except Exception:
        await notify_admin_of_error(traceback.format_exc())

# --- STARTUP ---
async def start_main():
    await user_client.start()
    await bot.start(bot_token=BOT_TOKEN)
    await ensure_groups_joined()
    print("✅ All systems go.")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    threading.Thread(target=run_server, daemon=True).start()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_main())
