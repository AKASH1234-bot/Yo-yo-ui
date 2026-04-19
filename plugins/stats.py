import logging, json, asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from database.redis_cache import get_cache, set_cache

logger = logging.getLogger(__name__)

def _sk(u): return f"ustats:{u}"
def _hk(u): return f"uhist:{u}"
TK = "trending"
TTL = 86400 * 30

async def record_search(uid: int, q: str):
    q = q.strip().lower()[:80]
    if len(q) < 2: return
    try:
        raw = await get_cache(_sk(uid))
        s = json.loads(raw) if raw else {"s": 0, "d": 0}
        s["s"] += 1
        await set_cache(_sk(uid), json.dumps(s), ex=TTL)
        raw = await get_cache(_hk(uid))
        h = json.loads(raw) if raw else []
        if q in h: h.remove(q)
        h.insert(0, q)
        await set_cache(_hk(uid), json.dumps(h[:10]), ex=TTL)
        raw = await get_cache(TK)
        t = json.loads(raw) if raw else {}
        t[q] = t.get(q, 0) + 1
        await set_cache(TK, json.dumps(t), ex=86400)
        logger.info(f"[stats] recorded search uid={uid} q={q}")
    except Exception as e:
        logger.warning(f"[stats] record_search error: {e}")

async def record_download(uid: int):
    try:
        raw = await get_cache(_sk(uid))
        s = json.loads(raw) if raw else {"s": 0, "d": 0}
        s["d"] += 1
        await set_cache(_sk(uid), json.dumps(s), ex=TTL)
        logger.info(f"[stats] recorded download uid={uid}")
    except Exception as e:
        logger.warning(f"[stats] record_download error: {e}")

@Client.on_message(filters.command("mystats") & filters.private)
async def mystats_cmd(_, message: Message):
    uid = message.from_user.id
    try:
        raw = await get_cache(_sk(uid))
        logger.info(f"[stats] mystats raw={raw} uid={uid}")
        s = json.loads(raw) if raw else {"s": 0, "d": 0}
    except Exception as e:
        logger.warning(f"[stats] mystats error: {e}")
        s = {"s": 0, "d": 0}
    await message.reply(
        f"📊 <b>YOUR STATS</b>\n"
        f"──────────────────\n"
        f"🔍 Searches : <code>{s.get('s',0)}</code>\n"
        f"📥 Downloads: <code>{s.get('d',0)}</code>",
        quote=True
    )

@Client.on_message(filters.command("history") & filters.private)
async def history_cmd(_, message: Message):
    try:
        raw = await get_cache(_hk(message.from_user.id))
        h = json.loads(raw) if raw else []
    except:
        h = []
    if not h:
        return await message.reply("🕒 No history yet.", quote=True)
    lines = "\n".join(f"{i+1}. <code>{q}</code>" for i, q in enumerate(h))
    await message.reply(f"🕒 <b>LAST {len(h)} SEARCHES</b>\n──────────────────\n{lines}", quote=True)

@Client.on_message(filters.command("trending") & filters.private)
async def trending_cmd(_, message: Message):
    try:
        raw = await get_cache(TK)
        t = json.loads(raw) if raw else {}
    except:
        t = {}
    if not t:
        return await message.reply("📈 No trending data yet.", quote=True)
    top = sorted(t.items(), key=lambda x: x[1], reverse=True)[:10]
    medals = ["🥇","🥈","🥉"] + ["🔹"]*7
    lines = "\n".join(f"{medals[i]} <code>{q}</code> — <b>{c}</b>" for i,(q,c) in enumerate(top))
    await message.reply(f"🔥 <b>TOP {len(top)} TRENDING</b>\n──────────────────\n{lines}", quote=True)

@Client.on_message(filters.command("testredis") & filters.private)
async def test_redis(_, message: Message):
    """Admin debug command to test Redis"""
    uid = message.from_user.id
    try:
        await set_cache(f"test:{uid}", "ok", ex=60)
        val = await get_cache(f"test:{uid}")
        if val == "ok":
            await message.reply("✅ Redis is working correctly!")
        else:
            await message.reply(f"⚠️ Redis set but got: {val}")
    except Exception as e:
        await message.reply(f"❌ Redis error: {e}")
