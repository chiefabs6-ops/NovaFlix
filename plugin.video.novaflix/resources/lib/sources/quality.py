"""Release-title quality: resolution, source, HDR, codecs, audio and cinema-recording tags.
Pure functions, no Kodi.

A release name says what the uploader claims, not what the file is: every value
here is "the name says so", never a measurement. Unknown or conflicting values
stay None and are shown as absent (DEC-004). Matching works on whole tags only:
the name is lower-cased and separators (. _ - [ ] ( ) : and spaces) become one
space, so "WEB-DL", "web.dl" and "WEB DL" are the same and "TS" never matches
inside "DTS" or "Bits".

To support a new tag, add a row to the matching table below. Ranking weights
live in WEIGHTS; the source list reads them, so no UI code changes.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from resources.lib.sources import matcher

# A tag is a run of letters/digits; "+" may end a tag ("HDR10+", "DD+").
_B, _E = r"(?<![a-z0-9])", r"(?![a-z0-9])"


def _tag(pattern):
    return re.compile(_B + "(?:" + pattern + ")" + _E)


# -- matching tables (first match wins within a table) -----------------------------

# Cinema recordings: filmed or line-recorded in a cinema, or a print of a cinema copy.
CAM_TAGS = [
    ("CAM", _tag(r"(?:hd|hq|new )?cam(?: ?rip)?")),
    ("TS", _tag(r"(?:hd ?)?ts(?: ?rip)?|(?:hd ?)?tele ?sync")),
    ("TC", _tag(r"hd ?tc|tele ?cine")),
    ("PDVD", _tag(r"pre ?dvd(?: ?rip)?|pdvd|(?:hq|hd) ?pre(?: ?rip)?")),
]
# "TS" after these is a container or stream name, never a telesync.
_TS_CONTEXT = re.compile(_B + r"(?:mpeg|m2|transport) ts" + _E)
# Fakes and adverts dressed up as the film: betting-site names, "watch ... free" pages.
SPAM_TAGS = [
    ("betting", _tag(r"(?:1 ?x ?bet|4 ?ra ?bet|mel ?bet|most ?bet|line ?bet|22 ?bet|bet ?winner|pari ?match)"
                     r"(?: ?rip)?")),  # "4rabetrip"
    ("watch free", re.compile(_B + r"(?:watch(?: [a-z0-9]+)* free|free (?:hd|full) (?:movies?|online))" + _E)),
]
# Years a release name states; "1920x1080" is a size, not a year.
_YEARS = re.compile(_B + r"(19[2-9][0-9]|20[0-4][0-9])" + _E + r"(?! ?x ?[0-9])")
# Subtitles burned into the picture. Not a cinema recording, often on early releases.
HARDSUB_TAGS = [
    ("KORSUB", _tag(r"kor ?subs?")),
    ("HC", _tag(r"hc|hard ?subs?|hard ?coded(?: subs?)?")),
]

# Explicit pixel heights beat loose words ("4K Remastered 1080p" is 1080p).
_EXACT_RESOLUTIONS = [
    ("2160p", _tag(r"2160[pi]|3840 ?x ?2160|4320p")),
    ("1080p", _tag(r"1080[pi]|1920 ?x ?1080")),
    ("720p", _tag(r"720p|1280 ?x ?720")),
    ("576p", _tag(r"576[pi]")),
    ("480p", _tag(r"480[pi]")),
    ("360p", _tag(r"360p|240p")),
]
_LOOSE_RESOLUTIONS = [
    ("2160p", _tag(r"4k|uhd|ultra ?hd")),
    ("1080p", _tag(r"fhd|full ?hd")),
    # "HD" alone, but not "DTS-HD", "HD MA" or "HD CAM" style tags.
    ("720p", re.compile(r"(?<!dts )(?<!true )(?<!full )(?<!ultra )" + _B + r"hd" + _E + r"(?! (?:ma|hra|cam|ts|tc|rip)" + _E + ")")),
    ("SD", _tag(r"sd")),
]

SOURCES = [
    ("REMUX", _tag(r"(?:bd|uhd ?bd|blu ?ray)? ?remux")),
    ("BluRay", _tag(r"blu ?ray|uhd ?bd|bd ?(?:25|50|66|100)|bdmv|complete bluray")),
    ("BDRip", _tag(r"bd ?rip|br ?rip|bd")),
    ("WEB-DL", _tag(r"web ?dl|web ?dlrip")),
    ("WEBRip", _tag(r"web ?rip|web ?cap")),
    ("WEB", _tag(r"web")),
    ("HDTV", _tag(r"hdtv(?: ?rip)?|pdtv|dsr|dvb")),
    ("DVDRip", _tag(r"dvd ?rip|dvd ?(?:5|9)|dvd ?r|dvd|ntsc|pal")),
    ("HDRip", _tag(r"hd ?rip")),
    ("TVRip", _tag(r"tv ?rip|sat ?rip")),
    ("VHSRip", _tag(r"vhs ?rip|vhs")),
]
# Sources that cannot both be true of one file; WEB-DL and WEB, BluRay and REMUX can.
_SOURCE_FAMILY = {"REMUX": "disc", "BluRay": "disc", "BDRip": "disc", "WEB-DL": "web", "WEBRip": "web",
                  "WEB": "web", "HDTV": "tv", "TVRip": "tv", "DVDRip": "dvd", "HDRip": "rip", "VHSRip": "vhs"}

HDR_TAGS = [
    ("DV", _tag(r"dolby ?vision|dovi|dv")),
    ("HDR10+", _tag(r"hdr10 ?plus|hdr10\+")),
    ("HDR10", re.compile(_B + r"hdr10(?![a-z0-9+])")),
    ("HDR", re.compile(_B + r"hdr(?![a-z0-9+])")),
    ("HLG", _tag(r"hlg")),
]

VIDEO_CODECS = [
    ("AV1", _tag(r"av1")),
    ("HEVC", _tag(r"hevc|[xh] ?265")),
    ("AVC", _tag(r"avc|[xh] ?264")),
    ("VP9", _tag(r"vp9")),
    ("XviD", _tag(r"xvid|divx")),
    ("MPEG-2", _tag(r"mpeg ?2")),
]

# Every audio tag found is kept; channel counts are read separately.
AUDIO_TAGS = [
    ("TrueHD", _tag(r"true ?hd")),
    ("DTS:X", _tag(r"dts ?x")),
    ("DTS-HD MA", _tag(r"dts ?hd ?ma")),
    ("DTS-HD", re.compile(_B + r"dts ?hd(?! ?ma" + _E + r")" + _E)),
    ("DTS", re.compile(_B + r"dts(?! ?(?:hd|x)" + _E + r")" + _E)),
    ("DDP", re.compile(_B + r"(?:ddp|dd\+|e ?ac ?3|dolby digital plus)(?=[0-9 ]|$)")),
    ("DD", re.compile(_B + r"(?:dd|ac ?3|dolby digital)(?![a-z+])(?=[0-9 ]|$)")),
    ("AAC", re.compile(_B + r"aac(?=[0-9 ]|$)")),
    ("FLAC", re.compile(_B + r"flac(?=[0-9 ]|$)")),
    ("Opus", re.compile(_B + r"opus(?=[0-9 ]|$)")),
    ("LPCM", _tag(r"l?pcm")),
    ("MP3", _tag(r"mp3")),
    ("Atmos", _tag(r"atmos")),
]
_CHANNELS = re.compile(r"(?<![0-9])([1-9]) ([01])(?:ch)?(?![0-9])")

# -- ranking ---------------------------------------------------------------------

# Points per attribute; a release's score is the sum. Unknown values get a middle
# score, so a release is never sunk just because its name is unusual.
WEIGHTS = {
    "resolution": {"2160p": 40, "1080p": 30, "720p": 20, "576p": 10, "480p": 8, "SD": 6, "360p": 2, None: 12},
    "source": {"REMUX": 12, "BluRay": 9, "WEB-DL": 8, "WEB": 7, "BDRip": 6, "WEBRip": 6, "HDTV": 3,
               "DVDRip": 2, "HDRip": 2, "TVRip": 0, "VHSRip": -5, None: 4},
    "hdr": {"DV": 4, "HDR10+": 4, "HDR10": 3, "HDR": 3, "HLG": 2},   # the best one counts
    "video_codec": {"XviD": -2, "MPEG-2": -2},                        # others 0
    "audio": {"Atmos": 2, "TrueHD": 2, "DTS:X": 2, "DTS-HD MA": 2, "DTS-HD": 1, "DDP": 1, "LPCM": 2,
              "FLAC": 1},                                              # the best one counts
    "cam": -100,       # a cinema recording sinks below everything, whatever it claims
    "spam": -100,      # betting adverts and "watch free" pages, too
    "other_year": -100,  # a movie release naming another year is most likely another film
    "hardsub": -5,
}

# Quality tabs of the source list, best first.
UHD, FHD, HD, SD, OTHER = "uhd", "1080p", "720p", "sd", "other"
TIERS = [UHD, FHD, HD, SD, OTHER]
_TIER_OF = {"2160p": UHD, "1080p": FHD, "720p": HD, "576p": SD, "480p": SD, "SD": SD, "360p": SD}
RESOLUTION_RANK = {"2160p": 6, "1080p": 5, "720p": 4, "576p": 3, "480p": 2, "SD": 1, "360p": 0}


@dataclass
class Quality:
    """What a release name states. None/empty = not stated (or stated in conflicting ways)."""
    title: str = ""
    resolution: Optional[str] = None      # "2160p" | "1080p" | "720p" | "576p" | "480p" | "SD" | "360p"
    resolution_exact: bool = False        # a pixel height ("1080p"), not a loose word ("HD", "4K")
    source: Optional[str] = None          # a SOURCES name, e.g. "WEB-DL"
    hdr: List[str] = field(default_factory=list)       # e.g. ["DV", "HDR10"]
    video_codec: Optional[str] = None     # "HEVC" | "AVC" | "AV1" | ...
    audio: List[str] = field(default_factory=list)     # e.g. ["TrueHD", "Atmos"]
    channels: Optional[str] = None        # e.g. "7.1"
    cam: Optional[str] = None             # cinema-recording tag found: "CAM" | "TS" | "TC" | "PDVD"
    hardsub: Optional[str] = None         # burned-in subtitles: "KORSUB" | "HC"
    spam: Optional[str] = None            # "betting" | "watch free"
    years: List[int] = field(default_factory=list)     # years the name states
    other_year: Optional[int] = None      # movie: the name states this year, not the film's
    warnings: List[str] = field(default_factory=list)  # e.g. "conflicting resolution"

    @property
    def is_cam(self):
        return self.cam is not None

    @property
    def suspect(self):
        """Listed last whatever it claims: a cinema recording, spam, or (movies) another year."""
        return self.is_cam or bool(self.spam) or self.other_year is not None

    @property
    def tier(self):
        """The quality tab. A cinema recording's or spam's claimed resolution says nothing about its picture."""
        if self.is_cam or self.spam:
            return OTHER
        return _TIER_OF.get(self.resolution, OTHER)


def normalize(text):
    """Lower case, separators to single spaces; "+" kept ("HDR10+", "DD+")."""
    text = re.sub(r"[^a-z0-9+]+", " ", str(text).lower())
    return re.sub(r" +(?=\+)", "", text).strip()


def _all(table, text):
    return [name for name, pattern in table if pattern.search(text)]


def _first(table, text):
    return next((name for name, pattern in table if pattern.search(text)), None)


def _resolution(text, q):
    exact = set(_all(_EXACT_RESOLUTIONS, text))
    found = exact or set(_all(_LOOSE_RESOLUTIONS, text))
    if len(found) == 1:
        q.resolution_exact = bool(exact)
        q.resolution = found.pop()
    elif found:
        q.warnings.append("conflicting resolution")


def _source(text, q):
    found = _all(SOURCES, text)
    if "REMUX" in found:
        found = [s for s in found if s not in ("BluRay", "BDRip")]  # "BluRay REMUX" is a remux
    if "WEB-DL" in found or "WEBRip" in found:
        found = [s for s in found if s != "WEB"]
    if len({_SOURCE_FAMILY[s] for s in found}) > 1:
        q.warnings.append("conflicting source")
    elif found:
        q.source = found[0]


def _cam(text):
    for name, pattern in CAM_TAGS:
        for m in pattern.finditer(text):
            if name == "TS" and _TS_CONTEXT.search(text[max(0, m.start() - 10):m.end()]):
                continue
            return name
    return None


def parse(name, titles=None):
    """A Quality for one release or file name. Never raises: anything that is not
    a non-empty string gives an empty Quality. titles: the movie/show/episode names,
    whose words are never tags (a film called "Cam", an episode called "HD")."""
    if not isinstance(name, str) or not name.strip():
        return Quality(title=name if isinstance(name, str) else "")
    q = Quality(title=name)
    base = re.split(r"[\\/]", name)[-1]
    if base.lower().endswith(matcher.VIDEO_EXTENSIONS) and not base.endswith(".TS"):
        base = base.rsplit(".", 1)[0]  # ".ts" is a file type, not a telesync; "Movie.TS" is a tag
    text = normalize(matcher.without_titles(base, titles))
    if not text:
        return q
    _resolution(text, q)
    _source(text, q)
    q.cam = _cam(text)
    q.hardsub = _first(HARDSUB_TAGS, text)
    q.spam = _first(SPAM_TAGS, text)
    q.years = sorted({int(y) for y in _YEARS.findall(text)})
    hdr = _all(HDR_TAGS, text)
    if len(hdr) > 1 and "HDR" in hdr:
        hdr.remove("HDR")  # "HDR10 HDR" says HDR10
    q.hdr = hdr
    q.video_codec = _first(VIDEO_CODECS, text)
    q.audio = _all(AUDIO_TAGS, text)
    channels = _CHANNELS.search(text)
    q.channels = f"{channels.group(1)}.{channels.group(2)}" if channels and q.audio else None
    return q


def combine(*qualities):
    """One Quality from several names of the same release (episode file first, then the pack):
    the first one that states a value wins; cinema and subtitle tags in any of them count."""
    out = Quality(title=next((q.title for q in qualities if q.title), ""))
    for attr in ("resolution", "source", "video_codec", "channels", "cam", "hardsub", "spam"):
        setattr(out, attr, next((getattr(q, attr) for q in qualities if getattr(q, attr)), None))
    out.resolution_exact = next((q.resolution_exact for q in qualities if q.resolution), False)
    out.hdr = next((q.hdr for q in qualities if q.hdr), [])
    out.audio = next((q.audio for q in qualities if q.audio), [])
    out.years = sorted({y for q in qualities for y in q.years})
    out.warnings = sorted({w for q in qualities for w in q.warnings})
    if out.resolution and "conflicting resolution" in out.warnings:
        out.warnings.remove("conflicting resolution")  # the other name states it plainly
    return out


def of_candidate(candidate, titles=None, year=None):
    """The Quality of a source list entry: its file name, then its release name, then the
    resolution the provider stated (Torrentio's own label) when no name states one.
    year: a movie's release year. Names that state years, none of them within a year of it,
    get other_year (the closest one); a name without a year is never marked."""
    names = [n for n in (candidate.file_name, candidate.release_name) if n]
    q = combine(*(parse(n, titles) for n in names)) if names else Quality()
    if not q.resolution and "conflicting resolution" not in q.warnings and candidate.resolution in RESOLUTION_RANK:
        q.resolution = candidate.resolution
    if year and q.years and all(abs(y - year) > 1 for y in q.years):
        q.other_year = min(q.years, key=lambda y: abs(y - year))
    return q


def _best(table, values):
    return max((table.get(v, 0) for v in values), default=0)


def score(q, weights=None):
    """Higher is better. Explainable: the sum of the WEIGHTS rows for what the name states."""
    w = weights or WEIGHTS
    total = w["resolution"].get(q.resolution, w["resolution"][None]) + w["source"].get(q.source, w["source"][None])
    total += _best(w["hdr"], q.hdr) + w["video_codec"].get(q.video_codec, 0) + _best(w["audio"], q.audio)
    if q.is_cam:
        total += w["cam"]
    if q.spam:
        total += w["spam"]
    if q.other_year is not None:
        total += w["other_year"]
    if q.hardsub:
        total += w["hardsub"]
    return total


def summary(q):
    """Short display parts, best first: ["WEB-DL", "DV HDR10", "TrueHD Atmos 7.1"]."""
    parts = [q.source, " ".join(q.hdr) or None]
    audio = " ".join(q.audio[:2] + ([q.channels] if q.channels else []))
    parts.append(audio or None)
    return [p for p in parts if p]
