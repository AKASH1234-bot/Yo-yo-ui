import logging
from struct import pack
import re
import base64
from pyrogram.file_id import FileId
from pymongo.errors import DuplicateKeyError, BulkWriteError
from umongo import Instance, Document, fields
from motor.motor_asyncio import AsyncIOMotorClient
from marshmallow.exceptions import ValidationError
from info import DATABASE_URI, DATABASE_NAME, COLLECTION_NAME, USE_CAPTION_FILTER

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


client = AsyncIOMotorClient(DATABASE_URI)
db = client[DATABASE_NAME]
instance = Instance.from_db(db)

@instance.register
class Media(Document):
    file_id = fields.StrField(attribute='_id')
    file_ref = fields.StrField(allow_none=True)
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StrField(allow_none=True)
    mime_type = fields.StrField(allow_none=True)
    caption = fields.StrField(allow_none=True)

    class Meta:
        indexes = ('$file_name', )
        collection_name = COLLECTION_NAME


async def save_file(media):
    """Save file in database"""

    # TODO: Find better way to get same file_id for same media to avoid duplicates
    file_id, file_ref = unpack_new_file_id(media.file_id)
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
    try:
        file = Media(
            file_id=file_id,
            file_ref=file_ref,
            file_name=file_name,
            file_size=media.file_size,
            file_type=media.file_type,
            mime_type=media.mime_type,
            caption=media.caption.html if media.caption else None,
        )
    except ValidationError:
        logger.exception('Error occurred while saving file in database')
        return False, 2
    else:
        try:
            await file.commit()
        except DuplicateKeyError:      
            logger.warning(
                f'{getattr(media, "file_name", "NO_FILE")} is already saved in database'
            )

            return False, 0
        else:
            logger.info(f'{getattr(media, "file_name", "NO_FILE")} is saved to database')
            return True, 1

async def bulk_save_files(media_list):
    """
    Save massive batches of files using direct PyMongo bulk inserts for extreme performance logic.
    Bypasses Umongo per-item commit overhead.
    Returns: (total_inserted, total_duplicates, total_errors)
    """
    if not media_list:
        return 0, 0, 0
        
    docs_to_insert = []
    
    for media in media_list:
        try:
            file_id, file_ref = unpack_new_file_id(media.file_id)
            file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
            
            doc = {
                '_id': file_id,
                'file_ref': file_ref,
                'file_name': file_name,
                'file_size': media.file_size,
                'file_type': getattr(media, 'file_type', None),
                'mime_type': getattr(media, 'mime_type', None),
                'caption': media.caption.html if media.caption else None
            }
            docs_to_insert.append(doc)
        except Exception as e:
            logger.exception(f"Error packing file data for {getattr(media, 'file_name', 'NO_FILE')}: {e}")
            
    if not docs_to_insert:
        return 0, 0, len(media_list)
        
    try:
        # direct pymongo insert using the underlying motor collection
        # ordered=False allows MongoDB to process the entire batch and gracefully ignore DuplicateKeyErrors
        res = await db[COLLECTION_NAME].insert_many(docs_to_insert, ordered=False)
        return len(res.inserted_ids), 0, len(media_list) - len(res.inserted_ids)
    except BulkWriteError as e:
        # e.details['writeErrors'] contains the duplicates
        write_errors = e.details.get('writeErrors', [])
        dup_count = len(write_errors)
        inserted_count = e.details.get('nInserted', 0)
        return inserted_count, dup_count, len(media_list) - (inserted_count + dup_count)
    except Exception as e:
        logger.exception("Catastrophic error during bulk insert")
        return 0, 0, len(media_list)

async def get_search_results(query, file_type=None, max_results=10, offset=0, filter=False):
    """For given query return (results, next_offset) using MongoDB $text index for speed"""
    import hashlib
    from database.redis_cache import get_cache, set_cache

    query = query.strip()

    # ── Try Redis cache first ──
    cache_key = f"search:{hashlib.md5(f'{query}|{file_type}|{max_results}|{offset}'.encode()).hexdigest()}"
    cached = await get_cache(cache_key, as_json=True)
    if cached is not None:
        # Wrap dicts in SimpleNamespace so callers can use dot notation (file.file_name)
        from types import SimpleNamespace
        files = [SimpleNamespace(**f) for f in cached['files']]
        return files, cached['next_offset'], cached['total_results']

    # ── MongoDB query ──
    if not query:
        raw_pattern = '.'
        # Fallback to regex for empty query
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
        if USE_CAPTION_FILTER:
            filter_query = {'$or': [{'file_name': regex}, {'caption': regex}]}
        else:
            filter_query = {'file_name': regex}
    else:
        # Use fast MongoDB $text search (leverages the '$file_name' text index)
        filter_query = {'$text': {'$search': query}}

    if file_type:
        filter_query['file_type'] = file_type

    total_results = await Media.count_documents(filter_query)
    next_offset = offset + max_results

    if next_offset > total_results:
        next_offset = ''

    cursor = Media.find(filter_query)
    # Sort by recent (using _id because $text search forbids $natural sort)
    cursor.sort('_id', -1)
    # Slice files according to offset and max results
    cursor.skip(offset).limit(max_results)
    # Get list of files
    files = await cursor.to_list(length=max_results)

    # ── Store in Redis for 10 minutes (600s) ──
    # Serialise umongo documents to plain dicts for JSON storage
    try:
        serialised_files = [f.dump() for f in files]
        await set_cache(cache_key, {
            'files': serialised_files,
            'next_offset': next_offset,
            'total_results': total_results
        }, ex=600)
    except Exception:
        pass  # Cache write failure is non-fatal

    return files, next_offset, total_results




async def get_all_search_results(query, file_type=None, max_results=200):
    """
    Fetch a large batch of results for language analysis, deduplication, and sorting.
    Returns a flat list of file objects (already deduplicated and sorted by size desc).
    Results are cached in Redis for 10 minutes.
    """
    import hashlib
    from database.redis_cache import get_cache, set_cache
    from utils_lang import deduplicate_files, sort_by_size_desc
    from types import SimpleNamespace

    query = query.strip()

    # ── Try Redis cache first ──
    cache_key = f"allsearch:{hashlib.md5(f'{query}|{file_type}|{max_results}'.encode()).hexdigest()}"
    cached = await get_cache(cache_key, as_json=True)
    if cached is not None:
        return [SimpleNamespace(**f) for f in cached]

    # ── MongoDB query ──
    if not query:
        raw_pattern = '.'
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
        if USE_CAPTION_FILTER:
            filter_query = {'$or': [{'file_name': regex}, {'caption': regex}]}
        else:
            filter_query = {'file_name': regex}
            
        cursor = Media.collection.find(filter_query)
        cursor.sort('_id', -1)
    else:
        filter_query = {'$text': {'$search': query}}
        if file_type:
            filter_query['file_type'] = file_type
            
        # Project the MongoDB textScore so we can factor it into our size sorting
        cursor = Media.collection.find(
            filter_query, 
            projection={'score': {'$meta': 'textScore'}}
        )
        cursor.sort([('score', {'$meta': 'textScore'})])

    cursor.limit(max_results)
    files_dicts = await cursor.to_list(length=max_results)

    # Convert raw dicts to mock objects and normalize _id
    files = []
    query_words = query.lower().split() if query else []
    from utils_lang import extract_season_episode
    
    # ── Separate Core Words (Title) from Meta Words ──
    meta_patterns = [
        r'^19\d{2}$', r'^20\d{2}$',  # Years
        r'^s\d+$', r'^e\d+$', r'^season\d*$', r'^episode\d*$',  # Seasons/Episodes
        r'^4k$', r'^2160p$', r'^1080p$', r'^720p$', r'^480p$', r'^360p$',  # Quality
        r'^tamil$', r'^hindi$', r'^telugu$', r'^malayalam$', r'^kannada$', r'^english$' # Languages
    ]
    meta_regex = re.compile('|'.join(meta_patterns), re.IGNORECASE)
    
    core_words = [w for w in query_words if not meta_regex.match(w)]
    meta_words = [w for w in query_words if meta_regex.match(w)]
    
    for f in files_dicts:
        f['file_id'] = str(f.pop('_id', ''))
        fname = f.get('file_name', '').lower()
        
        # Calculate exact word match count to override MongoDB TF-IDF obscure scoring
        core_matches = sum(1 for word in core_words if word in fname)
        meta_matches = sum(1 for word in meta_words if word in fname)
        
        f['match_count'] = core_matches + meta_matches
        f['core_matches'] = core_matches
        
        # Extract season and episode
        season_num, episode_num = extract_season_episode(fname)
        f['season_num'] = season_num
        f['episode_num'] = episode_num
        
        files.append(SimpleNamespace(**f))

    # ── Strict Relevancy Filter ──
    if files:
        # 1. Hard Drop: If there are core words in the query, but the file matched ZERO of them, drop it completely.
        if core_words:
            files = [f for f in files if getattr(f, 'core_matches', 0) > 0]
            
        # 2. Max Match Purge: If the highest matching file matched 2 words, delete all files that only matched 1 word.
        if files:
            max_match = max(getattr(f, 'match_count', 0) for f in files)
            if max_match > 0:
                files = [f for f in files if getattr(f, 'match_count', 0) == max_match]

    # ── Deduplicate and sort ──
    files = deduplicate_files(files)
    files = sort_by_size_desc(files)

    # ── Cache for 10 minutes ──
    try:
        serialised = [f.__dict__ for f in files]
        await set_cache(cache_key, serialised, ex=600)
    except Exception:
        pass

    return files



async def get_file_details(query):
    filter = {'file_id': query}
    cursor = Media.find(filter)
    filedetails = await cursor.to_list(length=1)
    return filedetails


def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0

    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0

            r += bytes([i])

    return base64.urlsafe_b64encode(r).decode().rstrip("=")


def encode_file_ref(file_ref: bytes) -> str:
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")


def unpack_new_file_id(new_file_id):
    """Return file_id, file_ref"""
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    file_ref = encode_file_ref(decoded.file_reference)
    return file_id, file_ref
