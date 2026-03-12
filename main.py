from telethon import TelegramClient, events, Button, functions
from telethon.sessions import StringSession
from telethon.errors import MessageNotModifiedError, InviteHashExpiredError, UserAlreadyParticipantError
from flask import Flask
import threading, asyncio, os, re, traceback

# --- FLASK WEB SERVER (Keep-Alive) ---
app = Flask(__name__)
@app.route('/')
def home(): return "🟢 SECURE OTP RELAY ONLINE"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# --- CONFIGURATION ---
API_ID = 25240346
API_HASH = 'b8849fd945ed9225a002fda96591b6ee'
BOT_TOKEN = '7610030035:AAEJf2HX7lSg9H9QyS1Y1a8o_586qhvGmkg'
STRING_SESSION = '1BVtsOLQBu1sWLUjy9O3WhRUoNkCwOcalVvxCOMrjYfFrUezu0qaZrlBK1CUHZE0cm4dnq4V58LhDxyat4qcpkQmCgyD65gCKoxGGc-ZVpMgPLLfg1BD235emPa_y3g3eyoBmCDXd9q01rKcQaacp174qxlomjy_rXM4xBiblwCWNhoztyIGBFERNDnkiKz3EztZAHd64nb4kK4NSN49BDl1hgxMfqaeIs2lIkRCUMHLyrYzrAZ4DY6biOsNakeaoHGrQJEecnn9V4xQEtm9zvfddkuVn6IiLMTDGjA4mBYbdjB6AaU-FubFhKRqjVhwU0mk5Aih2cqPrQ8nUHwMvrYp6HekIo8s='

ADMIN_ID = 6357920694
TARGET_BOT = "UxOtpBOT"

# Correcting IDs for Telethon (adding -100 prefix for supergroups)
SOURCE_ID = -1003633481131
DEST_ID = -1003824856633

# Approval System (Admin is approved by default)
approved_users = {ADMIN_ID}
pending_numbers = {}

user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
bot = TelegramClient('bot_session', API_ID, API_HASH)

# --- ERROR HANDLER ---
async def send_error(error_text):
    try:
        await bot.send_message(ADMIN_ID, f"⚠️ **RAW SYSTEM ERROR:**\n\n`{error_text}`")
    except Exception as e:
        print(f"Failed to send error to admin: {e}")

# --- ADMIN COMMANDS ---

@bot.on(events.NewMessage(pattern=r'/approve (\d+)', from_users=ADMIN_ID))
async def approve_user(event):
    uid = int(event.pattern_match.group(1))
    approved_users.add(uid)
    await event.reply(f"✅ User `{uid}` has been approved.")
    await bot.send_message(uid, "🎉 **Congratulations!** Your account has been approved by the admin. Use /start to begin.")

@bot.on(events.NewMessage(pattern=r'/disapprove (\d+)', from_users=ADMIN_ID))
async def disapprove_user(event):
    uid = int(event.pattern_match.group(1))
    if uid in approved_users:
        approved_users.remove(uid)
        await event.reply(f"❌ User `{uid}` has been removed from approved list.")
    else:
        await event.reply("User was not in the list.")

# --- ACCESS CONTROL CHECK ---
async def is_authorized(event):
    if event.sender_id in approved_users:
        return True
    
    # Notify Admin of unauthorized attempt
    user = await event.get_sender()
    details = f"Name: {user.first_name}\nID: `{user.id}`\nUsername: @{user.username or 'None'}"
    await bot.send_message(ADMIN_ID, f"🚫 **UNAUTHORIZED ACCESS ATTEMPT**\n\n{details}")
    
    # Notify User
    await event.reply("❌ **Access Denied.**\nYou are not authorized to use this bot. Your details have been sent to the admin for review.")
    return False

# --- BOT LOGIC ---

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if not await is_authorized(event): return
    await event.reply("🇻🇪 **Secure OTP Relay**\nStatus: Authorized", 
                     buttons=[Button.inline("🚀 Request Numbers", b"get_ven")])

@bot.on(events.CallbackQuery(data=b"get_ven"))
async def callback_handler(event):
    if not await is_authorized(event): return
    
    try:
        await event.edit("⏳ Fetching...")
        await user_client.send_message(TARGET_BOT, '/start')
        await asyncio.sleep(3)
        
        msgs = await user_client.get_messages(TARGET_BOT, limit=1)
        if msgs and msgs[0].reply_markup:
            for r_idx, row in enumerate(msgs[0].reply_markup.rows):
                for c_idx, btn in enumerate(row.buttons):
                    if "Venezuela" in btn.text:
                        await msgs[0].click(r_idx, c_idx)
                        await asyncio.sleep(4)
                        
                        list_msgs = await user_client.get_messages(TARGET_BOT, limit=1)
                        found_nums = re.findall(r'(\d{10,15})', list_msgs[0].text)
                        
                        if found_nums:
                            for n in found_nums: pending_numbers[n] = event.chat_id
                            num_str = "\n".join([f"• `{n}`" for n in found_nums])
                            await event.edit(f"✅ **Active Numbers:**\n{num_str}", 
                                           buttons=[Button.inline("🔄 Refresh List", b"get_ven")])
                        return
    except Exception:
        await send_error(traceback.format_exc())

# --- OTP LISTENER ---

@user_client.on(events.NewMessage)
async def otp_forwarder(event):
    try:
        if event.chat_id != SOURCE_ID: return
        
        text = event.message.text or ""
        if "OTP" in text or "New" in text:
            otp_match = re.search(r'(\d{4,8})', text)
            num_match = re.search(r'Number:.*?([\d\*]+)', text)
            
            if otp_match and num_match:
                otp = otp_match.group(1)
                m_num = num_match.group(1)
                f4, l4 = m_num.split('*')[0][:4], m_num.split('*')[-1][-4:]
                
                bot_user = (await bot.get_me()).username
                buttons = [[Button.inline(f"{otp}", b"none")],
                           [Button.url("🚀 Panel", f"https://t.me/{bot_user}")]]

                for p_num, c_id in list(pending_numbers.items()):
                    if p_num.startswith(f4) and p_num.endswith(l4):
                        caption = f"🇻🇪 VE | {f4}••{l4} | FB"
                        await bot.send_message(c_id, caption, buttons=buttons)
                        await bot.send_message(DEST_ID, caption, buttons=buttons)
                        del pending_numbers[p_num]
                        break
    except Exception:
        await send_error(traceback.format_exc())

# --- RUN ---
async def start_all():
    await user_client.start()
    await bot.start(bot_token=BOT_TOKEN)
    print("✅ Secure Bot Online.")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    threading.Thread(target=run_server, daemon=True).start()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_all())
