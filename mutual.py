import os
import random
import asyncio
import zipfile
from telethon import TelegramClient, events, functions
from telethon.tl.functions.channels import InviteToChannelRequest, JoinChannelRequest
from telethon.errors import (
    FloodWaitError, UserPrivacyRestrictedError, 
    PeerFloodError, UserAlreadyParticipantError,
    UserChannelsTooMuchError, UserBannedInChannelError
)

# ==================== CONFIGURATION ====================
API_ID = 8407612 
API_HASH = 'ead6912bce303e57b80130276451200f'
BOT_TOKEN = '7937328325:AAEzT3FlBv2SPun6R2E2vm5emA5MrPw2ajs'

ADMIN_IDS = [5425526761,8396275064] 

# --- Timing & Limits ---
MIN_ADD_DELAY = 2      
MAX_ADD_DELAY = 5      
ACC_SWITCH_DELAY = 1    # Minutes
ROUND_GAP = 1          # Minutes
ADDS_PER_ROUND = 20     
TOTAL_ROUNDS = 5        

SESSIONS_DIR = 'sessions/'
TARGET_GROUP = "none" 
# ========================================================

os.makedirs(SESSIONS_DIR, exist_ok=True)

bot = TelegramClient('master_pro_bot', API_ID, API_HASH)

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ==================== ADMIN COMMANDS ====================

@bot.on(events.NewMessage(pattern='/start'))
async def start_cmd(event):
    if not is_admin(event.sender_id): return
    await event.reply(
        "🚀 **Professional Adder (Final Version)**\n\n"
        "**Commands:**\n"
        "📍 `/setgroup @username` - Set target\n"
        "📊 `/status` - Check stats\n"
        "🔍 `/check` - Cleanup dead sessions\n"
        "📦 `/export` - Download all sessions\n"
        "⚡️ `/start_adding` - Start process"
    )

@bot.on(events.NewMessage)
async def handle_session_upload(event):
    if not is_admin(event.sender_id) or not event.document: return
    if event.file.name and event.file.name.endswith('.session'):
        path = os.path.join(SESSIONS_DIR, event.file.name)
        await event.download_media(file=path)
        await event.reply(f"📥 **Session Saved:** `{event.file.name}`")

@bot.on(events.NewMessage(pattern='/setgroup'))
async def set_group(event):
    global TARGET_GROUP
    if not is_admin(event.sender_id): return
    try:
        TARGET_GROUP = event.text.split(' ')[1].replace("https://t.me/", "@")
        await event.reply(f"🎯 **Target Set:** {TARGET_GROUP}")
    except:
        await event.reply("❌ Usage: `/setgroup @group_username`")

@bot.on(events.NewMessage(pattern='/status'))
async def check_status(event):
    if not is_admin(event.sender_id): return
    files = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
    await event.reply(f"📊 **Status**\n📂 Sessions Loaded: {len(files)}\n🎯 Target: {TARGET_GROUP}")

@bot.on(events.NewMessage(pattern='/check'))
async def audit(event):
    if not is_admin(event.sender_id): return
    files = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
    if not files: return await event.reply("📂 No sessions found.")

    msg = await event.reply("🔍 Auditing sessions... please wait.")
    report = "📑 **Audit Results:**\n"
    
    for f in files:
        path = os.path.join(SESSIONS_DIR, f)
        c = TelegramClient(path, API_ID, API_HASH)
        try:
            await c.connect()
            if not await c.is_user_authorized(): 
                raise Exception("Unauthorized")
            me = await c.get_me()
            report += f"✅ {f} (+{me.phone})\n"
        except Exception:
            report += f"❌ {f} (Dead) - Removed\n"
            os.remove(path)
        finally: 
            await c.disconnect()
            
    await bot.edit_message(event.chat_id, msg.id, report)

@bot.on(events.NewMessage(pattern='/export'))
async def export_sessions(event):
    if not is_admin(event.sender_id): return
    zip_name = "backup_sessions.zip"
    with zipfile.ZipFile(zip_name, 'w') as zipf:
        for f in os.listdir(SESSIONS_DIR):
            if f.endswith('.session'):
                zipf.write(os.path.join(SESSIONS_DIR, f), f)
    await bot.send_file(event.chat_id, zip_name, caption="📦 All sessions exported.")
    os.remove(zip_name)

# ==================== CORE ADDING LOGIC ====================

@bot.on(events.NewMessage(pattern='/start_adding'))
async def start_adding(event):
    if not is_admin(event.sender_id): return
    if TARGET_GROUP == "none": return await event.reply("❌ Use `/setgroup @username` first.")

    session_files = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
    if not session_files: return await event.reply("❌ No sessions found in folder.")
    
    pointers = {s: 0 for s in session_files}
    
    await event.reply(f"🏁 **Adding Started!**\n🔄 Total Rounds: {TOTAL_ROUNDS}\n👥 Accounts: {len(session_files)}")

    for r in range(1, TOTAL_ROUNDS + 1):
        await bot.send_message(event.chat_id, f"🕒 **ROUND {r}/{TOTAL_ROUNDS} STARTED**")
        
        for s_file in session_files:
            path = os.path.join(SESSIONS_DIR, s_file)
            if not os.path.exists(path): continue
            
            client = TelegramClient(path, API_ID, API_HASH)
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    await bot.send_message(event.chat_id, f"⚠️ **{s_file}** is logged out. Skipping.")
                    continue

                # 1. Resolve Target Group
                try:
                    target_entity = await client.get_entity(TARGET_GROUP)
                    await client(JoinChannelRequest(target_entity))
                except Exception as e:
                    await bot.send_message(event.chat_id, f"❌ **{s_file}** failed to resolve group:\n`{str(e)}`")
                    continue

                # 2. Get Contacts
                contacts = await client(functions.contacts.GetContactsRequest(hash=0))
                users = [u for u in contacts.users if not u.bot and not u.deleted]
                
                start_idx = pointers[s_file]
                batch = users[start_idx : start_idx + ADDS_PER_ROUND]

                if not batch:
                    await bot.send_message(event.chat_id, f"ℹ️ **{s_file}**: No more mutual contacts to add.")
                    continue

                # Counters
                added_count = 0
                privacy_count = 0
                already_count = 0
                flood_status = "None"
                raw_errors = []

                # 3. Add Loop
                for user in batch:
                    try:
                        await client(InviteToChannelRequest(target_entity, [user]))
                        added_count += 1
                        await asyncio.sleep(random.randint(MIN_ADD_DELAY, MAX_ADD_DELAY))
                        
                    except UserPrivacyRestrictedError:
                        privacy_count += 1
                    except UserAlreadyParticipantError:
                        already_count += 1
                    except (UserChannelsTooMuchError, UserBannedInChannelError) as e:
                        raw_errors.append(f"[{user.id}] {str(e)}")
                    except FloodWaitError as e:
                        flood_status = f"FloodWait ({e.seconds}s)"
                        break # Halt adding for this account
                    except PeerFloodError:
                        flood_status = "PeerFlood (Spam Limited)"
                        break # Halt adding for this account
                    except Exception as e:
                        raw_errors.append(f"[{user.id}] {str(e)}")

                # Move pointer forward regardless of success/fail to prevent infinite looping on same bad contacts
                pointers[s_file] += len(batch)
                
                # 4. Generate Admin Report
                report = (
                    f"📈 **Report: {s_file}**\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ **Added Successfully:** {added_count}\n"
                    f"🛡 **Blocked by Privacy:** {privacy_count}\n"
                    f"👥 **Already in Group:** {already_count}\n"
                    f"🛑 **Flood Status:** {flood_status}\n"
                )
                
                if raw_errors:
                    report += "\n⚠️ **Raw Errors Encountered:**\n"
                    for err in raw_errors[:5]:
                        report += f"`{err}`\n"
                    if len(raw_errors) > 5:
                        report += f"...and {len(raw_errors) - 5} more errors.\n"

                await bot.send_message(event.chat_id, report)
                await asyncio.sleep(ACC_SWITCH_DELAY * 60)

            except Exception as e:
                await bot.send_message(event.chat_id, f"❌ **Critical Error on {s_file}:**\n`{str(e)}`")
            finally:
                if client.is_connected():
                    await client.disconnect()

        # Inter-round cooldown
        if r < TOTAL_ROUNDS:
            await bot.send_message(event.chat_id, f"⏳ Round {r} finished. Waiting {ROUND_GAP} mins before next round...")
            await asyncio.sleep(ROUND_GAP * 60)

    await bot.send_message(event.chat_id, "🏆 **All Rounds Complete! Process Finished.**")

async def main():
    await bot.start(bot_token=BOT_TOKEN)
    print("-----------------------------------")
    print("🚀 BOT ACTIVE & READY TO RECEIVE COMMANDS")
    print("-----------------------------------")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
