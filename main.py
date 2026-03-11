from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import MessageNotModifiedError
import asyncio
import re

# --- CONFIGURATION ---
API_ID = 25240346
API_HASH = 'b8849fd945ed9225a002fda96591b6ee'
BOT_TOKEN = '7610030035:AAEJf2HX7lSg9H9QyS1Y1a8o_586qhvGmkg'

# ⚠️ PASTE YOUR BRAND NEW STRING SESSION HERE
STRING_SESSION = '1BVtsOLQBu1sWLUjy9O3WhRUoNkCwOcalVvxCOMrjYfFrUezu0qaZrlBK1CUHZE0cm4dnq4V58LhDxyat4qcpkQmCgyD65gCKoxGGc-ZVpMgPLLfg1BD235emPa_y3g3eyoBmCDXd9q01rKcQaacp174qxlomjy_rXM4xBiblwCWNhoztyIGBFERNDnkiKz3EztZAHd64nb4kK4NSN49BDl1hgxMfqaeIs2lIkRCUMHLyrYzrAZ4DY6biOsNakeaoHGrQJEecnn9V4xQEtm9zvfddkuVn6IiLMTDGjA4mBYbdjB6AaU-FubFhKRqjVhwU0mk5Aih2cqPrQ8nUHwMvrYp6HekIo8s='

TARGET_BOT = 'OsmanOTPs_Bot'

# --- INITIALIZATION ---
user_client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
bot = TelegramClient('bot_session', API_ID, API_HASH)

pending_numbers = {}

print("--- Linker Bot is Starting ---")

# --- BOT LOGIC ---

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.reply(
        "👋 Welcome to the OTP Linker!\n\nClick below to fetch the Venezuela service.",
        buttons=[Button.inline("🚀 Request Venezuela", b"get_ven")]
    )

@bot.on(events.CallbackQuery(data=b"get_ven"))
async def callback_handler(event):
    # 1. Gracefully handle the double-click / edit error
    try:
        await event.edit("⏳ Connecting to Provider Bot... Please wait.")
    except MessageNotModifiedError:
        pass # Ignore and keep going
    
    try:
        await user_client.send_message(TARGET_BOT, '/start')
        await asyncio.sleep(2.5) 
        
        messages = await user_client.get_messages(TARGET_BOT, limit=1)
        
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
                    await event.edit("✅ **Venezuela Selected!**\nWaiting for OTP generation...")
                except MessageNotModifiedError:
                    pass
                
                await asyncio.sleep(3.5)
                reply_msgs = await user_client.get_messages(TARGET_BOT, limit=1)
                
                if reply_msgs:
                    provider_text = reply_msgs[0].text
                    
                    # 2. BULLETPROOF REGEX: Grab any sequence of 8 to 15 digits
                    number_match = re.search(r'(\d{8,15})', provider_text)
                    
                    if number_match:
                        full_number = number_match.group(1)
                        pending_numbers[full_number] = event.chat_id
                        
                        try:
                            await event.edit(
                                f"📩 **Response from Provider:**\n\n{provider_text}",
                                buttons=[Button.inline("🔄 Get New Number", b"get_ven")]
                            )
                        except MessageNotModifiedError:
                            pass
                    else:
                        print(f"DEBUG - Extraction Failed. Raw: {repr(provider_text)}")
                        try:
                            await event.edit(
                                f"📩 **Response:**\n\n{provider_text}\n\n❌ Could not extract number.",
                                buttons=[Button.inline("🔄 Try Again", b"get_ven")]
                            )
                        except MessageNotModifiedError:
                            pass
            else:
                try:
                    await event.edit(
                        "❌ Could not find the 'Venezuela' option in the menu.",
                        buttons=[Button.inline("🔄 Try Again", b"get_ven")]
                    )
                except MessageNotModifiedError:
                    pass
                
    except Exception as e:
        print(f"Callback Error: {e}")


# --- GROUP LISTENER LOGIC ---

@user_client.on(events.NewMessage)
async def otp_group_listener(event):
    text = event.message.text or ""
    
    if "OTP Received" in text and "Number:" in text:
        # Match the masked number format (e.g., 58416***7420)
        masked_match = re.search(r'Number:\s*([\d\*]+)', text)
        
        if masked_match:
            masked_number = masked_match.group(1)
            parts = re.split(r'\*+', masked_number)
            
            if len(parts) == 2:
                first_4 = parts[0][:4]
                last_4 = parts[1][-4:]
                
                for pending_num, chat_id in list(pending_numbers.items()):
                    if pending_num.startswith(first_4) and pending_num.endswith(last_4):
                        await bot.send_message(chat_id, f"🎉 **OTP ARRIVED!**\n\n{text}")
                        del pending_numbers[pending_num]
                        break

# --- RUN ---
print("Starting clients...")
user_client.start()
bot.start(bot_token=BOT_TOKEN)
print("✅ Bot is Online and ready!")
bot.run_until_disconnected()
