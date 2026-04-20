class script(object):

    START_TXT = """𝙷𝙴𝙻𝙻𝙾 {},

𝙼𝚈 𝙽𝙰𝙼𝙴 𝙸𝚂 <a href=https://t.me/{}>{}</a>, 𝙸 𝙲𝙰𝙽 𝙿𝚁𝙾𝚅𝙸𝙳𝙴 𝙼𝙾𝚅𝙸𝙴𝚂, 𝙹𝚄𝚂𝚃 𝙰𝙳𝙳 𝙼𝙴 𝚃𝙾 𝚈𝙾𝚄𝚁 𝙶𝚁𝙾𝚄𝙿 𝙰𝙽𝙳 𝙴𝙽𝙹𝙾𝚈 😍"""

    HELP_TXT = """𝙷𝙴𝚈 {}

𝙷𝙴𝚁𝙴 𝙸𝚂 𝚃𝙷𝙴 𝙷𝙴𝙻𝙿 𝙵𝙾𝚁 𝙼𝚈 𝙲𝙾𝙼𝙼𝙰𝙽𝙳𝚂."""

    ABOUT_TXT = """✯ 𝙼𝚈 𝙽𝙰𝙼𝙴: {}

✯ 𝙲𝚁𝙴𝙰𝚃𝙾𝚁: <a href=https://t.me/TeamEvamaria>Team Eva Maria</a>

✯ 𝙻𝙸𝙱𝚁𝙰𝚁𝚈: 𝙿𝚈𝚁𝙾𝙶𝚁𝙰𝙼

✯ 𝙻𝙰𝙽𝙶𝚄𝙰𝙶𝙴: 𝙿𝚈𝚃𝙷𝙾𝙽 𝟹

✯ 𝙳𝙰𝚃𝙰 𝙱𝙰𝚂𝙴: 𝙼𝙾𝙽𝙶𝙾 𝙳𝙱

✯ 𝙱𝙾𝚃 𝚂𝙴𝚁𝚅𝙴𝚁: 𝙷𝙴𝚁𝙾𝙺𝚄

✯ 𝙱𝚄𝙸𝙻𝙳 𝚂𝚃𝙰𝚃𝚄𝚂: v2.0.0 [ 𝙾𝙿𝚃𝙸𝙼𝙸𝚉𝙴𝙳 ]"""

    SOURCE_TXT = """<b>NOTE:</b>

- Eva Maria is a open source project.

- Source - https://github.com/EvamariaTG/EvaMaria

<b>DEVS:</b>

- <a href=https://t.me/TeamEvamaria>Team Eva Maria</a>"""

    MANUELFILTER_TXT = """Help: <b>Filters</b>

- Filter is the feature were users can set automated replies for a particular keyword and EvaMaria will respond whenever a keyword is found the message

<b>NOTE:</b>

1. eva maria should have admin privillage.

2. only admins can add filters in a chat.

3. alert buttons have a limit of 64 characters.

<b>Commands and Usage:</b>

• /filter - <code>add a filter in chat</code>

• /filters - <code>list all the filters of a chat</code>

• /del - <code>delete a specific filter in chat</code>

• /delall - <code>delete the whole filters in a chat (chat owner only)</code>"""

    BUTTON_TXT = """Help: <b>Buttons</b>

- Eva Maria Supports both url and alert inline buttons.

<b>NOTE:</b>

1. Telegram will not allows you to send buttons without any content, so content is mandatory.

2. Eva Maria supports buttons with any telegram media type.

3. Buttons should be properly parsed as markdown format

<b>URL buttons:</b>

<code>[Button Text](buttonurl:https://t.me/EvaMariaBot)</code>

<b>Alert buttons:</b>

<code>[Button Text](buttonalert:This is an alert message)</code>"""

    AUTOFILTER_TXT = """Help: <b>Auto Filter</b>

<b>NOTE:</b>

1. Make me the admin of your channel if it's private.

2. make sure that your channel does not contains camrips, porn and fake files.

3. Forward the last message to me with quotes.

I'll add all the files in that channel to my db."""

    CONNECTION_TXT = """Help: <b>Connections</b>

- Used to connect bot to PM for managing filters

- it helps to avoid spamming in groups.

<b>NOTE:</b>

1. Only admins can add a connection.

2. Send <code>/connect</code> for connecting me to ur PM

<b>Commands and Usage:</b>

• /connect - <code>connect a particular chat to your PM</code>

• /disconnect - <code>disconnect from a chat</code>

• /connections - <code>list all your connections</code>"""

    EXTRAMOD_TXT = """Help: <b>Extra Modules</b>

<b>NOTE:</b>

these are the extra features of Eva Maria

<b>Commands and Usage:</b>

• /id - <code>get id of a specified user.</code>

• /info - <code>get information about a user.</code>"""

    ADMIN_TXT = """Help: <b>Admin mods</b>

<b>NOTE:</b>

This module only works for my admins

<b>Commands and Usage:</b>

• /logs - <code>to get the rescent errors</code>

• /stats - <code>to get status of files in db.</code>

• /delete - <code>to delete a specific file from db.</code>

• /users - <code>to get list of my users and ids.</code>

• /chats - <code>to get list of the my chats and ids </code>

• /leave - <code>to leave from a chat.</code>

• /disable - <code>do disable a chat.</code>

• /ban - <code>to ban a user.</code>

• /unban - <code>to unban a user.</code>

• /channel - <code>to get list of total connected channels</code>

• /broadcast - <code>to broadcast a message to all users</code>"""

    STATUS_TXT = """★ 𝚃𝙾𝚃𝙰𝙻 𝙵𝙸𝙻𝙴𝚂: <code>{}</code>

★ 𝚃𝙾𝚃𝙰𝙻 𝚄𝚂𝙴𝚁𝚂: <code>{}</code>

★ 𝚃𝙾𝚃𝙰𝙻 𝙲𝙷𝙰𝚃𝚂: <code>{}</code>

★ 𝚄𝚂𝙴𝙳 𝚂𝚃𝙾𝚁𝙰𝙶𝙴: <code>{}</code> 𝙼𝚒𝙱

★ 𝙵𝚁𝙴𝙴 𝚂𝚃𝙾𝚁𝙰𝙶𝙴: <code>{}</code> 𝙼𝚒𝙱"""

    LOG_TEXT_G = """#NewGroup

Group = {}(<code>{}</code>)

Total Members = <code>{}</code>

Added By - {}

"""

    LOG_TEXT_P = """#NewUser

🤖 Bot: @{}

ID - <code>{}</code>

Name - {}

"""

    NO_RESULT_TXT = """#NoResult

★ Group Name: {}

★ Group ID: <code>{}</code>

★ Name: {}

★ Message: {}"""

    NOT_FILE_TXT = """<b>sᴏʀʀʏ ɴᴏ ꜰɪʟᴇs ᴡᴇʀᴇ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ {} 😕

ᴄʜᴇᴄᴋ ʏᴏᴜʀ sᴘᴇʟʟɪɴɢ ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ 😃

ᴍᴏᴠɪᴇ ʀᴇǫᴜᴇꜱᴛ ꜰᴏʀᴍᴀᴛ 👇

ᴇxᴀᴍᴘʟᴇ : Uncharted or Uncharted 2022 or Uncharted En

ꜱᴇʀɪᴇꜱ ʀᴇǫᴜᴇꜱᴛ ꜰᴏʀᴍᴀᴛ 👇

ᴇxᴀᴍᴘʟᴇ : Loki S01 or Loki S01E04 or Lucifer S03E24

🚯 ᴅᴏɴᴛ ᴜꜱᴇ ➠ ':(!,./)</b>"""

    HOW_TO_USE_TXT = """🎬 <b>Cinema Club™ Bot — Features Guide</b>

━━━━━━━━━━━━━━━━━━━━━
🔍 <b>SEARCH MOVIES</b>
━━━━━━━━━━━━━━━━━━━━━
• Type any movie name in the group
• Bot shows all files instantly
• Use Language buttons to filter
• Use Quality buttons (480p/720p/1080p)
• Click any file → sent to your PM

━━━━━━━━━━━━━━━━━━━━━
📺 <b>SERIES SEARCH</b>
━━━━━━━━━━━━━━━━━━━━━
• Type: <code>Loki S01E01</code>
• Click SERIES tab to filter series only
• Season buttons appear automatically

━━━━━━━━━━━━━━━━━━━━━
🌐 <b>LANGUAGE FILTERS</b>
━━━━━━━━━━━━━━━━━━━━━
Malayalam | Tamil | Hindi | English
Telugu | Kannada | Multi Audio | Dual Audio

━━━━━━━━━━━━━━━━━━━━━
⚡ <b>SPECIAL FEATURES</b>
━━━━━━━━━━━━━━━━━━━━━
• Send All To PM — get all results at once
• INFO tab — movie info &amp; details
• MOVIE tab — movies only
• SERIES tab — series only

━━━━━━━━━━━━━━━━━━━━━
📊 <b>YOUR STATS</b>
━━━━━━━━━━━━━━━━━━━━━
• /mystats — your search &amp; download stats
• /history — your last 10 searches
• /trending — top searched movies

━━━━━━━━━━━━━━━━━━━━━
💡 <b>TIPS</b>
━━━━━━━━━━━━━━━━━━━━━
• Use short movie names for best results
• Don't use: ':(|,./
• Files auto-delete after 5 minutes in group
• Files in group auto-delete after 5 minutes"""
