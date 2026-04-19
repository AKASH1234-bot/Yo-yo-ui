import asyncio
import re
import ast
import math
from Script import script
from plugins.fsub import ForceSub
from database.connections_mdb import active_connection, all_connections, delete_connection, if_active, make_active, \
    make_inactive
from info import ADMINS, AUTH_CHANNEL, REQ_CHANNEL_1, REQ_CHANNEL_2, AUTH_USERS, CUSTOM_FILE_CAPTION, AUTH_GROUPS, \
    SPELL_LNK, LOG_CHANNEL
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
from utils import get_size, is_subscribed, temp
from database.users_chats_db import db
from database.ia_filterdb import Media, get_file_details, get_search_results, get_all_search_results
from database.filters_mdb import (
    del_all,
    find_filter,
    get_filters,
)
from utils_lang import detect_languages, detect_query_language, strip_language_from_query
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

BUTTONS = {}
LANG_DATA = {}  # Stores language-grouped files per message: key -> {search, all_files, lang_groups, query_lang}


def build_search_ui(key, req, offset=0):
    """
    Core UI Builder for the Advanced Dual-Filter Search Module.
    Handles intersection filters (Language + Season), dynamic grid buttons, Send All, and Pagination.
    """
    data = LANG_DATA.get(key)
    if not data:
        return None, 0

    active_lang = data.get('active_lang')
    active_season = data.get('active_season')
    active_quality = data.get('active_quality')
    lang_groups = data.get('lang_groups', {})
    all_seasons = data.get('all_seasons', [])
    all_qualities = data.get('all_qualities', [])
    all_files = data.get('all_files', [])
    search = data.get('search', '')

    # ── 1. Apply Intersecting Filters ──
    display_files = all_files.copy()
    
    if active_lang and active_lang in lang_groups:
        display_files = [f for f in display_files if f in lang_groups[active_lang]]
        
    if active_season:
        season_int = int(active_season.replace("S", ""))
        display_files = [f for f in display_files if getattr(f, 'season_num', None) == season_int]

    if active_quality:
        # Match using same regex from utils_lang
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

    total = len(display_files)
    page_files = display_files[offset:offset + 10]
    
    # ── 2. Build Buttons ──
    btn = []

    # SEND ALL Button (Only for Series!)
    if total > 0 and all_seasons:
        btn.append([InlineKeyboardButton("📥 SEND ALL 📥", callback_data=f"sendall_{req}_{key}_{offset}")])

    # Languages Grid
    if lang_groups:
        lang_btns = []
        for lang_label, lang_files in lang_groups.items():
            if lang_label == active_lang:
                lang_btns.append(InlineKeyboardButton(f"✅ {lang_label}", callback_data=f"lang_{key}_ALL"))
            else:
                lang_btns.append(InlineKeyboardButton(f"{lang_label}", callback_data=f"lang_{key}_{lang_label}"))
        for i in range(0, len(lang_btns), 3):
            btn.append(lang_btns[i:i + 3])

    # Seasons Grid
    if all_seasons:
        season_btns = []
        for s_label in all_seasons:
            if s_label == active_season:
                season_btns.append(InlineKeyboardButton(f"✅ {s_label}", callback_data=f"season_{key}_ALL"))
            else:
                season_btns.append(InlineKeyboardButton(f"{s_label}", callback_data=f"season_{key}_{s_label}"))
        for i in range(0, len(season_btns), 4):
            btn.append(season_btns[i:i + 4])
            
    # Quality Grid
    if all_qualities:
        qual_btns = []
        for q_label in all_qualities:
            if q_label == active_quality:
                qual_btns.append(InlineKeyboardButton(f"✅ {q_label}", callback_data=f"qual_{key}_ALL"))
            else:
                qual_btns.append(InlineKeyboardButton(f"{q_label}", callback_data=f"qual_{key}_{q_label}"))
        for i in range(0, len(qual_btns), 3):
            btn.append(qual_btns[i:i + 3])

    # File Buttons
    for file in page_files:
        btn.append([
            InlineKeyboardButton(
                text=f"📂 [{get_size(file.file_size)}] 👉 {file.file_name}",
                callback_data=f'filep#{file.file_id}'
            )
        ])

    # Pagination Grid
    if total > 0:
        n_offset = offset + 10 if offset + 10 < total else 0
        off_set = 0 if 0 < offset <= 10 else (None if offset == 0 else offset - 10)
        
        total_pages = math.ceil(total / 10)
        current_page = math.ceil(offset / 10) + 1

        if n_offset == 0:
            if off_set is not None:
                btn.append([
                    InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"),
                    InlineKeyboardButton(f"📃 {current_page}/{total_pages}", callback_data="pages")
                ])
            else:
                btn.append([InlineKeyboardButton(f"📃 {current_page}/{total_pages}", callback_data="pages")])
        elif off_set is None:
            btn.append([
                InlineKeyboardButton(f"🗓 {current_page}/{total_pages}", callback_data="pages"),
                InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")
            ])
        else:
            btn.append([
                InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"),
                InlineKeyboardButton(f"🗓 {current_page}/{total_pages}", callback_data="pages"),
                InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")
            ])

    return btn, total


@Client.on_message((filters.group | filters.private) & filters.text & filters.incoming)
async def give_filter(client, message):
    k = await manual_filters(client, message)
   

    if k == False:
        await auto_filter(client, message)


@Client.on_callback_query(filters.regex(r"^next_"))
async def next_page(bot, query):
    """Handle pagination strictly passing offset to builder."""
    ident, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer("You cannot interact with this menu.", show_alert=True)
    try:
        offset = int(offset)
    except:
        offset = 0

    btn, total = build_search_ui(key, req, offset=offset)
    if not btn:
        return await query.answer("Session expired! Please search again.", show_alert=True)

    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass
    except FloodWait as e:
        return await query.answer(f"Please wait {e.value} seconds...", show_alert=True)
    await query.answer()


@Client.on_callback_query(filters.regex(r"^lang_"))
async def lang_filter(bot, query):
    """Handle language filter button clicks."""
    _, key, selected_lang = query.data.split("_", 2)
    
    data = LANG_DATA.get(key)
    if not data:
        return await query.answer("Session expired! Please search again.", show_alert=True)

    req = query.from_user.id
    
    # Toggle: if clicking same lang again or "ALL", reset to show all files
    if selected_lang == "ALL" or selected_lang == data.get('active_lang'):
        data['active_lang'] = None
    else:
        data['active_lang'] = selected_lang

    btn, total = build_search_ui(key, req, offset=0)
    if btn:
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        except MessageNotModified:
            pass
        except FloodWait as e:
            return await query.answer(f"Please wait {e.value} seconds...", show_alert=True)
    await query.answer()


@Client.on_callback_query(filters.regex(r"^season_"))
async def season_filter(bot, query):
    """Handle season filter button clicks."""
    _, key, selected_season = query.data.split("_", 2)
    
    data = LANG_DATA.get(key)
    if not data:
        return await query.answer("Session expired! Please search again.", show_alert=True)

    req = query.from_user.id
    
    # Toggle: if clicking same season again or "ALL", reset to show all seasons
    if selected_season == "ALL" or selected_season == data.get('active_season'):
        data['active_season'] = None
    else:
        data['active_season'] = selected_season

    btn, total = build_search_ui(key, req, offset=0)
    if btn:
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        except MessageNotModified:
            pass
        except FloodWait as e:
            return await query.answer(f"Please wait {e.value} seconds...", show_alert=True)
    await query.answer()

@Client.on_callback_query(filters.regex(r"^qual_"))
async def quality_filter(bot, query):
    """Handle quality filter button clicks."""
    _, key, selected_quality = query.data.split("_", 2)
    
    data = LANG_DATA.get(key)
    if not data:
        return await query.answer("Session expired! Please search again.", show_alert=True)

    req = query.from_user.id
    
    # Toggle: if clicking same quality again or "ALL", reset
    if selected_quality == "ALL" or selected_quality == data.get('active_quality'):
        data['active_quality'] = None
    else:
        data['active_quality'] = selected_quality

    btn, total = build_search_ui(key, req, offset=0)
    if btn:
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        except MessageNotModified:
            pass
        except FloodWait as e:
            return await query.answer(f"Please wait {e.value} seconds...", show_alert=True)
    await query.answer()

@Client.on_callback_query(filters.regex(r"^sendall_"))
async def send_all_files(bot, query):
    """
    Handle the SEND ALL button.
    Redirects to PM with Deep-Link to trigger ForceSub join request logic.
    """
    _, req, key, offset = query.data.split("_")
    
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer("You cannot interact with this menu.", show_alert=True)
        
    data = LANG_DATA.get(key)
    if not data:
        return await query.answer("Session expired! Please search again.", show_alert=True)
        
    await query.answer(url=f"https://t.me/{temp.U_NAME}?start=all_batch_{key}_{offset}")

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    if query.data == "close_data":
        await query.message.delete()
    elif query.data == "delallconfirm":
        userid = query.from_user.id
        chat_type = query.message.chat.type

        if chat_type == enums.ChatType.PRIVATE:
            grpid = await active_connection(str(userid))
            if grpid is not None:
                grp_id = grpid
                try:
                    chat = await client.get_chat(grpid)
                    title = chat.title
                except:
                    await query.message.edit_text("Make sure I'm present in your group!!", quote=True)
                    return await query.answer('Done')
            else:
                await query.message.edit_text(
                    "I'm not connected to any groups!\nCheck /connections or connect to any groups",
                    quote=True
                )
                return await query.answer('Done')

        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            title = query.message.chat.title

        else:
            return await query.answer('Done')

        st = await client.get_chat_member(grp_id, userid)
        if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in ADMINS):
            await del_all(query.message, grp_id, title)
        else:
            await query.answer("You need to be Group Owner or an Auth User to do that!", show_alert=True)
    elif query.data == "delallcancel":
        userid = query.from_user.id
        chat_type = query.message.chat.type

        if chat_type == enums.ChatType.PRIVATE:
            await query.message.reply_to_message.delete()
            await query.message.delete()

        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            st = await client.get_chat_member(grp_id, userid)
            if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in ADMINS):
                await query.message.delete()
                try:
                    await query.message.reply_to_message.delete()
                except:
                    pass
            else:
                await query.answer("That's not for you!!", show_alert=True)
    elif "groupcb" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        act = query.data.split(":")[2]
        hr = await client.get_chat(int(group_id))
        title = hr.title
        user_id = query.from_user.id

        if act == "":
            stat = "CONNECT"
            cb = "connectcb"
        else:
            stat = "DISCONNECT"
            cb = "disconnect"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{stat}", callback_data=f"{cb}:{group_id}"),
             InlineKeyboardButton("DELETE", callback_data=f"deletecb:{group_id}")],
            [InlineKeyboardButton("BACK", callback_data="backcb")]
        ])

        await query.message.edit_text(
            f"Group Name : **{title}**\nGroup ID : `{group_id}`",
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return await query.answer('Done')
    elif "connectcb" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        hr = await client.get_chat(int(group_id))

        title = hr.title

        user_id = query.from_user.id

        mkact = await make_active(str(user_id), str(group_id))

        if mkact:
            await query.message.edit_text(
                f"Connected to **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text('Some error occurred!!', parse_mode=enums.ParseMode.MARKDOWN)
        return await query.answer('Done')
    elif "disconnect" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        hr = await client.get_chat(int(group_id))

        title = hr.title
        user_id = query.from_user.id

        mkinact = await make_inactive(str(user_id))

        if mkinact:
            await query.message.edit_text(
                f"Disconnected from **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text(
                f"Some error occurred!!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return await query.answer('Done')
    elif "deletecb" in query.data:
        await query.answer()

        user_id = query.from_user.id
        group_id = query.data.split(":")[1]

        delcon = await delete_connection(str(user_id), str(group_id))

        if delcon:
            await query.message.edit_text(
                "Successfully deleted connection"
            )
        else:
            await query.message.edit_text(
                f"Some error occurred!!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return await query.answer('Done')
    elif query.data == "backcb":
        await query.answer()

        userid = query.from_user.id

        groupids = await all_connections(str(userid))
        if groupids is None:
            await query.message.edit_text(
                "There are no active connections!! Connect to some groups first.",
            )
            return await query.answer('Done')
        buttons = []
        for groupid in groupids:
            try:
                ttl = await client.get_chat(int(groupid))
                title = ttl.title
                active = await if_active(str(userid), str(groupid))
                act = " - ACTIVE" if active else ""
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"{title}{act}", callback_data=f"groupcb:{groupid}:{act}"
                        )
                    ]
                )
            except:
                pass
        if buttons:
            await query.message.edit_text(
                "Your connected group details ;\n\n",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    elif "alertmessage" in query.data:
        grp_id = query.message.chat.id
        i = query.data.split(":")[1]
        keyword = query.data.split(":")[2]
        reply_text, btn, alerts, fileid = await find_filter(grp_id, keyword)
        if alerts is not None:
            alerts = ast.literal_eval(alerts)
            alert = alerts[int(i)]
            alert = alert.replace("\\n", "\n").replace("\\t", "\t")
            await query.answer(alert, show_alert=True)
    if query.data.startswith("file"):
        
        
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('No such file exist.')
        files = files_[0]
        title = files.file_name
        size = get_size(files.file_size)
        f_caption = files.caption
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
            f_caption = f_caption
        if f_caption is None:
            f_caption = f"{files.file_name}"

        try:
            # Always Bot PM mode: redirect to PM
            if AUTH_CHANNEL and not await is_subscribed(client, query):
                await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
                return
            else:
                await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
                return
        except UserIsBlocked:
            await query.answer('Unblock the bot mahn !', show_alert=True)
        except PeerIdInvalid:
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
        except Exception as e:
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
            
    elif query.data.startswith("checksub"):
        if AUTH_CHANNEL and not await is_subscribed(client, query):
            await query.answer("Join Both Channels & Then Click Get File 😒", show_alert=True)
            return
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('No such file exist.')
        files = files_[0]
        title = files.file_name
        size = get_size(files.file_size)
        f_caption = files.caption
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
                f_caption = f_caption
        if f_caption is None:
            f_caption = f"{title}"
        await query.answer()
        await client.send_cached_media(
            chat_id=query.from_user.id,
            file_id=file_id,
            caption=f_caption,
            protect_content=True if ident == 'checksubp' else False
        )
    elif query.data == "pages":
        await query.answer()
    elif query.data == "start":
        buttons = [[
            InlineKeyboardButton('➕ Add Me To Your Groups ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
        ], [
            InlineKeyboardButton('Movie Search Group', url= 'https://t.me/MVM_Links'),
            InlineKeyboardButton('Movie Updates', url='https://t.me/+6Mb-6zj2Gh0xYjhl')
        ], 
        ]
            
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.START_TXT.format(query.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer('Done')
    elif query.data == "help":
        buttons = [[
            InlineKeyboardButton('Manual Filter', callback_data='manuelfilter'),
            InlineKeyboardButton('Auto Filter', callback_data='autofilter')
        ], [
            InlineKeyboardButton('Connection', callback_data='coct'),
            InlineKeyboardButton('Extra Mods', callback_data='extra')
        ], [
            InlineKeyboardButton('🏠 Home', callback_data='start'),
            InlineKeyboardButton('🔮 Status', callback_data='stats')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.HELP_TXT.format(query.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "about":
        buttons = [[
            InlineKeyboardButton('🤖 Updates', url='https://t.me/TeamEvamaria'),
            InlineKeyboardButton('♥️ Source', callback_data='source')
        ], [
            InlineKeyboardButton('🏠 Home', callback_data='start'),
            InlineKeyboardButton('🔐 Close', callback_data='close_data')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ABOUT_TXT.format(temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "source":
        buttons = [[
            InlineKeyboardButton('👩\u200d🦯 Back', callback_data='about')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.SOURCE_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "manuelfilter":
        buttons = [[
            InlineKeyboardButton('👩\u200d🦯 Back', callback_data='help'),
            InlineKeyboardButton('⏹️ Buttons', callback_data='button')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.MANUELFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "button":
        buttons = [[
            InlineKeyboardButton('👩\u200d🦯 Back', callback_data='manuelfilter')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.BUTTON_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "autofilter":
        buttons = [[
            InlineKeyboardButton('👩\u200d🦯 Back', callback_data='help')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.AUTOFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "coct":
        buttons = [[
            InlineKeyboardButton('👩\u200d🦯 Back', callback_data='help')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.CONNECTION_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "extra":
        buttons = [[
            InlineKeyboardButton('👩\u200d🦯 Back', callback_data='help'),
            InlineKeyboardButton('👮\u200d♂️ Admin', callback_data='admin')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.EXTRAMOD_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "admin":
        buttons = [[
            InlineKeyboardButton('👩\u200d🦯 Back', callback_data='extra')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ADMIN_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "stats":
        buttons = [[
            InlineKeyboardButton('👩\u200d🦯 Back', callback_data='help'),
            InlineKeyboardButton('♻️', callback_data='rfrsh')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        total = await Media.count_documents()
        users = await db.total_users_count()
        chats = await db.total_chat_count()
        monsize = await db.get_db_size()
        free = 536870912 - monsize
        monsize = get_size(monsize)
        free = get_size(free)
        await query.message.edit_text(
            text=script.STATUS_TXT.format(total, users, chats, monsize, free),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "rfrsh":
        await query.answer("Fetching MongoDb DataBase")
        buttons = [[
            InlineKeyboardButton('👩\u200d🦯 Back', callback_data='help'),
            InlineKeyboardButton('♻️', callback_data='rfrsh')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        total = await Media.count_documents()
        users = await db.total_users_count()
        chats = await db.total_chat_count()
        monsize = await db.get_db_size()
        free = 536870912 - monsize
        monsize = get_size(monsize)
        free = get_size(free)
        await query.message.edit_text(
            text=script.STATUS_TXT.format(total, users, chats, monsize, free),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    await query.answer('Done')


async def auto_filter(client, msg, spoll=False):
    message = msg
    if message.text.startswith("/"): return  # ignore commands
    if re.findall("((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
        return
    if 2 < len(message.text) < 100:
        search = message.text

        # ── Step 1: Detect language in user's search query ──
        query_lang = detect_query_language(search)
        # Strip language from search so MongoDB finds more results
        clean_search = strip_language_from_query(search) if query_lang else search

        # ── Step 2: Fetch ALL results (deduplicated + sorted by size desc) ──
        all_files = await get_all_search_results(clean_search.lower())
        if not all_files:
            # Static "Not Found" reply with channel join button
            btn = [[
                InlineKeyboardButton("⭕ Join Here ⭕", url=SPELL_LNK)
            ]]
            n = await message.reply_text(
                text=script.NOT_FILE_TXT.format(search),
                reply_markup=InlineKeyboardMarkup(btn)
            )
            await asyncio.sleep(30)
            await n.delete()
            try:
                await message.delete()
            except:
                pass
            return
    else:
        return

    # ── Step 3: Extract features and Store State ──
    from utils_lang import detect_languages, detect_seasons, detect_qualities
    
    lang_groups = detect_languages(all_files)
    all_seasons = detect_seasons(all_files)
    all_qualities = detect_qualities(all_files)
    
    # Determine initial active lang (if user requested it)
    active_lang = query_lang if (query_lang and query_lang in lang_groups) else None

    # Store state for callbacks
    key = f"{message.chat.id}-{message.id}"
    req = message.from_user.id if message.from_user else 0
    
    LANG_DATA[key] = {
        'search': search,
        'all_files': all_files,
        'lang_groups': lang_groups,
        'all_seasons': all_seasons,
        'all_qualities': all_qualities,
        'query_lang': query_lang,
        'active_lang': active_lang,
        'active_season': None,
        'active_quality': None
    }

    # ── Step 4: Build UI via helper ──
    btn, total = build_search_ui(key, req, offset=0)
    if not btn:
        return

    # ── Step 6: Send message ──
    lang_info = f" ({active_lang})" if active_lang else ""
    cap = f"Hey 👋 Buddy 😎 \n \n Here Is The Results For #{search}{lang_info}"
    dll = await message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn))
    await asyncio.sleep(60)
    fll = await dll.edit_text(f"<b>🗑️ Filter Deleted After 1 Min ‼️ \n 🔍Search Again !!</b>")
    # Clean up stored state
    LANG_DATA.pop(key, None)
    await asyncio.sleep(60)
    await fll.delete()
    try:
        await message.delete()
    except:
        pass


async def manual_filters(client, message, text=False):
    group_id = message.chat.id
    name = text or message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    keywords = await get_filters(group_id)
    for keyword in reversed(sorted(keywords, key=len)):
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_filter(group_id, keyword)

            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")

            if btn is not None:
                try:
                    if fileid == "None":
                        if btn == "[]":
                            dm =await client.send_message(
                                group_id, 
                                reply_text, 
                                disable_web_page_preview=True,
                                reply_to_message_id=reply_id)
                            await asyncio.sleep(30)

                            await dm.delete()

                            await message.delete()
                        else:
                            button = eval(btn)
                            dm= await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                reply_to_message_id=reply_id
                            )
                            await asyncio.sleep(30)
                            await dm.delete()
                            await message.delete()
                    elif btn == "[]":
                        dm= await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            reply_to_message_id=reply_id
                        )
                        await asyncio.sleep(30)
                        await dm.delete()
                        await message.delete()
                    else:
                        button = eval(btn)
                        dm= await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id
                        )
                        await asyncio.sleep(30)
                        await dm.delete()
                        await message.delete()
                except Exception as e:
                    logger.exception(e)
                break
    else:
        return False
