import telebot, requests, time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask 
from threading import Thread 
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from collections import defaultdict

pending_batches = defaultdict(list)

from collections import defaultdict, deque

pending_batches = defaultdict(list)
batch_queue = deque()
current_batch_user = None



BOT_TOKEN = "7915253544:AAGwNkzHzezVltMC6SyEEQsIaYMH0LHMf0c"

FORCE_CHANNELS = ["join_hyponet", "codexverse"]  # Channel usernames without @


GROUP_LINK = 'https://t.me/hyporesetgc'
BOT_LINK = "https://t.me/insta_reset_robot"  # Replace with your bot's link

ADMIN_ID = 6897739611  # your Telegram user ID

from pymongo import MongoClient

MONGO_URI = "mongodb+srv://botplays90:botplays90@botplays.ycka9.mongodb.net/?retryWrites=true&w=majority&appName=botplays"
client = MongoClient(MONGO_URI)
db = client["reset_bot"]
users_col = db["users"]
stats_col = db["stats"]
sticker_col = db["sticker"]
pending_col = db["pending_batches"]
queue_col = db["batch_queue"]
settings_col = db["settings"]




bot = telebot.TeleBot(BOT_TOKEN)
deveop='botplays90'
user_reset_state = {}
pending_verification = {}  # To track users who need to verify

app = Flask('')

@app.route('/')
def home():
    return "Bot is running"

def run_http_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_http_server)
    t.start()


def is_user_joined(user_id):
    for channel in FORCE_CHANNELS:
        try:
            member = bot.get_chat_member(f"@{channel}", user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

def check_membership(func):
    def wrapper(message: Message, *args, **kwargs):
        if not is_user_joined(message.from_user.id):
            buttons = InlineKeyboardMarkup()
            for channel in FORCE_CHANNELS:
                buttons.add(InlineKeyboardButton(f"📢 Join @{channel}", url=f"https://t.me/{channel}"))
            buttons.add(InlineKeyboardButton("✅ I’ve Joined", callback_data="check_joined"))
            bot.send_message(
                message.chat.id,
                "🚨 You must join all required channels to use this bot.",
                reply_markup=buttons
            )
            return
        return func(message, *args, **kwargs)
    return wrapper

@bot.callback_query_handler(func=lambda call: call.data == "check_joined")
def verify_channel_join(call):
    user_id = call.from_user.id
    if is_user_joined(user_id):
        bot.answer_callback_query(call.id, "✅ You're verified!")
        bot.send_message(user_id, "Thanks for joining! You can now use the bot.\n\nType /start to begin.")
    else:
        bot.answer_callback_query(call.id, "❌ You're still not a member of all channels!", show_alert=True)



def send_verification_prompt(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    message_id = message.message_id

    markup = InlineKeyboardMarkup()

    # Add buttons for each required channel
    buttons = []
    for channel, url in REQUIRED_CHANNELS.items():
        buttons.append(InlineKeyboardButton(f"{channel}", url=url))

    # Add buttons in rows of 2
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.row(buttons[i], buttons[i + 1])
        else:
            markup.row(buttons[i])

    # Add verify button
    markup.add(InlineKeyboardButton("✅ I've Joined - Verify Now", callback_data=f"verify_{user_id}"))

    text = (
        "🔒 *Verification Required*\n\n"
        f"👤 *User*: {first_name}\n"
        f"🆔 *User ID*: `{user_id}`\n\n"
        "To use this bot, you must join our official channels:\n\n"
        "👉 Then click the *Verify Now* button\n\n"
        "You'll be able to use /resett after verification!"
    )

    try:
        bot.send_message(
            chat_id,
            text,
            reply_markup=markup,
            reply_to_message_id=message_id,
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"[!] Error sending verification prompt: {e}")



@bot.message_handler(commands=['users'])
def list_users(message):
    if message.from_user.id != ADMIN_ID:
        return

    users = users_col.find()
    text = "👥 <b>Registered Users:</b>\n\n"
    for u in users:
        safe_name = (u.get("name") or "Unknown").replace("<", "&lt;").replace(">", "&gt;")
        text += f"- {safe_name} (<code>{u['_id']}</code>)\n"

    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if message.from_user.id != ADMIN_ID:
        return

    total_users = users_col.count_documents({})
    reset_stats = stats_col.find_one({"_id": "reset_counter"})
    reset_count = reset_stats.get("count", 0) if reset_stats else 0

    text = (
        "<b>📊 Bot Stats:</b>\n\n"
        f"👥 Total Users/Groups: <b>{total_users}</b>\n"
        f"🔁 Total Resets Done: <b>{reset_count}</b>\n"
    )

    bot.send_message(message.chat.id, text, parse_mode="HTML")



@bot.my_chat_member_handler()
def handle_bot_added_or_removed(event):
    chat = event.chat
    status = event.new_chat_member.status

    if status in ["member", "administrator"]:
        # Save channel/group ID
        if not users_col.find_one({"_id": chat.id}):
            users_col.insert_one({"_id": chat.id, "name": chat.title})
            print(f"[+] Bot added to: {chat.title} ({chat.id})")
    elif status in ["left", "kicked"]:
        # Optionally remove if bot was removed
        users_col.delete_one({"_id": chat.id})
        print(f"[-] Bot removed from: {chat.title} ({chat.id})")



@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return

    if not message.reply_to_message:
        bot.reply_to(message, "✏️ Please reply to the message you want to broadcast.")
        return

    targets = users_col.find()
    sent = 0
    failed = 0

    for target in targets:
        try:
            bot.copy_message(
                chat_id=target['_id'],
                from_chat_id=message.chat.id,
                message_id=message.reply_to_message.message_id
            )
            sent += 1
        except Exception as e:
            print(f"[x] Failed to send to {target['_id']}: {e}")
            failed += 1

    bot.send_message(
        message.chat.id,
        f"✅ Broadcast Summary:\n\n"
        f"📤 Sent: {sent}\n"
        f"❌ Failed: {failed}\n"
        f"📦 Total Targets: {sent + failed}"
    )


@bot.message_handler(commands=["setsticker"])
def set_sticker(message):
    if message.from_user.id != ADMIN_ID:
        return

    if not message.reply_to_message or not message.reply_to_message.sticker:
        return bot.reply_to(message, "❌ Please reply to a sticker to save it.")

    file_id = message.reply_to_message.sticker.file_id
    sticker_col.update_one({"_id": "default"}, {"$set": {"file_id": file_id}}, upsert=True)
    bot.reply_to(message, "✅ Sticker has been saved.")


@bot.message_handler(commands=["removesticker"])
def remove_sticker(message):
    if message.from_user.id != ADMIN_ID:
        return

    result = sticker_col.delete_one({"_id": "default"})
    if result.deleted_count:
        bot.reply_to(message, "🗑️ Sticker has been removed.")
    else:
        bot.reply_to(message, "⚠️ No sticker was set.")



@bot.message_handler(commands=['start', 'resett'])
@check_membership
def handle_commands(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    chat_type = message.chat.type
    chat_title = message.chat.title if message.chat.title else message.from_user.first_name
    name = message.from_user.first_name

    if message.text.strip() == "/start":
        sticker_doc = sticker_col.find_one({"_id": "default"})
        if sticker_doc:
            try:
                sent_sticker = bot.send_sticker(chat_id, sticker_doc["file_id"])
                time.sleep(0.9)
                bot.delete_message(chat_id, sent_sticker.message_id)
            except Exception as e:
                print(f"[!] Failed to send/delete sticker: {e}")


    # 1. Save group/channel ID for broadcast
    if chat_type in ["group", "supergroup", "channel"]:
        if not users_col.find_one({"_id": chat_id}):
            users_col.insert_one({"_id": chat_id, "name": chat_title})

    # 2. Check if user is registered (for group use)
    if not users_col.find_one({"_id": user_id}):
        if chat_type != "private":
            # Ask to start the bot in private
            btn = InlineKeyboardMarkup()
            btn.add(InlineKeyboardButton("👉 Start Bot in Private", url=f"https://t.me/{bot.get_me().username}?start=start"))

            bot.reply_to(
                message,
                "❌ You must start the bot in private chat before using it in groups.\n\nClick the button below to get started.",
                reply_markup=btn
            )
            return
        else:
            users_col.insert_one({"_id": user_id, "name": name})

    # 3. Private Chat: Show intro & prompt to add to group
    if chat_type == "private":
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("⛔️ resetGc", url=GROUP_LINK),
            InlineKeyboardButton("👨‍💻 Developer", url=f"https://t.me/{deveop}")
        )
        markup.add(
            InlineKeyboardButton("[+] Add Me to Group", url=f"https://t.me/{bot.get_me().username}?startgroup=true")
        )
        bot.send_message(
            chat_id,
            f'❇️ Heyy {name}\n🆔id={user_id}\n\n'
            "🚫 This bot works only in groups!\n\n"
            "👉 Add me to your group to use the reset feature.\n"
            "👉 Then use /resett in your group",
            reply_markup=markup
        )
        return

    # 4. Group Chat: Handle /resett logic
    if message.text.startswith('/resett'):
        if len(message.text.split()) > 1:
            process_reset_request(message, ' '.join(message.text.split()[1:]))
        else:
            msg = bot.reply_to(message, "📩 Reply To This Message With Your username/email you want to reset:")
            user_reset_state[user_id] = {
                "chat_id": chat_id,
                "prompt_msg_id": msg.message_id
            }



def get_pending(user_id):
    doc = pending_col.find_one({"_id": user_id})
    return doc["inputs"] if doc else []

def set_pending(user_id, inputs):
    pending_col.update_one({"_id": user_id}, {"$set": {"inputs": inputs}}, upsert=True)

def remove_pending(user_id):
    pending_col.delete_one({"_id": user_id})

def enqueue_batch(user_id, chat_id, msg_id):
    if not queue_col.find_one({"user_id": user_id}):
        queue_col.insert_one({"user_id": user_id, "chat_id": chat_id, "msg_id": msg_id})

def dequeue_batch():
    doc = queue_col.find_one_and_delete({})
    return (doc["user_id"], doc["chat_id"], doc["msg_id"]) if doc else None

def get_current_user():
    doc = settings_col.find_one({"_id": "current_user"})
    return doc["user_id"] if doc else None

def set_current_user(user_id):
    settings_col.update_one({"_id": "current_user"}, {"$set": {"user_id": user_id}}, upsert=True)

def clear_current_user():
    settings_col.delete_one({"_id": "current_user"})





import telebot.apihelper

def process_reset_request(message, input_text):
    user_id = message.from_user.id
    start_time = time.time()

    try:
        res = requests.post(
            'https://i.instagram.com/api/v1/accounts/send_password_reset/',
            headers={
                'user-agent': 'Mozilla/5.0',
                'x-csrftoken': 'vEG96oJnlEsyUWNS53bHLkVTMFYQKCBV'
            },
            data={"user_email": input_text}
        ).json()

        speed = round(time.time() - start_time, 2)
        status = res.get("status", "fail")
        obfuscated = res.get("obfuscated_email", input_text)

        x = bot.send_message(message.chat.id, f"⚡️ sending reset to {input_text}", reply_to_message_id=message.message_id)

        if status != 'ok':
            error_message = res.get('message', 'Unknown error')
            msg = (
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔹 Status: ❌ Failed\n"
                f"🔹 Account: {obfuscated}\n"
                f"🔹 Reason: {error_message}\n"
                f"🔹 Processed by: @{message.from_user.first_name}\n"
                f"⚡ Speed: {speed} seconds\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💎 Bot by @BotPlays90"
            )
        else:
            stats_col.update_one({"_id": "reset_counter"}, {"$inc": {"count": 1}}, upsert=True)
            msg = (
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔹 Status: ✅ Success\n"
                f"🔹 Account: {obfuscated}\n"
                f"🔹 Processed by: @{message.from_user.first_name}\n"
                f"⚡ Speed: {speed} seconds\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💎 Bot by @BotPlays90"
            )

        bot.send_message(message.chat.id, msg, reply_to_message_id=message.message_id)
        bot.delete_message(chat_id=message.chat.id, message_id=x.message_id)

    except telebot.apihelper.ApiTelegramException as e:
        if "Too Many Requests" in str(e):
            retry_seconds = int(str(e).split("retry after")[1].split()[0])
            bot.send_message(message.chat.id, f"🚫 Rate limit hit. Retrying in {retry_seconds} seconds...")
            time.sleep(retry_seconds + 1)
            process_reset_request(message, input_text)  # Retry
            return
        else:
            bot.send_message(message.chat.id, f"❌ Telegram API error:\n{e}")

    except Exception as e:
        speed = round(time.time() - start_time, 2)
        bot.send_message(
            message.chat.id,
            f"❌ Error processing `{input_text}`\n⚡ Speed: {speed}s\nError: {e}",
            parse_mode="Markdown"
        )

    user_reset_state.pop(user_id, None)

@bot.message_handler(func=lambda m: m.reply_to_message and m.from_user.id in user_reset_state)
def handle_reset_input(m):
    user_id = m.from_user.id
    reset_info = user_reset_state.get(user_id)

    if not reset_info or m.chat.id != reset_info["chat_id"] or m.reply_to_message.message_id != reset_info["prompt_msg_id"]:
        return

    if not is_user_joined(user_id):
        buttons = InlineKeyboardMarkup()
        for channel in FORCE_CHANNELS:
            buttons.add(InlineKeyboardButton(f"📢 Join @{channel}", url=f"https://t.me/{channel}"))
        buttons.add(InlineKeyboardButton("✅ I’ve Joined", callback_data="check_joined"))
        bot.send_message(
            m.chat.id,
            "🚨 You must join all required channels to use this feature.",
            reply_markup=buttons
        )
        return

    inputs = [x.strip() for x in m.text.replace(",", "\n").split("\n") if x.strip()]
    if not inputs:
        return bot.reply_to(m, "❌ Please provide at least one valid username/email.")

    set_pending(user_id, inputs)

    if not get_current_user():
        set_current_user(user_id)
        send_next_batch(m.chat.id, user_id, m.reply_to_message.message_id)
    else:
        enqueue_batch(user_id, m.chat.id, m.reply_to_message.message_id)
        bot.send_message(m.chat.id, "⏳ Please wait, your batch is in queue...")



def send_next_batch(chat_id, user_id, reply_to_msg_id):
    inputs = get_pending(user_id)
    if not inputs:
        bot.send_message(chat_id, "✅ All resets completed.", reply_to_message_id=reply_to_msg_id)
        remove_pending(user_id)
        clear_current_user()
        start_next_queued_batch()
        return

    batch = inputs[:10]
    set_pending(user_id, inputs[10:])

    for input_text in batch:
        try:
            dummy_msg = type('', (), {})()
            dummy_msg.chat = type('', (), {'id': chat_id})
            dummy_msg.from_user = type('', (), {'id': user_id, 'first_name': 'User'})
            dummy_msg.text = f"/resett {input_text}"
            dummy_msg.message_id = reply_to_msg_id
            process_reset_request(dummy_msg, input_text)
            time.sleep(2)
        except Exception as e:
            bot.send_message(chat_id, f"❌ Error on: {input_text}\n{e}")

    if get_pending(user_id):
        btn = InlineKeyboardMarkup()
        btn.add(InlineKeyboardButton("▶ Send Next 10", callback_data=f"nextbatch_{user_id}"))
        bot.send_message(chat_id, "📩 10 resets processed. Click below to continue after 15s.", reply_markup=btn)
    else:
        bot.send_message(chat_id, "✅ All resets processed.")
        remove_pending(user_id)
        clear_current_user()
        start_next_queued_batch()


def start_next_queued_batch():
    next_user = dequeue_batch()
    if next_user:
        user_id, chat_id, msg_id = next_user
        set_current_user(user_id)
        send_next_batch(chat_id, user_id, msg_id)



@bot.callback_query_handler(func=lambda c: c.data.startswith("nextbatch_"))
def handle_next_batch_callback(c):
    target_user_id = int(c.data.split("_")[1])
    if c.from_user.id != target_user_id:
        return bot.answer_callback_query(c.id, "❌ This isn't your session.")
    
    bot.answer_callback_query(c.id, "⏳ Please wait 15 seconds...")
    time.sleep(15)
    send_next_batch(c.message.chat.id, c.from_user.id, c.message.message_id)



@bot.callback_query_handler(func=lambda c: c.data.startswith("nextbatch_"))
def handle_next_batch_callback(c):
    target_user_id = int(c.data.split("_")[1])
    if c.from_user.id != target_user_id:
        return bot.answer_callback_query(c.id, "❌ This isn't your session.")

    bot.answer_callback_query(c.id, "⏳ Please wait 15 seconds...")
    time.sleep(15)
    send_next_batch(c.message.chat.id, c.from_user.id, c.message.message_id)



@bot.callback_query_handler(func=lambda c: c.data.startswith("verify_"))
def verify_callback(c):
    user_id = int(c.data.split("_")[1])
    
    if c.from_user.id != user_id:
        bot.answer_callback_query(c.id, "This verification is not for you.")
        return

        
        # Check if this user had a pending reset request
        if user_id in pending_verification:
            user_data = pending_verification[user_id]
            
            # Edit the verification message
            bot.edit_message_text(
                chat_id=user_data['chat_id'],
                message_id=c.message.message_id,
                text="✅ *Verification Complete!*\n\nYou can now use the /resett command.",
                parse_mode='Markdown'
            )
            
            # If there was input text with the original command, process it now
            if user_data['input_text']:
                # Create a dummy message object to pass to process_reset_request
                dummy_msg = type('', (), {})()
                dummy_msg.from_user = c.from_user
                dummy_msg.chat = type('', (), {'id': user_data['chat_id'], 'type': 'group'})
                dummy_msg.text = f"/reset {user_data['input_text']}"
                dummy_msg.message_id = c.message.message_id

                process_reset_request(dummy_msg, user_data['input_text'])
            
            del pending_verification[user_id]

    else:
        bot.answer_callback_query(c.id, "❌ You haven't joined all required channels!")

        # Send verification prompt again using updated function
        send_verification_prompt(c.message)


keep_alive()

if __name__ == "__main__":
    print("[✓] Bot is Online — Group-only / Multi-user enabled")
    bot.infinity_polling()
