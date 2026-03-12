from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import MessageNotModifiedError
from flask import Flask
import threading, asyncio, os, re, traceback, json

# --- FLASK KEEP-ALIVE ---
app = Flask(__name__)
@app.route('/')
def home(): return "🟢 OTP RELAY FIXED ID VERSION"

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

# CRITICAL FIX: Supergroup IDs MUST start with -100
SOURCE_ID = -1003633481131
DEST_ID = -1003824856633

# --- PERSISTENT APPROVAL SYSTEM ---
DB_FILE = "users.json"
def load_approved():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return set(json.load(f))
        except: return {ADMIN_ID}
    return {ADMIN_ID}

def save_approved():
    with open(DB_FILE, "w") as f: json.dump(list(approved_users), f)

approved_users = load_approved()
pending_numbers = {}

user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
bot = TelegramClient('bot_session', API_ID, API_HASH)

# --- ADMIN NOTIFICATIONS ---
async def send_to_admin(msg):
    try: await bot.send_message(ADMIN_ID, msg)
    except: pass

# --- ACCESS CONTROL ---
async def is_auth(event):
    if event.sender_id in approved_users: return True
    user = await event.get_sender()
    details = f"👤 Name: {user.first_name}\n🆔 ID: `{user.id}`\n🔗 User: @{user.username or 'None'}"
    await send_to_admin(f"🚫 **UNAUTHORIZED ATTEMPT**\n\n{details}")
    await event.reply("❌ **Access Denied.** Your details have been sent to admin.")
    return False

# --- ADMIN COMMANDS ---
@bot.on(events.NewMessage(pattern=r'/approve (\d+)', from_users=ADMIN_ID))
async def approve(event):
    uid = int(event.pattern_match.group(1))
    approved_users.add(uid)
    save_approved()
    await event.reply(f"✅ User `{uid}` Approved.")

@bot.on(events.NewMessage(pattern=r'/disapprove (\d+)', from_users=ADMIN_ID))
async def disapprove(event):
    uid = int(event.pattern_match.group(1))
    if uid in approved_users:
        approved_users.remove(uid)
        save_approved()
        await event.reply(f"❌ User `{uid}` Disapproved.")

# --- BOT LOGIC ---
@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    if not await is_auth(event): return
    await event.reply("🇻🇪 **Venezuela Relay Pro**", buttons=[Button.inline("🚀 Request Service", b"get_ven")])

@bot.on(events.CallbackQuery(data=b"get_ven"))
async def callback(event):
    if not await is_auth(event): return
    try:
        await event.edit("⏳ Fetching numbers...")
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
                        found = re.findall(r'(\d{10,15})', list_msgs[0].text)
                        if found:
                            for n in found: pending_numbers[n] = event.chat_id
                            num_str = "\n".join([f"• `{n}`" for n in found])
                            await event.edit(f"✅ **Numbers Fetched:**\n{num_str}", 
                                           buttons=[Button.inline("🔄 Refresh List", b"get_ven"),
                                                    Button.url("💬 OTP Group", "https://t.me/+6gHllUFSnBBmYzc1")])
                        return
    except Exception: await send_to_admin(traceback.format_exc())

# --- THE FORWARDER (Listener for Source Group) ---
@user_client.on(events.NewMessage)
async def forwarder(event):
    try:
        # Verify message is from your specific Source ID
        if event.chat_id != SOURCE_ID: return
        
        text = event.message.text or ""
        # Match Masked format (58••9064) and the OTP code
        masked_match = re.search(r'(\d{2})[•\*]+(\d{4})', text)
        otp_match = re.search(r'(\d{4,10})', text)

        if masked_match and otp_match:
            f2, l4 = masked_match.group(1), masked_match.group(2)
            otp_code = otp_match.group(1)
            
            bot_obj = await bot.get_me()
            btns = [[Button.inline(f"{otp_code}", b"none")],
                    [Button.url("🚀 Panel", f"https://t.me/{bot_obj.username}"),
                     Button.url("📱 Channel", "https://t.me/+6gHllUFSnBBmYzc1")]]

            for p_num, c_id in list(pending_numbers.items()):
                if p_num.startswith(f2) and p_num.endswith(l4):
                    caption = f"🇻🇪 VE | {f2}••{l4} | FB"
                    # 1. Send to the User who requested it
                    await bot.send_message(c_id, caption, buttons=btns)
                    # 2. Send to your Destination Group
                    try:
                        await bot.send_message(DEST_ID, caption, buttons=btns)
                    except Exception as e:
                        await send_to_admin(f"Forwarding Error: {e}\nCheck if Bot is Admin in Destination!")
                    
                    del pending_numbers[p_num]
                    break
    except Exception: await send_to_admin(traceback.format_exc())

# --- RUN ---
async def start_pro():
    await user_client.start()
    await bot.start(bot_token=BOT_TOKEN)
    print("✅ All systems go. Listening to Source Group.")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    threading.Thread(target=run_server, daemon=True).start()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_pro())
