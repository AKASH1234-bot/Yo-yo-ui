import os
import logging
import random
import asyncio
from Script import script
from pyrogram import Client, filters, enums
from pyrogram.errors import ChatAdminRequired, FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from database.ia_filterdb import Media, get_file_details, unpack_new_file_id
from database.users_chats_db import db
from info import CHANNELS, ADMINS, AUTH_CHANNEL, LOG_CHANNEL, PICS, BATCH_FILE_CAPTION, CUSTOM_FILE_CAPTION, PROTECT_CONTENT, REQ_CHANNEL_1, REQ_CHANNEL_2
from utils import get_size, is_subscribed, temp
from database.connections_mdb import active_connection
from plugins.fsub import ForceSub
from database.redis_cache import flush_by_prefix
import re
import json
import base64
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BATCH_FILES = {}

def start_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('➕ Add Me As Admin 👉 Groups ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')],
        [
            InlineKeyboardButton('🎬 Movie Search...', url='https://t.me/+AngJ8lGmH4wwNWY1'),
            InlineKeyboardButton('📢 Movie Updates', url='https://t.me/ccllinks')
        ],
        [InlineKeyboardButton('📖 How to Use', callback_data='howtouse')]
    ])

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await message.reply(
            script.START_TXT.format(message.from_user.mention if message.from_user else message.chat.title, temp.U_NAME, temp.B_NAME),
            reply_markup=start_buttons()
        )
        await asyncio.sleep(2)
        if not await db.get_chat(message.chat.id):
            total = await client.get_chat_members_count(message.chat.id)
            await client.send_message(LOG_CHANNEL, script.LOG_TEXT_G.format(message.chat.title, message.chat.id, total, "Unknown"))
            await db.add_chat(message.chat.id, message.chat.title)
        return

    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(message.from_user.id, message.from_user.mention))

    if len(message.command) != 2:
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(message.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=start_buttons(),
            parse_mode=enums.ParseMode.HTML
        )
        return

    if len(message.command) == 2 and message.command[1] in ["subscribe", "error", "okay", "help"]:
        if message.command[1] == "subscribe":
            await ForceSub(client, message)
            return
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(message.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=start_buttons(),
            parse_mode=enums.ParseMode.HTML
        )
        return

    kk, file_id = message.command[1].split("_", 1) if "_" in message.command[1] else (False, False)
    pre = ('checksubp' if kk == 'filep' else 'checksub') if kk else False

    status = await ForceSub(client, message, file_id=file_id, mode=pre)
    if not status:
        return

    data = message.command[1]
    try:
        pre, file_id = data.split('_', 1)
    except:
        file_id = data
        pre = ""

    if pre == "all":
        try:
            parts = data.split("_")
            offset = int(parts[-1])
            key = "_".join(parts[2:-1])
        except:
            return await message.reply("Invalid batch link.")

        from plugins.pm_filter import LANG_DATA
        lang_data = LANG_DATA.get(key)
        if not lang_data:
            return await message.reply("Session expired! Please search again in the group.")

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
            return await message.reply("No files found.")

        chat_id = message.from_user.id
        sts = await message.reply(f"Sending {len(page_files)} files to you...")

        async def send_batch():
            from plugins.stats import record_search, record_download
            for f in page_files:
                file_id, file_ref = f.file_id, getattr(f, 'file_ref', None)
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
                    await client.send_cached_media(chat_id=chat_id, file_id=file_id, caption=f_caption, protect_content=True)
                    await record_search(chat_id, f.file_name or "unknown")
                    await record_download(chat_id)
                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                    await client.send_cached_media(chat_id=chat_id, file_id=file_id, caption=f_caption, protect_content=True)
                except Exception as e:
                    logger.error(f"Failed to Send All for {f.file_name}: {e}")
                await asyncio.sleep(0.5)
            await sts.delete()

        asyncio.create_task(send_batch())
        return

    if data.split("-", 1)[0] == "BATCH":
        sts = await message.reply("Please wait")
        file_id = data.split("-", 1)[1]
        msgs = BATCH_FILES.get(file_id)
        if not msgs:
            file = await client.download_media(file_id)
            try:
                with open(file) as file_data:
                    msgs = json.loads(file_data.read())
            except:
                await sts.edit("FAILED")
                return await client.send_message(LOG_CHANNEL, "UNABLE TO OPEN FILE.")
            os.remove(file)
            BATCH_FILES[file_id] = msgs
        for msg in msgs:
            title = msg.get("title")
            size = get_size(int(msg.get("size", 0)))
            f_caption = msg.get("caption", "")
            if BATCH_FILE_CAPTION:
                try:
                    f_caption = BATCH_FILE_CAPTION.format(file_name='' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
                except Exception as e:
                    logger.exception(e)
            if f_caption is None:
                f_caption = f"{title}"
            try:
                await client.send_cached_media(chat_id=message.from_user.id, file_id=msg.get("file_id"), caption=f_caption, protect_content=msg.get('protect', False))
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await client.send_cached_media(chat_id=message.from_user.id, file_id=msg.get("file_id"), caption=f_caption, protect_content=msg.get('protect', False))
            except Exception as e:
                logger.warning(e, exc_info=True)
                continue
            await asyncio.sleep(1)
        await sts.delete()
        return

    elif data.split("-", 1)[0] == "DSTORE":
        sts = await message.reply("Please wait")
        b_string = data.split("-", 1)[1]
        decoded = (base64.urlsafe_b64decode(b_string + "=" * (-len(b_string) % 4))).decode("ascii")
        try:
            f_msg_id, l_msg_id, f_chat_id, protect = decoded.split("_", 3)
        except:
            f_msg_id, l_msg_id, f_chat_id = decoded.split("_", 2)
            protect = "/pbatch" if PROTECT_CONTENT else "batch"
        async for msg in client.iter_messages(int(f_chat_id), int(l_msg_id), int(f_msg_id)):
            if msg.media:
                media = getattr(msg, msg.media.value)
                if BATCH_FILE_CAPTION:
                    try:
                        f_caption = BATCH_FILE_CAPTION.format(file_name=getattr(media, 'file_name', ''), file_size=getattr(media, 'file_size', ''), file_caption=getattr(msg, 'caption', ''))
                    except Exception as e:
                        logger.exception(e)
                        f_caption = getattr(msg, 'caption', '')
                else:
                    file_name = getattr(media, 'file_name', '')
                    f_caption = getattr(msg, 'caption', file_name)
                try:
                    await msg.copy(message.chat.id, caption=f_caption, protect_content=True if protect == "/pbatch" else False)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    await msg.copy(message.chat.id, caption=f_caption, protect_content=True if protect == "/pbatch" else False)
                except Exception as e:
                    logger.exception(e)
                    continue
            elif msg.empty:
                continue
            else:
                try:
                    await msg.copy(message.chat.id, protect_content=True if protect == "/pbatch" else False)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    await msg.copy(message.chat.id, protect_content=True if protect == "/pbatch" else False)
                except Exception as e:
                    logger.exception(e)
                    continue
            await asyncio.sleep(1)
        return await sts.delete()

    files_ = await get_file_details(file_id)
    if not files_:
        pre, file_id = ((base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")).split("_", 1)
        try:
            msg = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file_id,
                protect_content=True if pre == 'filep' else False,
            )
            filetype = msg.media
            file = getattr(msg, filetype.value)
            title = file.file_name
            size = get_size(file.file_size)
            f_caption = f"<code>{title}</code>"
            if CUSTOM_FILE_CAPTION:
                try:
                    f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title, file_size='' if size is None else size, file_caption='')
                except:
                    return
            await msg.edit_caption(f_caption)
            return
        except:
            pass
        return await message.reply('No such file exist.')

    files = files_[0]
    title = files.file_name
    size = get_size(files.file_size)
    f_caption = files.caption
    if CUSTOM_FILE_CAPTION:
        try:
            f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
        except Exception as e:
            logger.exception(e)
    if f_caption is None:
        f_caption = f"{files.file_name}"
    await client.send_cached_media(
        chat_id=message.from_user.id,
        file_id=file_id,
        caption=f_caption,
        protect_content=True if pre == 'filep' else False,
    )
    from plugins.stats import record_search, record_download
    asyncio.create_task(record_search(message.from_user.id, title or "unknown"))
    asyncio.create_task(record_download(message.from_user.id))
    await client.send_message(
        LOG_CHANNEL,
        f"#FILE_SENT\n"
        f"🤖 **Bot:** @{temp.U_NAME} (`{temp.B_NAME}`)\n"
        f"👤 **User:** {message.from_user.mention} [`{message.from_user.id}`]\n"
        f"📄 **File:** `{title}`\n"
        f"📦 **Size:** {size}"
    )


@Client.on_message(filters.command('channel') & filters.user(ADMINS))
async def channel_info(bot, message):
    if isinstance(CHANNELS, (int, str)):
        channels = [CHANNELS]
    elif isinstance(CHANNELS, list):
        channels = CHANNELS
    else:
        raise ValueError("Unexpected type of CHANNELS")
    text = '📑 **Indexed channels/groups**\n'
    for channel in channels:
        chat = await bot.get_chat(channel)
        if chat.username:
            text += '\n@' + chat.username
        else:
            text += '\n' + chat.title or chat.first_name
    text += f'\n\n**Total:** {len(CHANNELS)}'
    if len(text) < 4096:
        await message.reply(text)
    else:
        file = 'Indexed channels.txt'
        with open(file, 'w') as f:
            f.write(text)
        await message.reply_document(file)
        os.remove(file)


@Client.on_message(filters.command('logs') & filters.user(ADMINS))
async def log_file(bot, message):
    try:
        await message.reply_document('TelegramBot.log')
    except Exception as e:
        await message.reply(str(e))


@Client.on_message(filters.command('delete') & filters.user(ADMINS))
async def delete(bot, message):
    reply = message.reply_to_message
    if reply and reply.media:
        msg = await message.reply("Processing...⏳", quote=True)
    else:
        await message.reply('Reply to file with /delete which you want to delete', quote=True)
        return
    for file_type in ("document", "video", "audio"):
        media = getattr(reply, file_type, None)
        if media is not None:
            break
    else:
        await msg.edit('This is not supported file format')
        return
    file_id, file_ref = unpack_new_file_id(media.file_id)
    result = await Media.collection.delete_one({'_id': file_id})
    if result.deleted_count:
        await flush_by_prefix("search:")
        await msg.edit('File is successfully deleted from database')
    else:
        file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
        result = await Media.collection.delete_many({'file_name': file_name, 'file_size': media.file_size, 'mime_type': media.mime_type})
        if result.deleted_count:
            await flush_by_prefix("search:")
            await msg.edit('File is successfully deleted from database')
        else:
            result = await Media.collection.delete_many({'file_name': media.file_name, 'file_size': media.file_size, 'mime_type': media.mime_type})
            if result.deleted_count:
                await flush_by_prefix("search:")
                await msg.edit('File is successfully deleted from database')
            else:
                await msg.edit('File not found in database')


@Client.on_message(filters.command('deleteall') & filters.user(ADMINS))
async def delete_all_index(bot, message):
    await message.reply_text(
        'This will delete all indexed files.\nDo you want to continue??',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="YES", callback_data="autofilter_delete")],
            [InlineKeyboardButton(text="CANCEL", callback_data="close_data")]
        ]),
        quote=True,
    )


@Client.on_callback_query(filters.regex(r'^autofilter_delete'))
async def delete_all_index_confirm(bot, message):
    await Media.collection.drop()
    await flush_by_prefix("search:")
    await message.answer('Done')
    await message.message.edit('Succesfully Deleted All The Indexed Files.')
