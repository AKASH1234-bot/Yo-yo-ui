# plugins/userstats.py
from pyrogram import Client, filters
from datetime import datetime, timedelta, timezone
from database.users_chats_db import db
from database.join_reqs import JoinReqs
from database.redis_cache import get_cache, set_cache
from info import ADMINS
import json

CACHE_KEY = "userstats"
CACHE_TTL = 300  # 5 minutes

@Client.on_message(filters.command("users") & filters.user(ADMINS))
async def user_stats(client, message):
    sts = await message.reply("⏳ Fetching stats...")

    # Try cache first
    cached = await get_cache(CACHE_KEY)
    if cached:
        return await sts.edit(cached)

    now = datetime.now(timezone.utc)
    today      = now.replace(hour=0, minute=0, second=0, microsecond=0)
    this_week  = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    try:
        total       = await db.col.count_documents({})
        day_count   = await db.col.count_documents({'joined_date': {'$gte': today}})
        week_count  = await db.col.count_documents({'joined_date': {'$gte': this_week}})
        month_count = await db.col.count_documents({'joined_date': {'$gte': this_month}})
    except:
        total = day_count = week_count = month_count = "?"

    jr = JoinReqs()
    try:
        req1 = await jr.get_all_users_count(channel=1) if jr.isActive() else "N/A"
        req2 = await jr.get_all_users_count(channel=2) if jr.isActive() else "N/A"
    except:
        req1 = req2 = "N/A"

    lines = []
    try:
        async for u in db.col.find({'joined_date': {'$gte': today}}).sort('joined_date', -1).limit(10):
            name = u.get('name', 'Unknown')
            uid  = u.get('id', '')
            lines.append(f"• [{name}](tg://user?id={uid}) `{uid}`")
    except:
        pass

    day_list = "\n".join(lines) if lines else "_None yet_"

    text = (
        f"👥 **USER STATISTICS**\n"
        f"──────────────────\n"
        f"📊 **Total:** `{total}`\n"
        f"📅 **Today:** `{day_count}`\n"
        f"📆 **This Week:** `{week_count}`\n"
        f"🗓 **This Month:** `{month_count}`\n\n"
        f"📨 **Join Requests**\n"
        f"Channel 1: `{req1}`\n"
        f"Channel 2: `{req2}`\n\n"
        f"**Today's New Users:**\n{day_list}\n\n"
        f"_⚡ Cached for 5 mins_"
    )

    await set_cache(CACHE_KEY, text, ex=CACHE_TTL)
    await sts.edit(text)
