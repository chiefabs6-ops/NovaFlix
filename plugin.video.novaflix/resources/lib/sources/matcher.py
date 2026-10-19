"""Release/file name parsing and episode matching. Pure functions, no Kodi.

Handles the naming styles seen in Torrentio and Nyaa results (fixtures in
tests/fixtures): "[Group] Show - 03 (1080p) [HASH].mkv", "Show S02E05",
"Show S2 - 08", "E3 Title", batches "S01 E01-E14" / "01-12", absolute
numbering, scene-style "...x265-Group", and extras (NCOP/NCED/PV...).
Unknown values stay None; nothing is guessed (DEC-004).
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple

VIDEO_EXTENSIONS = (".mkv", ".mp4", ".avi", ".m4v", ".webm", ".ts", ".mov", ".wmv")

_RESOLUTIONS = [("2160p", r"2160p|\b4k\b|\buhd\b"), ("1080p", r"1080[pi]"), ("720p", r"720p"),
                ("576p", r"576p"), ("480p", r"480p")]
RESOLUTION_ORDER = {"2160p": 4, "1080p": 3, "720p": 2, "576p": 1, "480p": 0}
_CODECS = [("AV1", r"\bav1\b"), ("HEVC", r"hevc|[xh]\.?265"), ("AVC", r"\bavc\b|[xh]\.?264")]
_ENGLISH_DUB = re.compile(r"english[ ._-]?dub|\beng[ ._-]?dub", re.I)
_ANY_DUB = re.compile(r"\[dub\]|\(dub\)|\bdubbed\b|\bdub\b", re.I)
_DUAL = re.compile(r"dual[ ._-]?audio|\bdual\b", re.I)
_ENGLISH = re.compile(r"\benglish\b|\beng\b", re.I)
# Audio languages other than English/Japanese, as release names write them.
_OTHER_LANGUAGE = re.compile(
    r"\b(?:chinese|mandarin|cantonese|spanish|espa[nñ]ol|latino|castellano|cast|portuguese|portugu[eê]s|"
    r"pt[ -]?br|brazilian|french|fran[cç]ais|vf|german|deutsch|italian|italiano|ita|hindi|tamil|telugu|"
    r"russian|rus|arabic|korean|thai|indonesian|polish|turkish|vietnamese|tagalog)\b", re.I)
# Subtitle mentions say nothing about audio: "[SUB PT-BR ENG]", "Eng Sub", "EngSubs", "Multi-Subs".
_SUBTITLE_INFO = re.compile(
    r"\b(?:eng(?:lish)?|multi|soft|matching(?: soft)?)[ ._-]?subs?\b"
    r"|\bsub(?:s|titles?)?\b[ :]*(?:[a-z-]{2,6}[ ,/+&]*)*", re.I)
_EXTRA = re.compile(r"\b(NC ?OP\d*|NC ?ED\d*|OP\d*|ED\d*|PV\d*|CM\d*|Preview|Trailer|Teaser|Menu|Recap|"
                    r"Specials?|SP\d*|OVA|OAD|ONA|Extras?|Bonus|Creditless)\b", re.I)


@dataclass
class Release:
    name: str
    group: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    episode_range: Optional[Tuple[int, int]] = None
    resolution: Optional[str] = None
    codec: Optional[str] = None
    audio: Optional[str] = None   # "dub" (English dub stated) | "dual" (dual audio) | None
    version: Optional[int] = None
    is_batch: bool = False
    is_extra: bool = False


def _strip_extension(name):
    lower = name.lower()
    for ext in VIDEO_EXTENSIONS:
        if lower.endswith(ext):
            return name[: -len(ext)]
    return name


def _group(name):
    m = re.match(r"\s*\[([^\]]+)\]", name)
    if m:
        return m.group(1).strip()
    m = re.search(r"-([A-Za-z0-9]{2,20})\s*$", name)  # scene style: "...x265-Rapta"
    if m and not m.group(1).isdigit():
        return m.group(1)
    return None


def _first(patterns, text):
    for value, pattern in patterns:
        if re.search(pattern, text, re.I):
            return value
    return None


def other_language_only(text):
    """True when the name states a non-English audio language and never English
    ("Mandarin Chinese + Cantonese Dub", "[DUAL JAP PT-BR]")."""
    audio_text = _SUBTITLE_INFO.sub(" ", text)
    return bool(_OTHER_LANGUAGE.search(audio_text)) and not _ENGLISH.search(audio_text)


def audio_of(text):
    """"dub" (English dub stated), "dual" (dual/multi audio) or None (DEC-025)."""
    if _ENGLISH_DUB.search(text):
        return "dub"
    if other_language_only(text):
        return None
    if _ANY_DUB.search(text):
        return "dub"
    if _DUAL.search(text):
        return "dual"
    return None


def parse(name):
    """Parse a release or file name. Path components are allowed; the last one wins."""
    base = _strip_extension(re.split(r"[\\/]", name)[-1]).replace("_", " ")
    rel = Release(name=name, group=_group(base))
    rel.resolution = _first(_RESOLUTIONS, base)
    rel.codec = _first(_CODECS, base)
    rel.audio = audio_of(base)

    # Remove bracketed tags, CRC hashes, years and technical tokens before numbering.
    core = re.sub(r"\[[^\]]*\]|\{[^}]*\}", " ", base)
    core = re.sub(r"\((?:19|20)\d\d\)", " ", core)
    core = re.sub(r"\([^)]*(?:p|bit|audio|sub|dub|bd|web|hevc|x26\d|aac|flac|opus|dual|batch)[^)]*\)", " ", core, flags=re.I)
    core = re.sub(r"\b(?:\d{3,4}p|[xh]\.?26[45]|10[ -]?bits?|8[ -]?bits?|\d\.\d|5\.1|2\.0|aac\d?|ddp?\d?|"
                  r"flac|opus|ac3|eac3|truehd|dts|hdr\d*|av1|hevc|avc|web[ -]?dl|webrip|bdrip|bluray|"
                  r"multi[ -]?subs?|msubs)\b", " ", core, flags=re.I)
    core = re.sub(r"\s+", " ", core).strip()

    m = re.search(r"\bS(\d{1,2})\s?E(\d{1,4})\s?[-~]\s?E?(\d{1,4})\b", core, re.I)
    if m:
        rel.season, rel.episode_range, rel.is_batch = int(m.group(1)), (int(m.group(2)), int(m.group(3))), True
    else:
        m = re.search(r"\bS(\d{1,2})\s?E(\d{1,4})(?:v(\d))?\b", core, re.I)
        if m:
            rel.season, rel.episode = int(m.group(1)), int(m.group(2))
            rel.version = int(m.group(3)) if m.group(3) else None

    season_words = r"\bS(\d{1,2})\b|\bSeason[ .]?(\d{1,2})\b|\b(\d{1,2})(?:st|nd|rd|th) Season\b"
    if rel.season is None:
        m = re.search(season_words, core, re.I)
        if m:
            rel.season = int(next(g for g in m.groups() if g))
            # Drop the season words so "Season 2" is not read as episode 2.
            core = (core[:m.start()] + " " + core[m.end():]).strip()
    if rel.season is None:
        # Season stated only inside brackets: "[Season 2]", "(Batch S02 S2)".
        m = re.search(season_words, " ".join(re.findall(r"[\[(]([^\])]*)[\])]", base)), re.I)
        if m:
            rel.season = int(next(g for g in m.groups() if g))

    if rel.episode is None and rel.episode_range is None:
        m = re.search(r"\s-\s(\d{1,4})\s?[-~]\s?(\d{1,4})\b", core)
        if m and int(m.group(1)) < int(m.group(2)):
            rel.episode_range, rel.is_batch = (int(m.group(1)), int(m.group(2))), True
    if rel.episode is None and rel.episode_range is None:
        m = (re.search(r"\s-\s(\d{1,4})(?:v(\d))?(?=\s|$)", core)
             or re.search(r"\bE[Pp]?\.?\s?(\d{1,4})(?:v(\d))?\b", core)
             or re.search(r"\bEpisode\s(\d{1,4})\b", core, re.I))
        if m:
            rel.episode = int(m.group(1))
            if m.lastindex and m.lastindex >= 2 and m.group(2):
                rel.version = int(m.group(2))
    if rel.episode is None and rel.episode_range is None:
        # Bare trailing number: "Show 03" (Nyaa style). Avoid 4-digit years.
        m = re.search(r"\s(\d{1,3})(?:v(\d))?\s*$", core)
        if m:
            rel.episode = int(m.group(1))

    if rel.episode is None and rel.episode_range is None:
        rel.is_batch = bool(re.search(r"batch|complete|season|\bS\d{1,2}\b", base, re.I))
    rel.is_extra = bool(_EXTRA.search(core)) and rel.episode_range is None
    return rel


def matches(rel, number, absolute=None, tvdb=None):
    """True: this release/file is the episode. False: it is another one.
    None: no episode number found (a "best guess" at most).

    number: episode within the AniList entry (DEC-013); absolute: absolute
    number when known; tvdb: (season, episode) from ani.zip when known.
    """
    if rel.is_extra:
        return False
    wanted = {number} | ({absolute} if absolute else set())
    if rel.episode is not None:
        if rel.season is not None and tvdb:
            if (rel.season, rel.episode) == tuple(tvdb):
                return True
            if rel.season != tvdb[0]:
                # Another season's label can still carry an absolute number ("S01 - 31"),
                # but the same number as ours is that season's own episode.
                return bool(absolute) and absolute != number and rel.episode == absolute
        return rel.episode in wanted
    if rel.episode_range is not None:
        low, high = rel.episode_range
        if rel.season is not None and tvdb and rel.season != tvdb[0]:
            return False
        if tvdb and rel.season is not None:
            return low <= tvdb[1] <= high
        return any(low <= n <= high for n in wanted)
    if rel.season is not None and tvdb and rel.season != tvdb[0]:
        return False  # batch of another season
    return None


def is_video(path):
    return path.lower().endswith(VIDEO_EXTENSIONS)
