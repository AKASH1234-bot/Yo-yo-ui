# plugins/stats.py
# Drop this file into plugins/ — no edits needed anywhere else.
# Hooks into pm_filter.py's auto_filter and commands.py's send_cached_media via monkey-patching.

import logging
import json
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from database.redis_cache import get_cache, set_cache

logger = logging.getLogger(__name__)

# ── Redis key helpers ──────────────────────────────────────────────────────────
def _stats_key(uid):   return f"ustats:{uid}"
def _history_key(uid): return f"uhist:{uid}"
TRENDING_KEY = "trending"

MAX_HISTORY  = 10
TTL_STATS    = 86400 * 30   # 30 days
TTL_HISTORY  = 86400 * 30
TTL_TRENDING = 86400         # reset leaderboard daily

# ── Internal helpers (imported by pm_filter & commands monkey-patch) ──────────

async def _record_search(user_id: int, query: str):
    query = query.strip().lower()[:80]
    if not query or len(query) < 2:
        return
    try:
        # stats
        raw = await get_cache(_stats_key(user_id))
        s = json.loads(raw) if raw else {"s": 0, "d": 0}
        s["s"] += 1
        await set_cache(_stats_key(user_id), json.dumps(s), ex=TTL_STATS)
        # history
        raw = await get_cache(_history_key(user_id))
        h = json.loads(raw) if raw else []
        if query in h: h.remove(query)
        h.insert(0, query)
        await set_cache(_history_key(user_id), json.dumps(h[:MAX_HISTORY]), ex=TTL_HISTORY)
        # trending
        raw = await get_cache(TRENDING_KEY)
        t = json.loads(raw) if raw else {}
        t[query] = t.get(query, 0) + 1
        await set_cache(TRENDING_KEY, json.dumps(t), ex=TTL_TRENDING)
    except Exception as e:
        logger.warning(f"[stats] record_search error: {e}")


async def _record_download(user_id: int):
    try:
        raw = await get_cache(_stats_key(user_id))
        s = json.loads(raw) if raw else {"s": 0, "d": 0}
        s["d"] += 1
        await set_cache(_stats_key(user_id), json.dumps(s), ex=TTL_STATS)
    except Exception as e:
        logger.warning(f"[stats] record_download error: {e}")


# ── Monkey-patch pm_filter.auto_filter to record searches ────────────────────
# We wrap the function AFTER the module is loaded by Pyrogram's plugin system.

import plugins.pm_filter as _pm

_orig_auto_filter = _pm.auto_filter

async def _patched_auto_filter(client, msg, spoll=False):
    # record search before handing off
    if msg and msg.from_user and msg.text:
        text = msg.text.strip()
        if 2 < len(text) < 100 and not text.startswith("/"):
            asyncio.create_task(_record_search(msg.from_user.id, text))
    return await _orig_auto_filter(client, msg, spoll)

_pm.auto_filter = _patched_auto_filter

# ── Monkey-patch commands.py to record downloads ─────────────────────────────
import plugins.commands as _cmd
import pyrogram

_orig_send_cached = pyrogram.Client.send_cached_media

async def _patched_send_cached(self, chat_id, file_id, **kwargs):
    result = await _orig_send_cached(self, chat_id, file_id, **kwargs)
    # only count when sending TO a user (int uid), not to groups
    try:
        if isinstance(chat_id, int) and chat_id > 0:
            asyncio.create_task(_record_download(chat_id))
    except Exception:
        pass
    return result

pyrogram.Client.send_cached_media = _patched_send_cached


# ── /mystats command ──────────────────────────────────────────────────────────
@Client.on_message(filters.command("mystats") & filters.private)
async def mystats_cmd(client: Client, message: Message):
    uid = message.from_user.id
    try:
        raw = await get_cache(_stats_key(uid))
        s = json.loads(raw) if raw else {"s": 0, "d": 0}
    except Exception:
        s = {"s": 0, "d": 0}

    text = (
        "📊 <b>YOUR STATS</b>\n"
        "──────────────────\n"
        f"🔍 <b>Total Searches :</b> <code>{s.get('s', 0)}</code>\n"
        f"📥 <b>Total Downloads:</b> <code>{s.get('d', 0)}</code>"
    )
    await message.reply(text, quote=True)


# ── /history command ──────────────────────────────────────────────────────────
@Client.on_message(filters.command("history") & filters.private)
async def history_cmd(client: Client, message: Message):
    uid = message.from_user.id
    try:
        raw = await get_cache(_history_key(uid))
        h = json.loads(raw) if raw else []
    except Exception:
        h = []

    if not h:
        return await message.reply("🕒 No search history yet.", quote=True)

    lines = "\n".join(f"{i+1}. <code>{q}</code>" for i, q in enumerate(h))
    text = f"🕒 <b>YOUR LAST {len(h)} SEARCHES</b>\n──────────────────\n{lines}"
    await message.reply(text, quote=True)


# ── /trending command ─────────────────────────────────────────────────────────
@Client.on_message(filters.command("trending") & filters.private)
async def trending_cmd(client: Client, message: Message):
    try:
        raw = await get_cache(TRENDING_KEY)
        t = json.loads(raw) if raw else {}
    except Exception:
        t = {}

    if not t:
        return await message.reply("📈 No trending data yet.", quote=True)

    top = sorted(t.items(), key=lambda x: x[1], reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    lines = "\n".join(f"{medals[i]} <code>{q}</code> — <b>{cnt}</b>" for i, (q, cnt) in enumerate(top))
    text = f"🔥 <b>TOP {len(top)} TRENDING MOVIES</b>\n──────────────────\n{lines}"
    await message.reply(text, quote=True)
