import os
import time
import httpx
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import FloodWait, RPCError
from pymongo import MongoClient
from collections import defaultdict
from pyrogram.enums import ParseMode
from force_join import check_membership
from server import keep_alive


# Configuration
API_ID = 26222466
API_HASH = "9f70e2ce80e3676b56265d4510561aef"
BOT_TOKEN = "7915253544:AAHWDhXpzE6I_L6Aq3reCzbm__7CAAhgqdI"
GROUP_LINK = 'https://t.me/hyporesetgc'
DEVELOPER = 'botplays90'
ADMIN_ID = 6897739611
MONGO_URI = "mongodb+srv://botplays90:botplays90@botplays.ycka9.mongodb.net/?retryWrites=true&w=majority&appName=botplays"
user_cooldowns = {}


# MongoDB setup
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["reset_bot"]
users_col = db["users"]
stats_col = db["stats"]
sticker_col = db["sticker"]

# Pyrogram client
app = Client(
    "reset_bot",
    api_id=API_ID,          # Add this
    api_hash=API_HASH,      # Add this
    bot_token=BOT_TOKEN,
    workers=100,
    max_concurrent_transmissions=20
)

# State management
user_reset_state = {}
pending_verification = {}

@app.on_message(filters.command(["start", "resett"]) & filters.private)
@check_membership
async def handle_start_private(client, message: Message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    
    # Send sticker if available
    sticker_doc = sticker_col.find_one({"_id": "default"})
    if sticker_doc:
        try:
            sent_sticker = await client.send_sticker(user_id, sticker_doc["file_id"])
            await asyncio.sleep(0.9)
            await client.delete_messages(user_id, sent_sticker.id)
        except Exception as e:
            print(f"Sticker error: {e}")
    
    # Register user
    if not users_col.find_one({"_id": user_id}):
        users_col.insert_one({"_id": user_id, "name": name})
    
    # Send welcome message
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⛔️ resetGc", url=GROUP_LINK),
         InlineKeyboardButton("👨‍💻 Developer", url=f"https://t.me/{DEVELOPER}")],
        [InlineKeyboardButton("[+] Add Me to Group", 
         url=f"https://t.me/{client.me.username}?startgroup=true")]
    ])
    
    await message.reply_text(
        f'❇️ Heyy {name}\n🆔id={user_id}\n\n'
        "🚫 This bot works only in groups!\n\n"
        "👉 Add me to your group to use the reset feature.\n"
        "👉 Then use /resett in your group",
        reply_markup=markup
    )

@app.on_message(filters.command("resett") & filters.group)
async def handle_reset_group(client, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Register group
    if not users_col.find_one({"_id": chat_id}):
        users_col.insert_one({
            "_id": chat_id, 
            "name": message.chat.title
        })
    
    # Check if user is registered
    if not users_col.find_one({"_id": user_id}):
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "👉 Start Bot in Private", 
                url=f"https://t.me/{client.me.username}?start=start"
            )
        ]])
        await message.reply_text(
            "❌ You must start the bot in private chat before using it in groups.\n\n"
            "Click the button below to get started.",
            reply_markup=markup
        )
        return
    
    # Process reset command
    if len(message.command) > 1:
        input_text = ' '.join(message.command[1:])
        await process_reset_request(client, message, input_text)
    else:
        msg = await message.reply_text(
            "📩 Reply To This Message With Your username/email you want to reset:",
            reply_to_message_id=message.id
        )
        user_reset_state[user_id] = {
            "chat_id": chat_id,
            "prompt_msg_id": msg.id
        }

@app.on_message(filters.group & filters.reply)
async def handle_reset_reply(client, message: Message):
    user_id = message.from_user.id

    if user_id not in user_reset_state:
        return

    state = user_reset_state[user_id]
    if (
        message.chat.id != state["chat_id"]
        or message.reply_to_message_id != state["prompt_msg_id"]
    ):
        return

    # Split inputs
    inputs = [
        x.strip() for x in message.text.replace(",", "\n").split("\n")
        if x.strip()
    ]

    if not inputs:
        await message.reply_text("❌ Please provide at least one valid username/email.")
        return

    if len(inputs) > 5:
        await message.reply_text("❌ You can only reset a maximum of 5 accounts at once.")
        return

    # Only apply cooldown if batch (2 to 5 inputs)
    if len(inputs) > 1:
        if user_id in user_cooldowns:
            await message.reply_text("⏳ You must wait 30 seconds before sending another batch of resets.")
            return
        user_cooldowns[user_id] = True
        asyncio.create_task(remove_batch_cooldown(user_id))

    # Start processing
    processing_msg = await message.reply_text(f"⚡ Processing {len(inputs)} accounts...")

    semaphore = asyncio.Semaphore(5)
    tasks = [
        process_reset_request(client, message, input_text, semaphore)
        for input_text in inputs
    ]

    await asyncio.gather(*tasks)

    try:
        await client.delete_messages(message.chat.id, processing_msg.id)
    except:
        pass

    del user_reset_state[user_id]

async def remove_batch_cooldown(user_id):
    await asyncio.sleep(30)
    user_cooldowns.pop(user_id, None)



async def process_reset_request(client, message: Message, input_text: str, semaphore=None):
    start_time = time.time()

    if semaphore:
        async with semaphore:
            await handle_reset_logic(client, message, input_text, start_time)
    else:
        await handle_reset_logic(client, message, input_text, start_time)

async def handle_request_error(client, message, input_text, error, start_time):
    await message.reply_text(f"⚠️ Request error for {input_text}:\n{error}")

async def handle_rpc_error(client, message, input_text, error, start_time):
    await message.reply_text(f"⚠️ Telegram RPC error for {input_text}:\n{error}")

async def handle_generic_error(client, message, input_text, error, start_time):
    await message.reply_text(f"⚠️ Unexpected error for {input_text}:\n{error}")



async def handle_reset_logic(client, message: Message, input_text: str, start_time):
    chat_id = message.chat.id
    user = message.from_user

    try:
        temp_msg = await client.send_message(
            chat_id,
            f"⚡️ Sending reset to {input_text}",
            reply_to_message_id=message.id
        )

        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.post(
                'https://i.instagram.com/api/v1/accounts/send_password_reset/',
                headers={
                    'user-agent': 'Mozilla/5.0',
                    'x-csrftoken': 'vEG96oJnlEsyUWNS53bHLkVTMFYQKCBV'
                },
                data={"user_email": input_text}
            )
            res = response.json()

        speed = round(time.time() - start_time, 2)
        status = res.get("status", "fail")
        obfuscated = res.get("obfuscated_email", input_text)

        if status != 'ok':
            error_message = res.get('message', 'Unknown error')
            result_text = (
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔹 Status: ❌ Failed\n"
                f"🔹 Account: {obfuscated}\n"
                f"🔹 Reason: {error_message}\n"
                f"🔹 Processed by: @{user.first_name}\n"
                f"⚡ Speed: {speed} seconds\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💎 Bot by @BotPlays90"
            )
        else:
            stats_col.update_one(
                {"_id": "reset_counter"},
                {"$inc": {"count": 1}},
                upsert=True
            )
            result_text = (
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔹 Status: ✅ Success\n"
                f"🔹 Account: {obfuscated}\n"
                f"🔹 Processed by: @{user.first_name}\n"
                f"⚡ Speed: {speed} seconds\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💎 Bot by @BotPlays90"
            )

        await client.delete_messages(chat_id, temp_msg.id)
        await client.send_message(
            chat_id,
            result_text,
            reply_to_message_id=message.id
        )

    except httpx.RequestError as e:
        await handle_request_error(client, message, input_text, e, start_time)
    except RPCError as e:
        await handle_rpc_error(client, message, input_text, e, start_time)
    except Exception as e:
        await handle_generic_error(client, message, input_text, e, start_time)




# Admin commands
@app.on_message(filters.command("users") & filters.user(ADMIN_ID))
async def list_users(client, message: Message):
    users = users_col.find()
    text = "👥 <b>Registered Users:</b>\n\n"
    for u in users:
        safe_name = (u.get("name") or "Unknown").replace("<", "&lt;").replace(">", "&gt;")
        text += f"- {safe_name} (<code>{u['_id']}</code>)\n"
    
    await message.reply_text(text, parse_mode="HTML")

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def show_stats(client, message: Message):
    total_users = users_col.count_documents({})
    reset_stats = stats_col.find_one({"_id": "reset_counter"})
    reset_count = reset_stats.get("count", 0) if reset_stats else 0
    
    text = (
        "<b>📊 Bot Stats:</b>\n\n"
        f"👥 Total Users/Groups: <b>{total_users}</b>\n"
        f"🔁 Total Resets Done: <b>{reset_count}</b>\n"
    )
    
    await message.reply_text(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID) & filters.reply)
async def broadcast(client, message: Message):
    targets = users_col.find()
    sent = 0
    failed = 0
    
    for target in targets:
        try:
            await client.copy_message(
                chat_id=target['_id'],
                from_chat_id=message.chat.id,
                message_id=message.reply_to_message.id
            )
            sent += 1
        except Exception as e:
            print(f"Broadcast failed to {target['_id']}: {e}")
            failed += 1
    
    await message.reply_text(
        f"✅ Broadcast Summary:\n\n"
        f"📤 Sent: {sent}\n"
        f"❌ Failed: {failed}\n"
        f"📦 Total Targets: {sent + failed}"
    )

@app.on_message(filters.command("setsticker") & filters.user(ADMIN_ID) & filters.reply)
async def set_sticker(client, message: Message):
    if not message.reply_to_message.sticker:
        return await message.reply_text("❌ Please reply to a sticker to save it.")
    
    file_id = message.reply_to_message.sticker.file_id
    sticker_col.update_one(
        {"_id": "default"}, 
        {"$set": {"file_id": file_id}}, 
        upsert=True
    )
    await message.reply_text("✅ Sticker has been saved.")

@app.on_message(filters.command("removesticker") & filters.user(ADMIN_ID))
async def remove_sticker(client, message: Message):
    result = sticker_col.delete_one({"_id": "default"})
    if result.deleted_count:
        await message.reply_text("🗑️ Sticker has been removed.")
    else:
        await message.reply_text("⚠️ No sticker was set.")

# Handle group additions/removals
@app.on_chat_member_updated()
async def handle_chat_member_update(client, update):
    if update.new_chat_member and update.new_chat_member.user.id == client.me.id:
        # Bot added to group
        if not users_col.find_one({"_id": update.chat.id}):
            users_col.insert_one({
                "_id": update.chat.id, 
                "name": update.chat.title
            })
            print(f"Bot added to: {update.chat.title} ({update.chat.id})")
    elif (update.old_chat_member and 
          update.old_chat_member.user.id == client.me.id and
          update.new_chat_member.status == "left"):
        # Bot removed from group
        users_col.delete_one({"_id": update.chat.id})
        print(f"Bot removed from: {update.chat.title} ({update.chat.id})")

keep_alive()

if __name__ == "__main__":
    print("[✓] Bot is Online — Optimized for speed")
    app.run()
