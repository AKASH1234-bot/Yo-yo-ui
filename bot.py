import logging
import logging.config
import asyncio

# Get logging configurations
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

# ── Fix for newer Telegram channels with large IDs ──
# Pyrogram v2.0.x rejects channel IDs > 2^31. Telegram has since
# created channels exceeding this limit. This patch must run BEFORE
# any Pyrogram imports that use get_peer_type().
import pyrogram.utils
pyrogram.utils.MIN_CHANNEL_ID = -1009999999999

from pyrogram import Client, __version__
from pyrogram.errors import FloodWait
from pyrogram.raw.all import layer
from database.ia_filterdb import Media
from database.users_chats_db import db
from info import SESSION, API_ID, API_HASH, BOT_TOKEN, LOG_STR, PORT, REQ_CHANNEL_1, REQ_CHANNEL_2
from database.redis_cache import get_cache, set_cache, delete_key
from utils import temp
from typing import Union, Optional, AsyncGenerator
from pyrogram import types
from aiohttp import web
from plugins import web_server

class Bot(Client):

    def __init__(self):
        super().__init__(
            name=SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=50,
            plugins={"root": "plugins"},
            sleep_threshold=5,
        )

    async def start(self):
        b_users, b_chats = await db.get_banned()
        temp.BANNED_USERS = b_users
        temp.BANNED_CHATS = b_chats
        # Auto-retry on FloodWait during login
        while True:
            try:
                await super().start()
                break
            except FloodWait as e:
                logging.warning(f"[Startup] FloodWait: Telegram says wait {e.value} seconds. Waiting...")
                await asyncio.sleep(e.value + 1)
                logging.info("[Startup] Retrying login...")
        await Media.ensure_indexes()

        # ── Detect FSub channel changes & invalidate stale cache ──
        current_channels = f"{REQ_CHANNEL_1}|{REQ_CHANNEL_2}"
        saved_channels = await get_cache("fsub_channels")
        if saved_channels and saved_channels != current_channels:
            logging.warning("[Startup] FSub channels changed! Clearing authorization cache...")
            temp.AUTHORIZED_USERS.clear()
            await delete_key("authorized_users")
            logging.info("[Startup] Authorization cache cleared ✅")
        # Always update the stored channel config
        await set_cache("fsub_channels", current_channels, ex=None)

        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        self.username = '@' + me.username

        # ── Pre-warm Pyrogram peer cache for all channels ──
        # Without this, Pyrogram doesn't recognize channel IDs after restart
        from info import AUTH_CHANNEL, CHANNELS
        channels_to_cache = []
        if AUTH_CHANNEL: channels_to_cache.append(AUTH_CHANNEL)
        if REQ_CHANNEL_1: channels_to_cache.append(REQ_CHANNEL_1)
        if REQ_CHANNEL_2: channels_to_cache.append(REQ_CHANNEL_2)
        if CHANNELS:
            channels_to_cache.extend([ch for ch in CHANNELS if isinstance(ch, int)])
        
        for ch_id in channels_to_cache:
            try:
                chat = await self.get_chat(ch_id)
                logging.info(f"[Startup] Cached peer: {chat.title} ({ch_id})")
            except Exception as e:
                logging.warning(f"[Startup] Failed to cache peer {ch_id}: {type(e).__name__}: {e}")

        # ── Pre-generate invite links at startup ──
        try:
            from plugins.fsub import INVITE_LINK
            import plugins.fsub as fsub_module
            invite_link_1 = None
            invite_link_2 = None
            invite_link_auth = None

            if REQ_CHANNEL_1:
                invite_link_1 = (await self.create_chat_invite_link(chat_id=REQ_CHANNEL_1, creates_join_request=True)).invite_link
                logging.info(f"[Startup] REQ_CHANNEL_1 invite ready: {invite_link_1}")
            if REQ_CHANNEL_2:
                invite_link_2 = (await self.create_chat_invite_link(chat_id=REQ_CHANNEL_2, creates_join_request=True)).invite_link
                logging.info(f"[Startup] REQ_CHANNEL_2 invite ready: {invite_link_2}")
            if AUTH_CHANNEL:
                invite_link_auth = (await self.create_chat_invite_link(chat_id=AUTH_CHANNEL)).invite_link
                logging.info(f"[Startup] AUTH_CHANNEL invite ready: {invite_link_auth}")

            fsub_module.INVITE_LINK = (invite_link_1, invite_link_2, invite_link_auth)
            logging.info("[Startup] All invite links pre-generated ✅")
        except Exception as e:
            logging.warning(f"[Startup] Could not pre-generate invite links: {type(e).__name__}: {e}")

        # Web server for HF Spaces health check (port 7860)
        app = web.AppRunner(await web_server())
        await app.setup()
        bind_address = "0.0.0.0"
        await web.TCPSite(app, bind_address, PORT).start()
        logging.info(f"{me.first_name} with Pyrogram v{__version__} (Layer {layer}) started on {me.username}.")
        logging.info(f"Web server running on port {PORT}")
        logging.info(LOG_STR)

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot stopped. Bye.")
    
    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        """Iterate through a chat sequentially.
        This convenience method does the same as repeatedly calling :meth:`~pyrogram.Client.get_messages` in a loop, thus saving
        you from the hassle of setting up boilerplate code. It is useful for getting the whole chat messages with a
        single call.
        Parameters:
            chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target chat.
                For your personal cloud (Saved Messages) you can simply use "me" or "self".
                For a contact that exists in your Telegram address book you can use his phone number (str).
                
            limit (``int``):
                Identifier of the last message to be returned.
                
            offset (``int``, *optional*):
                Identifier of the first message to be returned.
                Defaults to 0.
        Returns:
            ``Generator``: A generator yielding :obj:`~pyrogram.types.Message` objects.
        Example:
            .. code-block:: python
                for message in app.iter_messages("pyrogram", 1, 15000):
                    print(message.text)
        """
        current = offset
        while True:
            new_diff = min(199, limit - current)
            if new_diff < 0:
                return
            messages = await self.get_messages(chat_id, list(range(current, current+new_diff+1)))
            for message in messages:
                yield message
                current += 1


app = Bot()
app.run()
