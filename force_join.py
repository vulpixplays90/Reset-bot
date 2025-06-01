from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant, ChatAdminRequired, ChatWriteForbidden

# Replace with your channel username or ID
FORCE_JOIN_LINK = "https://t.me/+haA_76jVxq5mNGQ1"
FORCE_JOIN_CHANNEL_ID = -1002658036915  # Replace with your private channel's ID



def check_membership(func):
    async def wrapper(client: Client, message: Message):
        try:
            user = await client.get_chat_member(FORCE_JOIN_CHANNEL_ID, message.from_user.id)
            if user.status in ["kicked", "left"]:
                raise UserNotParticipant
        except UserNotParticipant:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 Join Channel", url=FORCE_JOIN_LINK)]
            ])
            return await message.reply(
                "🚫 You must join our private channel to use this bot.",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Force join check error: {e}")
            return await message.reply("❗ An error occurred. Please try again later.")
        return await func(client, message)
    return wrapper

