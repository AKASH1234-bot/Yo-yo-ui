"""
Async Redis cache layer for the bot.
Gracefully degrades — if REDIS_URI is not set or Redis is unreachable,
every function silently returns None/False so the bot falls back to
hitting MongoDB directly, exactly like before.
"""
import logging
import json
import redis.asyncio as redis
from info import REDIS_URI

logger = logging.getLogger(__name__)

# ── Create connection pool (shared across the whole process) ──
_pool = None
if REDIS_URI:
    try:
        _pool = redis.from_url(REDIS_URI, decode_responses=True)
        logger.info("Redis connection pool created.")
    except Exception as e:
        logger.warning(f"Redis init failed (bot will work without cache): {e}")


# ──────────── Key/Value helpers ────────────

async def set_cache(key: str, value, ex: int = 300):
    """Store a value in Redis with expiry (seconds). Pass ex=None for no expiry."""
    if not _pool:
        return False
    try:
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        if ex and ex > 0:
            await _pool.set(key, value, ex=ex)
        else:
            await _pool.set(key, value)
        return True
    except Exception as e:
        logger.error(f"Redis SET error: {e}")
        return False


async def get_cache(key: str, as_json: bool = False):
    """Retrieve a value from Redis. Returns None on miss or error."""
    if not _pool:
        return None
    try:
        val = await _pool.get(key)
        if val is not None and as_json:
            return json.loads(val)
        return val
    except Exception as e:
        logger.error(f"Redis GET error: {e}")
        return None


# ──────────── Set helpers (for user-ID collections) ────────────

async def add_to_set(key: str, *values):
    """Add one or more members to a Redis set."""
    if not _pool:
        return False
    try:
        await _pool.sadd(key, *values)
        return True
    except Exception as e:
        logger.error(f"Redis SADD error: {e}")
        return False


async def is_in_set(key: str, value) -> bool:
    """Check membership in a Redis set. Returns False on error."""
    if not _pool:
        return False
    try:
        return await _pool.sismember(key, str(value))
    except Exception as e:
        logger.error(f"Redis SISMEMBER error: {e}")
        return False


async def remove_from_set(key: str, *values):
    """Remove one or more members from a Redis set."""
    if not _pool:
        return False
    try:
        await _pool.srem(key, *values)
        return True
    except Exception as e:
        logger.error(f"Redis SREM error: {e}")
        return False


# ──────────── Invalidation helpers ────────────

async def delete_key(key: str):
    """Delete a single key from Redis."""
    if not _pool:
        return False
    try:
        await _pool.delete(key)
        return True
    except Exception as e:
        logger.error(f"Redis DELETE error: {e}")
        return False


async def flush_by_prefix(prefix: str):
    """Delete all keys matching a prefix (e.g. 'search:*').
    Uses SCAN to avoid blocking Redis on large key sets."""
    if not _pool:
        return False
    try:
        cursor = 0
        while True:
            cursor, keys = await _pool.scan(cursor=cursor, match=f"{prefix}*", count=100)
            if keys:
                await _pool.delete(*keys)
            if cursor == 0:
                break
        return True
    except Exception as e:
        logger.error(f"Redis FLUSH prefix error: {e}")
        return False

