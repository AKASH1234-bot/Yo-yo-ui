# plugins/userstats.py
from pyrogram import Client, filters
from pyrogram.types import Message
from datetime import datetime, timedelta, timezone
from database.users_chats_db import db
from info import ADMINS

@Client.on_message(filters.command("users") & filters.user(ADMINS))
async def user_stats(client: Client, message: Message):
    now = datetime.now(timezone.utc)

    today      = now.replace(hour=0, minute=0, second=0, microsecond=0)
    this_week  = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total      = await db.total_users_count()

    # Fetch all users with joined_date in each period
    async def get_users(since):
        result = []
        async for u in db.col.find({'joined_date': {'$gte': since}}).sort('joined_date', -1):
            result.append(u)
        return result

    day_users   = await get_users(today)
    week_users  = await get_users(this_week)
    month_users = await get_users(this_month)

    # Today's user list (max 20)
    lines = []
    for u in day_users[:20]:
        name = u.get('name', 'Unknown')
        uid  = u.get('id', '')
        lines.append(f"• [{name}](tg://user?id={uid}) `{uid}`")

    day_list = "\n".join(lines) if lines else "_None yet_"

    text = (
        f"👥 **USER STATISTICS**\n"
        f"──────────────────\n"
        f"📊 **Total Users:** `{total}`\n"
        f"📅 **Today:** `{len(day_users)}`\n"
        f"📆 **This Week:** `{len(week_users)}`\n"
        f"🗓 **This Month:** `{len(month_users)}`\n\n"
        f"**Today's New Users:**\n{day_list}"
    )
    await message.reply(text, quote=True)
