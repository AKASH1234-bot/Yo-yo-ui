# plugins/userstats.py
# Admin command: /users - shows new users today, this week, this month

from pyrogram import Client, filters
from pyrogram.types import Message
from datetime import datetime, timedelta
from database.users_chats_db import db
from info import ADMINS

@Client.on_message(filters.command("users") & filters.user(ADMINS))
async def user_stats(client: Client, message: Message):
    now = datetime.utcnow()
    today     = now.replace(hour=0, minute=0, second=0, microsecond=0)
    this_week = now - timedelta(days=now.weekday())
    this_week = this_week.replace(hour=0, minute=0, second=0, microsecond=0)
    this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    day_count,   day_cursor   = await db.get_users_since(today)
    week_count,  week_cursor  = await db.get_users_since(this_week)
    month_count, month_cursor = await db.get_users_since(this_month)
    total = await db.total_users_count()

    # Build today's user list (max 20)
    day_users = []
    async for u in day_cursor:
        if len(day_users) >= 20:
            break
        name = u.get('name', 'Unknown')
        uid  = u.get('id')
        day_users.append(f"• [{name}](tg://user?id={uid}) `{uid}`")

    day_list = "\n".join(day_users) if day_users else "None"

    text = (
        f"👥 **USER STATISTICS**\n"
        f"──────────────────\n"
        f"📊 **Total Users:** `{total}`\n"
        f"📅 **Today:** `{day_count}`\n"
        f"📆 **This Week:** `{week_count}`\n"
        f"🗓 **This Month:** `{month_count}`\n\n"
        f"**Today's New Users:**\n{day_list}"
    )
    await message.reply(text, quote=True)
