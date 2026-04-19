import re
from os import environ

id_pattern = re.compile(r'^.\d+$')
def is_enabled(value, default):
    if value.lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif value.lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default

# ──────────────────────────────────────────────
# Bot information (SET THESE IN HF SECRETS)
# ──────────────────────────────────────────────
SESSION = environ.get('SESSION', 'Media_search')
API_ID = int(environ.get('API_ID', '0'))
API_HASH = environ.get('API_HASH', '')
BOT_TOKEN = environ.get('BOT_TOKEN', '')

# Bot settings
CACHE_TIME = int(environ.get('CACHE_TIME', 300))
USE_CAPTION_FILTER = bool(environ.get('USE_CAPTION_FILTER', False))
PICS = (environ.get('PICS', 'https://graph.org/file/2b620131c3f18e3f431ba.jpg')).split()

# ──────────────────────────────────────────────
# Admins, Channels & Users (SET IN HF SECRETS)
# ──────────────────────────────────────────────
ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in environ.get('ADMINS', '').split()]
CHANNELS = [int(ch) if id_pattern.search(ch) else ch for ch in environ.get('CHANNELS', '').split()]
auth_users = [int(user) if id_pattern.search(user) else user for user in environ.get('AUTH_USERS', '').split()]
AUTH_USERS = (auth_users + ADMINS) if auth_users else []
auth_channel = environ.get('AUTH_CHANNEL')
AUTH_CHANNEL = int(auth_channel) if auth_channel and id_pattern.search(auth_channel) else None
auth_grp = environ.get('AUTH_GROUP')
AUTH_GROUPS = [int(ch) for ch in auth_grp.split()] if auth_grp else None

# Request Channels (SET IN HF SECRETS)
REQ_CHANNEL_1 = environ.get("REQ_CHANNEL_1")
REQ_CHANNEL_1 = int(REQ_CHANNEL_1) if REQ_CHANNEL_1 and id_pattern.search(REQ_CHANNEL_1) else None

REQ_CHANNEL_2 = environ.get("REQ_CHANNEL_2")
REQ_CHANNEL_2 = int(REQ_CHANNEL_2) if REQ_CHANNEL_2 and id_pattern.search(REQ_CHANNEL_2) else None

# ──────────────────────────────────────────────
# Hugging Face Spaces requires PORT 7860
# ──────────────────────────────────────────────
PORT = int(environ.get("PORT", "7860"))
GRP_LNK = environ.get('GRP_LNK', 't.me/MvM_Links')
CHNL_LNK = environ.get('CHNL_LNK', 'https://t.me/MvM_Links')

# ──────────────────────────────────────────────
# MongoDB information (SET IN HF SECRETS)
# ──────────────────────────────────────────────
DATABASE_URI = environ.get('DATABASE_URI', '')
DATABASE_NAME = environ.get('DATABASE_NAME', 'Cluster0')
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'Telegram_Files')
JOIN_REQS_DB = environ.get("JOIN_REQS_DB", DATABASE_URI)

# ──────────────────────────────────────────────
# Redis cache (SET IN HF SECRETS)
# Format: redis://default:PASSWORD@HOST:PORT/0
# ──────────────────────────────────────────────
REDIS_URI = environ.get('REDIS_URI')

# Others
SPELL_LNK = environ.get("SPELL_LNK", "")
LOG_CHANNEL = int(environ.get('LOG_CHANNEL', '0'))
SUPPORT_CHAT = environ.get('SUPPORT_CHAT', 'TeamEvamaria')
CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", "FILE : <code>{file_name}</code> \n \n <b>‼️ Join • \n \n 🔗 @MvM_Links \n \n ⚠️Share File Now⚠️</b>")
BATCH_FILE_CAPTION = environ.get("BATCH_FILE_CAPTION", CUSTOM_FILE_CAPTION)
MAX_LIST_ELM = environ.get("MAX_LIST_ELM", None)
INDEX_REQ_CHANNEL = int(environ.get('INDEX_REQ_CHANNEL', LOG_CHANNEL))
FILE_STORE_CHANNEL = [int(ch) for ch in (environ.get('FILE_STORE_CHANNEL', '')).split()] if environ.get('FILE_STORE_CHANNEL') else []
PROTECT_CONTENT = is_enabled((environ.get('PROTECT_CONTENT', "True")), True)
PUBLIC_FILE_STORE = is_enabled((environ.get('PUBLIC_FILE_STORE', "True")), True)

LOG_STR = "Bot Started Successfully.\n"
