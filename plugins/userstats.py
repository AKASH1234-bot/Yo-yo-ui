from pyrogram import Client, filters
from datetime import datetime, timedelta, timezone
from database.users_chats_db import db
from database.join_reqs import JoinReqs
from database.redis_cache import get_cache, set_cache
from info import ADMINS

@Client.on_message(filters.command("users") & filters.user(ADMINS))
async def user_stats(client, message):
    sts = await message.reply("⏳ Fetching stats...")
    cached = await get_cache("userstats")
    if cached:
        return await sts.edit(cached)
    now = datetime.now(timezone.utc)
    today      = now.replace(hour=0, minute=0, second=0, microsecond=0)
    this_week  = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        total       = await db.col.count_documents({}, maxTimeMS=5000)
        day_count   = await db.col.count_documents({'joined_date': {'$gte': today}}, maxTimeMS=5000)
        week_count  = await db.col.count_documents({'joined_date': {'$gte': this_week}}, maxTimeMS=5000)
        month_count = await db.col.count_documents({'joined_date': {'$gte': this_month}}, maxTimeMS=5000)
    except Exception as e:
        total = day_count = week_count = month_count = "?"
    jr = JoinReqs()
    try:
        req1 = await jr.get_all_users_count(channel=1) if jr.isActive() else "N/A"
        req2 = await jr.get_all_users_count(channel=2) if jr.isActive() else "N/A"
    except:
        req1 = req2 = "N/A"
    lines = []
    try:
        async for u in db.col.find({'joined_date': {'$gte': today}}).sort('joined_date', -1).limit(10).max_time_ms(5000):
            lines.append(f"• [{u.get('name','Unknown')}](tg://user?id={u.get('id','')}) `{u.get('id','')}`")
    except:
        pass
    text = (
        f"👥 **USER STATISTICS**\n──────────────────\n"
        f"📊 **Total:** `{total}`\n📅 **Today:** `{day_count}`\n"
        f"📆 **This Week:** `{week_count}`\n🗓 **This Month:** `{month_count}`\n\n"
        f"📨 **Join Requests**\nChannel 1: `{req1}`\nChannel 2: `{req2}`\n\n"
        f"**Today's New Users:**\n" + ("\n".join(lines) if lines else "_None yet_") +
        "\n\n_⚡ Cached for 5 mins_"
    )
    await set_cache("userstats", text, ex=300)
    await sts.edit(text)
