"""
Language detection engine for file search results.
Scans file names and user queries against a comprehensive global dictionary.
Uses word-boundary regex to handle messy filenames (dots, underscores, dashes, brackets).
"""
import re
from collections import OrderedDict

# ─────────────────────────────────────────────────────────────
# Global Language Dictionary
# Key   = Display label shown on button
# Value = tuple of lowercase keyword variations to match
# Order matters — determines button display order
# ─────────────────────────────────────────────────────────────
LANGUAGE_MAP = OrderedDict([
    # ── Indian Languages ──
    ("TAMIL",      ("tam", "tamil")),
    ("TELUGU",     ("tel", "telugu")),
    ("MALAYALAM",  ("mal", "malayalam", "malyalam")),
    ("KANNADA",    ("kan", "kannada")),
    ("HINDI",      ("hin", "hindi")),
    ("MARATHI",    ("mar", "marathi")),
    ("BENGALI",    ("ben", "bengali", "bangla")),
    ("PUNJABI",    ("pun", "punjabi")),
    ("GUJARATI",   ("guj", "gujarati")),
    ("ODIA",       ("odi", "odia", "oriya")),

    # ── International Languages ──
    ("ENGLISH",    ("eng", "english")),
    ("SPANISH",    ("spa", "spanish", "espanol", "español")),
    ("FRENCH",     ("fre", "french", "fra", "français")),
    ("GERMAN",     ("ger", "german", "deu", "deutsch")),
    ("ITALIAN",    ("ita", "italian", "italiano")),
    ("PORTUGUESE", ("por", "portuguese", "português")),
    ("RUSSIAN",    ("rus", "russian")),
    ("JAPANESE",   ("jpn", "japanese", "jap")),
    ("KOREAN",     ("kor", "korean")),
    ("CHINESE",    ("chi", "chinese", "mandarin", "chn")),
    ("ARABIC",     ("ara", "arabic")),
    ("TURKISH",    ("tur", "turkish")),
    ("THAI",       ("thai",)),
    ("VIETNAMESE", ("vie", "vietnamese")),
    ("INDONESIAN", ("ind", "indonesian")),
    ("MALAY",      ("msa", "malay")),
    ("PERSIAN",    ("per", "persian", "farsi")),
    ("DUTCH",      ("dut", "dutch", "nld")),
    ("POLISH",     ("pol", "polish")),
    ("SWEDISH",    ("swe", "swedish")),
    ("NORWEGIAN",  ("nor", "norwegian")),
    ("DANISH",     ("dan", "danish")),
    ("FINNISH",    ("fin", "finnish")),
    ("GREEK",      ("gre", "greek", "ell")),
    ("HEBREW",     ("heb", "hebrew")),
    ("ROMANIAN",   ("rom", "romanian")),
    ("HUNGARIAN",  ("hun", "hungarian")),
    ("CZECH",      ("cze", "czech")),
    ("UKRAINIAN",  ("ukr", "ukrainian")),
    ("URDU",       ("urd", "urdu")),
    ("SINHALA",    ("sin", "sinhala", "sinhalese")),

    # ── Audio Types ──
    ("DUAL",       ("dual", "dual audio", "dualaudio")),
    ("MULTI",      ("multi", "multi audio", "multiaudio")),
])

# ─────────────────────────────────────────────────────────────
# Pre-compiled regex patterns for each language
# Boundary: start/end of string OR any non-alphanumeric/underscore char
# This catches: Movie.TAM.1080p, Movie_tam_hd, Movie-Tam-720p, [TAM] etc.
# ─────────────────────────────────────────────────────────────
_LANG_PATTERNS = {}
for label, keywords in LANGUAGE_MAP.items():
    # Sort keywords longest-first so "dual audio" matches before "dual"
    sorted_kw = sorted(keywords, key=len, reverse=True)
    pattern = r'(?:^|[\s\.\-_\[\]\(\)\+]|(?<=\d))(' + '|'.join(re.escape(k) for k in sorted_kw) + r')(?:$|[\s\.\-_\[\]\(\)\+]|(?=\d))'
    _LANG_PATTERNS[label] = re.compile(pattern, re.IGNORECASE)


def detect_languages(files) -> OrderedDict:
    """
    Scan a list of file objects and return an OrderedDict of detected languages.
    Key   = language label (e.g. "TAMIL")
    Value = list of file objects whose file_name matches that language

    Files that match NO language are NOT included in any group.
    A single file CAN appear under multiple languages (e.g. "Dual" + "Tamil").
    """
    result = OrderedDict()

    for file in files:
        fname = getattr(file, 'file_name', '') or ''
        for label, pattern in _LANG_PATTERNS.items():
            if pattern.search(fname):
                if label not in result:
                    result[label] = []
                result[label].append(file)

    return result


def detect_query_language(query: str) -> str | None:
    """
    Scan the user's search query for an explicit language request.
    Returns the language label (e.g. "TAMIL") if found, else None.
    If multiple languages are found, returns the first match.
    """
    query_lower = query.lower().strip()
    for label, keywords in LANGUAGE_MAP.items():
        for kw in keywords:
            # Check if the keyword exists as a standalone word in the query
            pattern = r'(?:^|[\s])(' + re.escape(kw) + r')(?:$|[\s])'
            if re.search(pattern, query_lower):
                return label
    return None


def strip_language_from_query(query: str) -> str:
    """
    Remove the language keyword from the user's search query so MongoDB
    doesn't use it as a search term (which would miss files).
    e.g. "Leo 2023 tamil" → "Leo 2023"
    """
    query_lower = query.lower().strip()
    for label, keywords in LANGUAGE_MAP.items():
        for kw in sorted(keywords, key=len, reverse=True):
            pattern = r'(?:^|[\s])' + re.escape(kw) + r'(?:$|[\s])'
            if re.search(pattern, query_lower):
                # Remove the keyword and clean up extra spaces
                query = re.sub(r'(?i)(?:^|(?<=\s))' + re.escape(kw) + r'(?:$|(?=\s))', '', query).strip()
                query = re.sub(r'\s+', ' ', query)  # collapse multiple spaces
                return query
    return query


def deduplicate_files(files) -> list:
    """
    Remove exact duplicate files based on (file_name, file_size).
    Keeps the first occurrence.
    """
    seen = set()
    unique = []
    for file in files:
        fname = getattr(file, 'file_name', '') or ''
        fsize = getattr(file, 'file_size', 0) or 0
        key = (fname.lower(), fsize)
        if key not in seen:
            seen.add(key)
            unique.append(file)
    return unique


def extract_season_episode(fname: str):
    """
    Extracts Season and Episode numbers from filenames.
    Returns (season: int | None, episode: int | None)
    """
    fname = fname.lower()
    
    # Matches Season
    s_match = re.search(r'(?:^|[\W_])(?:s|season)\s*0?(\d+)', fname)
    season = int(s_match.group(1)) if s_match else None
    
    # Matches Episode
    e_match = re.search(r'(?:^|[\W_]|(?<=\d))(?:e|ep|episode)\s*0?(\d+)', fname)
    episode = int(e_match.group(1)) if e_match else None

    # Fallback for 01x02 format
    if season is None and episode is None:
        bx_match = re.search(r'(?:^|[\W_])0?(\d+)\s*x\s*0?(\d+)(?:[\W_]|$)', fname)
        if bx_match:
            season = int(bx_match.group(1))
            episode = int(bx_match.group(2))
            
    return season, episode

def detect_seasons(files) -> list:
    """
    Returns a sorted list of unique formatted season strings (e.g., ['S01', 'S02']) 
    present in the given files list.
    """
    seasons = set()
    for file in files:
        if getattr(file, 'season_num', None) is not None:
            seasons.add(f"S{file.season_num:02d}")
    return sorted(list(seasons))

def detect_qualities(files) -> list:
    """
    Returns a sorted list of unique quality strings (e.g., ['4K', '1080P', '720P']) 
    present in the given files list. Sort defaults to highest quality first.
    """
    qualities = set()
    quality_patterns = {
        '4K': r'(?i)\b(?:4k|2160p)\b',
        '1080P': r'(?i)\b1080p\b',
        '720P': r'(?i)\b720p\b',
        '480P': r'(?i)\b480p\b',
        '360P': r'(?i)\b360p\b'
    }
    
    for file in files:
        fname = getattr(file, 'file_name', '') or ''
        for q_label, q_pattern in quality_patterns.items():
            if re.search(q_pattern, fname):
                qualities.add(q_label)
                
    # Sort order: 4K > 1080P > 720P > 480P > 360P
    order = {'4K': 0, '1080P': 1, '720P': 2, '480P': 3, '360P': 4}
    return sorted(list(qualities), key=lambda x: order.get(x, 99))

def sort_by_size_desc(files) -> list:
    """
    Sort files by:
    1. Match Count (descending)
    2. Is Series (descending) -> Pushes series to top if identical match count?
       Actually, skip is_series. Just sort by Match Count.
    3. Season Number (ascending, S01 before S02) -> we use negative for descending sort
    4. Episode Number (ascending, E01 before E02) -> we use negative for descending sort
    5. File Size (descending) -> largest file sizes top
    """
    def get_sort_key(f):
        m_count = getattr(f, 'match_count', 0)
        
        # Season/Episode variables (handle None by converting to 0 for math)
        s_num = getattr(f, 'season_num', None)
        e_num = getattr(f, 'episode_num', None)
        
        # We want Ascending for seasons, but the global sort is reverse=True (Descending).
        # To make S1 appear BEFORE S2 in a Descending sort, S1 must evaluate mathematically HIGHER than S2.
        # So we use negative: -1 is > -2. 
        # For movies (None), they should appear below seasons if everything else matches, so use a very low number like -999.
        s_sort = -s_num if s_num is not None else -9999
        e_sort = -e_num if e_num is not None else -9999
        
        f_size = getattr(f, 'file_size', 0) or 0
        
        # Tuple Order: Match -> Season -> Episode -> Size
        return (m_count, s_sort, e_sort, f_size)

    return sorted(files, key=get_sort_key, reverse=True)
