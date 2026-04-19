from logging import getLogger
from pyrogram import Client, filters, enums
from pyrogram.types import ChatJoinRequest
from pyrogram.handlers import ChatJoinRequestHandler
from database.join_reqs import JoinReqs 
from info import ADMINS, REQ_CHANNEL_1, REQ_CHANNEL_2
from utils import temp
from database.redis_cache import delete_key

db = JoinReqs
logger = getLogger(__name__)

@Client.on_chat_join_request(filters.chat(REQ_CHANNEL_1 if REQ_CHANNEL_1 else "self"))
async def join_reqs_channel_1(client, join_req: ChatJoinRequest):

    if db().isActive():
        user_id = join_req.from_user.id
        first_name = join_req.from_user.first_name
        username = join_req.from_user.username
        date = join_req.date

        await db().add_user(
            user_id=user_id,
            first_name=first_name,
            username=username,
            date=date,
            channel=1
        )

@Client.on_chat_join_request(filters.chat(REQ_CHANNEL_2 if REQ_CHANNEL_2 else "self"))
async def join_reqs_channel_2(client, join_req: ChatJoinRequest):

    if db().isActive():
        user_id = join_req.from_user.id
        first_name = join_req.from_user.first_name
        username = join_req.from_user.username
        date = join_req.date

        await db().add_user(
            user_id=user_id,
            first_name=first_name,
            username=username,
            date=date,
            channel=2
        )

@Client.on_message(filters.command("totalrequests") & filters.private & filters.user((ADMINS.copy() + [1125210189])))
async def total_requests(client, message):

    if db().isActive():
        total_channel_1 = await db().get_all_users_count(channel=1)
        total_channel_2 = await db().get_all_users_count(channel=2)
        await message.reply_text(
            text=f"Total Requests Channel 1: {total_channel_1}\nTotal Requests Channel 2: {total_channel_2}",
            parse_mode=enums.ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

@Client.on_message(filters.command("purgerequests") & filters.private & filters.user(ADMINS))
async def purge_requests(client, message):
    
    if db().isActive():
        await db().delete_all_users(channel=1)
        await db().delete_all_users(channel=2)
        # Clear ALL authorization caches — users must re-verify
        temp.AUTHORIZED_USERS.clear()
        await delete_key("authorized_users")
        await message.reply_text(
            text="Purged All Requests & Cleared All Caches ✅",
            parse_mode=enums.ParseMode.MARKDOWN,
            disable_web_page_preview=True
)
        
