import telebot, requests, time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask 
from threading import Thread 
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message


BOT_TOKEN = "7915253544:AAHR6QqNFjShqr5cfLDQvBRkF5oAnNa0n8U"

FORCE_CHANNELS = ["join_hyponet", "codexverse"]  # Channel usernames without @


GROUP_LINK = 'https://t.me/hyporeset'
BOT_LINK = "https://t.me/insta_reset_robot"  # Replace with your bot's link

ADMIN_ID = 6897739611  # your Telegram user ID

from pymongo import MongoClient

MONGO_URI = "mongodb+srv://botplays90:botplays90@botplays.ycka9.mongodb.net/?retryWrites=true&w=majority&appName=botplays"
client = MongoClient(MONGO_URI)
db = client["reset_bot"]
users_col = db["users"]
stats_col = db["stats"]




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
    text = "👥 Registered Users:\n\n"
    for u in users:
        text += f"- {u['name']} (`{u['_id']}`)\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return

    if not message.reply_to_message:
        bot.reply_to(message, "✏️ Please reply to the message you want to broadcast.")
        return

    users = users_col.find()
    sent = 0
    for user in users:
        try:
            bot.copy_message(chat_id=user['_id'],
                             from_chat_id=message.chat.id,
                             message_id=message.reply_to_message.message_id)
            sent += 1
        except Exception as e:
            print(f"Failed to send to {user['_id']}: {e}")
            continue

    bot.send_message(message.chat.id, f"✅ Broadcast sent to {sent} users.")

@bot.message_handler(commands=['resetcount'])
def reset_count(message):
    if message.from_user.id != ADMIN_ID:
        return
    data = stats_col.find_one({"_id": "reset_counter"})
    count = data["count"] if data else 0
    bot.send_message(message.chat.id, f"✅ Total successful reset links sent: *{count}*", parse_mode='Markdown')



@bot.message_handler(commands=['start', 'resett'])
@check_membership
def handle_commands(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    first_name = message.from_user.first_name

    if not users_col.find_one({"_id": user_id}):
                users_col.insert_one({"_id": user_id, "name": first_name})

    if message.chat.type == "private":
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton(" ⛔️ resetGc", url=GROUP_LINK),
            InlineKeyboardButton("👨‍💻 Developer", url=f"https://t.me/{deveop}")
        )
        markup.add(
            InlineKeyboardButton("[+] Add Me to Group", url=f"https://t.me/{bot.get_me().username}?startgroup=true")
        )
        bot.send_message(
            message.chat.id,
            f'❇️ Heyy {name}\n🆔id={user_id}\n\n'
            "🚫 This bot works only in groups!\n\n"
            "👉 Add me to your group to use the reset feature.\n"
            "👉 Then use /resett in your group",
            reply_markup=markup
        )
        return




    # Handle both /reset and /reset <input>
    if message.text.startswith('/resett'):
        # Check if input is provided with command
        if len(message.text.split()) > 1:
            # Process immediately if input is provided
            process_reset_request(message, ' '.join(message.text.split()[1:]))
        else:
            # Ask for input if not provided
            msg = bot.reply_to(message, "📩 Reply To This Message With Your username/email you want to reset:")
            user_reset_state[user_id] = {
     "chat_id": message.chat.id,
     "prompt_msg_id": msg.message_id}

    else:
        bot.reply_to(message, "✅ You're verified! Use /resett <username/email> to start.")

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
            # If the status is not 'ok', get the error message (if available)
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
            # Count successful reset
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

    except Exception as e:
        speed = round(time.time() - start_time, 2)
        msg = (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"❌ Error processing request\n"
            f"🔹 Attempted: {input_text}\n"
            f"⚡ Speed: {speed} seconds\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💎 Bot by @BotPlays90"
        )

    bot.send_message(message.chat.id, msg, reply_to_message_id=message.message_id)
    bot.delete_message(chat_id=message.chat.id, message_id=x.message_id)
    
    user_reset_state.pop(user_id, None)

@bot.message_handler(func=lambda m: m.reply_to_message and m.from_user.id in user_reset_state)
def handle_reset_input(m):
    user_id = m.from_user.id
    reset_info = user_reset_state.get(user_id)

    # Only allow if user replied to the bot's prompt
    if (
        not reset_info or 
        m.chat.id != reset_info["chat_id"] or 
        m.reply_to_message.message_id != reset_info["prompt_msg_id"] or 
        m.reply_to_message.from_user.id != bot.get_me().id  # ensure reply is to the bot
    ):
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

    process_reset_request(m, m.text.strip())



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