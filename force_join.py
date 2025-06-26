from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant

FORCE_JOIN_USERNAME = "hyponet_remastered"  # Your public channel username (no '@')

def check_membership(func):
    async def wrapper(client: Client, message: Message):
        try:
            user = await client.get_chat_member(FORCE_JOIN_USERNAME, message.from_user.id)
            if user.status in ["kicked", "left"]:
                raise UserNotParticipant
        except UserNotParticipant:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 Join @hyponet_remastered", url=f"https://t.me/{FORCE_JOIN_USERNAME}")]
            ])
            return await message.reply(
                "🚫 To use this bot, please join our public channel first.",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Force join check error: {e}")
            return
        return await func(client, message)
    return wrapper
