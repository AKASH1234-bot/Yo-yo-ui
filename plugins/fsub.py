import logging
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserNotParticipant
from pyrogram.types import ChatJoinRequest, InlineKeyboardMarkup, InlineKeyboardButton, Message
from database.join_reqs import JoinReqs 
from info import AUTH_CHANNEL, JOIN_REQS_DB, REQ_CHANNEL_1, REQ_CHANNEL_2, ADMINS, CUSTOM_FILE_CAPTION, PROTECT_CONTENT, CHNL_LNK, GRP_LNK
from utils import temp, get_size
from database.redis_cache import is_in_set, add_to_set
from database.ia_filterdb import Media, get_file_details, get_search_results

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
LOCK = asyncio.Lock()
INVITE_LINK = None  
ForceSub_TEMP = {}
db = JoinReqs

# ──────────────────────────────────────────────
# STARTUP DIAGNOSTICS — logs channel config
# ──────────────────────────────────────────────
logger.info(f"[FSub Config] AUTH_CHANNEL={AUTH_CHANNEL} | REQ_CHANNEL_1={REQ_CHANNEL_1} | REQ_CHANNEL_2={REQ_CHANNEL_2} | JOIN_REQS_DB={'SET' if JOIN_REQS_DB else 'NOT SET'}")

# Build the join request filter dynamically — only if channels are set
_req_channels = []
if REQ_CHANNEL_1: _req_channels.append(REQ_CHANNEL_1)
if REQ_CHANNEL_2: _req_channels.append(REQ_CHANNEL_2)

if _req_channels:
    @Client.on_chat_join_request(filters.chat(_req_channels))
    async def fetch_requests(bot, event: ChatJoinRequest):
        user_id = event.from_user.id
        first_name = event.from_user.first_name
        username = event.from_user.username
        join_date = event.date

        # Determine the channel ID (1 or 2)
        channel_id = 1 if event.chat.id == REQ_CHANNEL_1 else 2
        logger.info(f"[FSub] Join request from user {user_id} for channel {channel_id}")

        # Add user to the database for the respective channel
        await db().add_user(
            user_id=user_id,
            first_name=first_name,
            username=username,
            date=join_date,
            channel=channel_id
        )
        async with LOCK:
        # Check if the user is added to both channels
            user_in_channel_1 = await db().get_user(user_id, channel=1)
            user_in_channel_2 = await db().get_user(user_id, channel=2)

        # If the user is not added to both channels, exit the function
            if not (user_in_channel_1 and user_in_channel_2):
                logger.info(f"[FSub] User {user_id} not yet in both channels, waiting...")
                return

            # Cache this user as authorized (RAM + Redis)
            temp.AUTHORIZED_USERS.add(user_id)
            await add_to_set("authorized_users", user_id)
            logger.info(f"[FSub] User {user_id} authorized via join requests (both channels)")

            if ForceSub_TEMP.get(event.from_user.id) is None:
                return

            file_id = ForceSub_TEMP.get(event.from_user.id)
            if file_id:
                if file_id.startswith("batch_"):
                    # The user requested SEND ALL batch files
                    parts = file_id.split("_")
                    offset = int(parts[-1])
                    key = "_".join(parts[1:-1])
                    
                    from plugins.pm_filter import LANG_DATA
                    lang_data = LANG_DATA.get(key)
                    if not lang_data:
                        await bot.send_message(event.from_user.id, "Session expired! Please search again in the group.")
                        ForceSub_TEMP[event.from_user.id] = None
                        return
                    
                    # Re-apply filters
                    import re
                    active_lang = lang_data.get('active_lang')
                    active_season = lang_data.get('active_season')
                    active_quality = lang_data.get('active_quality')
                    lang_groups = lang_data.get('lang_groups', {})
                    all_files = lang_data.get('all_files', [])
                    
                    display_files = all_files.copy()
                    if active_lang and active_lang in lang_groups:
                        display_files = [f for f in display_files if f in lang_groups[active_lang]]
                    if active_season:
                        season_int = int(active_season.replace("S", ""))
                        display_files = [f for f in display_files if getattr(f, 'season_num', None) == season_int]
                    if active_quality:
                        quality_patterns = {
                            '4K': r'(?i)\b(?:4k|2160p)\b',
                            '1080P': r'(?i)\b1080p\b',
                            '720P': r'(?i)\b720p\b',
                            '480P': r'(?i)\b480p\b',
                            '360P': r'(?i)\b360p\b'
                        }
                        q_pattern = quality_patterns.get(active_quality)
                        if q_pattern:
                            display_files = [f for f in display_files if re.search(q_pattern, getattr(f, 'file_name', '') or '')]
                        
                    page_files = display_files[offset:offset + 10]
                    if not page_files:
                        ForceSub_TEMP[event.from_user.id] = None
                        return await bot.send_message(event.from_user.id, "No files found.")
                        
                    chat_id = event.from_user.id
                    sts = await bot.send_message(chat_id, f"Authentication complete! Sending {len(page_files)} files to you...")
                    
                    async def send_batch():
                        for f in page_files:
                            fid = f.file_id
                            f_caption = getattr(f, 'caption', '') or ''
                            if CUSTOM_FILE_CAPTION:
                                try:
                                    title = f.file_name
                                    size = get_size(f.file_size) if hasattr(f, 'file_size') else ''
                                    f_caption = CUSTOM_FILE_CAPTION.format(
                                        file_name='' if title is None else title,
                                        file_size='' if size is None else size,
                                        file_caption='' if not f_caption else f_caption
                                    )
                                except Exception as e:
                                    logger.error(f"Failed to format caption: {e}")
                                    f_caption = f"{f.file_name}\n\n{CUSTOM_FILE_CAPTION}"
                            if not f_caption:
                                f_caption = f"{f.file_name}"
                            try:
                                await bot.send_cached_media(chat_id=chat_id, file_id=fid, caption=f_caption, protect_content=True)
                            except FloodWait as e:
                                await asyncio.sleep(e.value + 1)
                                await bot.send_cached_media(chat_id=chat_id, file_id=fid, caption=f_caption, protect_content=True)
                            except Exception as e:
                                logger.error(f"Failed to Send All for {f.file_name}: {e}")
                            await asyncio.sleep(0.5)
                        await sts.delete()
                        
                    asyncio.create_task(send_batch())
                    ForceSub_TEMP[event.from_user.id] = None
                    return

                # Normal individual file handling
                files_ = await get_file_details(file_id)
                if not files_:
                    return await bot.send_message(
                        chat_id=event.from_user.id,
                        text="No such file exists."
                    )
                files = files_[0]
                title = files.file_name
                size = get_size(files.file_size)
                f_caption = files.caption

                if CUSTOM_FILE_CAPTION:
                    try:
                        f_caption = CUSTOM_FILE_CAPTION.format(
                            file_name='' if title is None else title,
                            file_size='' if size is None else size,
                            file_caption='' if f_caption is None else f_caption
                        )
                    except Exception as e:
                        logger.exception(e)
                f_caption = f_caption or f"{files.file_name}"

                await bot.send_cached_media(
                    chat_id=event.from_user.id,
                    file_id=file_id,
                    caption=f_caption,
                    protect_content=True
                )
                ForceSub_TEMP[event.from_user.id] = None
else:
    logger.warning("[FSub] REQ_CHANNEL_1 and REQ_CHANNEL_2 are both None — join request handler DISABLED")



async def ForceSub(bot: Client, event: Message, file_id: str = None, mode="checksub"):
    global INVITE_LINK
    auth = ADMINS.copy() + [1125210189]
    
    logger.info(f"[FSub] ForceSub called for user {event.from_user.id if event.from_user else 'Unknown'} | file_id={file_id}")
    logger.info(f"[FSub] Channel config: AUTH_CHANNEL={AUTH_CHANNEL}, REQ_1={REQ_CHANNEL_1}, REQ_2={REQ_CHANNEL_2}")
    
    if event.from_user.id in auth:
        logger.info(f"[FSub] User {event.from_user.id} is admin, bypassing")
        return True

    if not AUTH_CHANNEL and not REQ_CHANNEL_1 and not REQ_CHANNEL_2:
        logger.info("[FSub] No channels configured, bypassing ForceSub")
        return True

    # Check RAM cache first — instant return
    if event.from_user.id in temp.AUTHORIZED_USERS:
        logger.info(f"[FSub] User {event.from_user.id} found in RAM cache, instant pass")
        return True

    # Check Redis cache — survives HF Spaces restarts
    if await is_in_set("authorized_users", event.from_user.id):
        temp.AUTHORIZED_USERS.add(event.from_user.id)  # Backfill RAM cache
        logger.info(f"[FSub] User {event.from_user.id} found in Redis cache, instant pass")
        return True

    is_cb = False
    if not hasattr(event, "chat"):
        event.message.from_user = event.from_user
        event = event.message
        is_cb = True

    # ──────────────────────────────────────────────
    # Step 1: Generate invite links (only once)
    # ──────────────────────────────────────────────
    try:
        if INVITE_LINK is None:
            logger.info(f"[FSub] Generating invite links...")
            invite_link_1 = None
            invite_link_2 = None
            invite_link_auth = None
            
            if REQ_CHANNEL_1:
                logger.info(f"[FSub] Creating invite for REQ_CHANNEL_1={REQ_CHANNEL_1}")
                invite_link_1 = (await bot.create_chat_invite_link(chat_id=REQ_CHANNEL_1, creates_join_request=True)).invite_link
                logger.info(f"[FSub] REQ_CHANNEL_1 invite: {invite_link_1}")
            
            if REQ_CHANNEL_2:
                logger.info(f"[FSub] Creating invite for REQ_CHANNEL_2={REQ_CHANNEL_2}")
                invite_link_2 = (await bot.create_chat_invite_link(chat_id=REQ_CHANNEL_2, creates_join_request=True)).invite_link
                logger.info(f"[FSub] REQ_CHANNEL_2 invite: {invite_link_2}")
            
            if AUTH_CHANNEL:
                logger.info(f"[FSub] Creating invite for AUTH_CHANNEL={AUTH_CHANNEL}")
                invite_link_auth = (await bot.create_chat_invite_link(chat_id=AUTH_CHANNEL)).invite_link
                logger.info(f"[FSub] AUTH_CHANNEL invite: {invite_link_auth}")
            
            INVITE_LINK = (invite_link_1, invite_link_2, invite_link_auth)
            logger.info(f"[FSub] All invite links created successfully: {INVITE_LINK}")
        else:
            invite_link_1, invite_link_2, invite_link_auth = INVITE_LINK
            logger.info(f"[FSub] Using cached invite links")
    except FloodWait as e:
        logger.warning(f"[FSub] FloodWait {e.value}s while creating invite links")
        await asyncio.sleep(e.value)
        fix_ = await ForceSub(bot, event, file_id)
        return fix_

    except Exception as err:
        logger.error(f"[FSub] FAILED to create invite links! Error type: {type(err).__name__}, Error: {err}", exc_info=True)
        await event.reply(
            text=f"Failed To Create Invite Link 🤦\n\nError: `{type(err).__name__}: {err}`\n\nReport 👉 @Maeve_324",
            parse_mode=enums.ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        return False

    # ──────────────────────────────────────────────
    # Step 2: Check DB + API in PARALLEL for speed
    # ──────────────────────────────────────────────
    use_db = REQ_CHANNEL_1 and REQ_CHANNEL_2 and JOIN_REQS_DB and db().isActive()

    async def _check_db(user_id):
        """Check join_reqs database"""
        if not use_db:
            return False
        try:
            logger.info(f"[FSub] Checking join_reqs DB for user {user_id}")
            ch1, ch2 = await asyncio.gather(
                db().get_user(user_id, channel=1),
                db().get_user(user_id, channel=2)
            )
            logger.info(f"[FSub] DB results: ch1={ch1 is not None}, ch2={ch2 is not None}")
            if ch1 and ch2 and ch1["user_id"] == user_id and ch2["user_id"] == user_id:
                return True
        except Exception as e:
            logger.error(f"[FSub] DB check failed: {type(e).__name__}: {e}")
        return False

    async def _check_api(bot, user_id):
        """Check Telegram API membership"""
        channels_to_check = []
        if REQ_CHANNEL_1: channels_to_check.append(REQ_CHANNEL_1)
        if REQ_CHANNEL_2: channels_to_check.append(REQ_CHANNEL_2)
        if not channels_to_check and AUTH_CHANNEL: channels_to_check.append(AUTH_CHANNEL)
        
        logger.info(f"[FSub] Checking membership via API for channels: {channels_to_check}")
        try:
            for channel in channels_to_check:
                user_status = await bot.get_chat_member(chat_id=channel, user_id=user_id)
                logger.info(f"[FSub] User {user_id} status in {channel}: {user_status.status}")
                if user_status.status not in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
                    return False
            return True
        except UserNotParticipant:
            return False
        except Exception as e:
            logger.error(f"[FSub] API check error: {type(e).__name__}: {e}")
            return False

    # Run DB and API checks simultaneously
    try:
        db_ok, api_ok = await asyncio.gather(
            _check_db(event.from_user.id),
            _check_api(bot, event.from_user.id)
        )
        
        if db_ok or api_ok:
            temp.AUTHORIZED_USERS.add(event.from_user.id)
            await add_to_set("authorized_users", event.from_user.id)
            logger.info(f"[FSub] User {event.from_user.id} verified (db={db_ok}, api={api_ok}), cached in RAM+Redis")
            return True
        
        # Not a member of required channels
        raise UserNotParticipant("Not a member")

    except UserNotParticipant:
        logger.info(f"[FSub] User {event.from_user.id} is NOT a member, showing join buttons")
        text = "**Join Our Channels Below 👇 You will get your file 👍**"
        buttons = []
        if invite_link_1:
            buttons.append([InlineKeyboardButton("1️⃣ First Click Here To Join", url=invite_link_1)])
        if invite_link_2:
            buttons.append([InlineKeyboardButton("2️⃣ Second Click Here To Join", url=invite_link_2)])
        if not invite_link_1 and not invite_link_2 and invite_link_auth:
            buttons.append([InlineKeyboardButton("✅ Click Here To Join", url=invite_link_auth)])

        logger.info(f"[FSub] Buttons generated: {len(buttons)} buttons")

        if file_id:
            ForceSub_TEMP[event.from_user.id] = file_id

        if not is_cb:
            await event.reply(
                text=text,
                quote=True,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.MARKDOWN,
            )
        return False

    except FloodWait as e:
        logger.warning(f"[FSub] FloodWait {e.value}s during membership check")
        await asyncio.sleep(e.value)
        fix_ = await ForceSub(bot, event, file_id)
        return fix_

    except Exception as err:
        logger.error(f"[FSub] Unexpected error: {type(err).__name__}: {err}", exc_info=True)
        await event.reply(
            text="Something went Wrong.",
            parse_mode=enums.ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        return False

def set_global_invite(url: str):
    global INVITE_LINK
    INVITE_LINK = url
