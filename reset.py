import telebot, requests, time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
REQUIRED_CHANNELS = ['@rayygrp', '@ALEXBOTPY']
GROUP_LINK = "https://t.me/RAYYGRP"

bot = telebot.TeleBot(BOT_TOKEN)
user_reset_state = {}

def is_user_member(user_id):
    for channel in REQUIRED_CHANNELS:
        try:
            member = bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except:
            return False
    return True

def send_verification_prompt(chat_id, user_id):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Join Rayy Group", url="https://t.me/rayygrp"),
        InlineKeyboardButton("Join AlexBotPY", url="https://t.me/ALEXBOTPY")
    )
    markup.add(InlineKeyboardButton("✅ Verify", callback_data=f"verify_{user_id}"))
    bot.send_message(
        chat_id,
        f"<b><a href='tg://user?id={user_id}'>You</a></b> must join both channels to use this bot.",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.message_handler(commands=['start', 'reset'])
def handle_commands(message):
    user_id = message.from_user.id

    if message.chat.type == "private":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Here Is Mine", url=GROUP_LINK))
        bot.send_message(
            message.chat.id,
            "𝗔𝗹𝗲𝘅 𝗕𝗼𝘁:\n❌ This bot only works in group chats.\n\n➕ Add me to your group to use me there!",
            reply_markup=markup
        )
        return

    if not is_user_member(user_id):
        send_verification_prompt(message.chat.id, user_id)
        return

    if message.text.startswith('/reset'):
        user_reset_state[user_id] = message.chat.id
        bot.reply_to(message, "𝗣𝗹𝗲𝗮𝘀𝗲 𝗿𝗲𝗽𝗹𝘆 𝘄𝗶𝘁𝗵 𝘆𝗼𝘂𝗿 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲 / 𝗘𝗺𝗮𝗶𝗹 𝗳𝗼𝗿 𝗿𝗲𝘀𝗲𝘁:")
    else:
        bot.reply_to(message, "✅ You're verified. Use /reset to start.")

@bot.message_handler(func=lambda m: m.from_user.id in user_reset_state)
def handle_reset_input(m):
    if m.chat.id != user_reset_state[m.from_user.id]:
        return

    user_id = m.from_user.id
    input_text = m.text.strip()
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

        msg = (
            f"🔰 <b>Status</b>: {'✅ Success' if status == 'ok' else '❌ Failed'}\n"
            f"🔰 <b>By</b>: {m.from_user.first_name}\n"
            f"🔰 <b>Email</b>: {obfuscated.replace('<', '&lt;').replace('>', '&gt;')}\n"
            f"⚡ <b>Speed</b>: {speed} sec\n"
            f"🔰 <b>DEV</b>: @AL3X_G0D"
        )

    except:
        speed = round(time.time() - start_time, 2)
        msg = (
            f"🔰 <b>Status</b>: ❌ Failed\n"
            f"🔰 <b>By</b>: {m.from_user.first_name}\n"
            f"⚡ <b>Speed</b>: {speed} sec\n"
            f"🔰 <b>DEV</b>: @AL3X_G0D"
        )

    bot.send_message(m.chat.id, msg, parse_mode="HTML")
    user_reset_state.pop(user_id, None)

@bot.callback_query_handler(func=lambda c: c.data.startswith("verify_"))
def verify_callback(c):
    user_id = int(c.data.split("_")[1])
    if c.from_user.id != user_id:
        bot.answer_callback_query(c.id, "This verification is not for you.")
        return

    if is_user_member(user_id):
        bot.send_message(c.message.chat.id, f"✅ You're verified, {c.from_user.first_name}!")
    else:
        send_verification_prompt(c.message.chat.id, user_id)

if __name__ == "__main__":
    print("[✓] Bot is Online — Group-only / Multi-user enabled")
    bot.infinity_polling()
