"""Release-language filter (Plan 3): keep releases whose audio can be in a wanted language.

Evidence: Torrentio's flag line (Candidate.languages) and words in the release / file name.
Subtitle mentions are removed first; they say nothing about the audio. A release with no
evidence at all is kept: most plain English releases carry none. "MULTi", "Dual Audio" count
as possibly wanted.

Language tabs: the source list has an English and a Polish tab that never mix languages.
A release with Polish evidence goes to the Polish tab; one with English audio (by the rule
above) goes to the English tab; a multi-language release with both is listed in both.
"""

import re

from resources.lib.sources import matcher

RELEASE_LANGUAGES = ("en",)
MULTI = "multi"
ENGLISH, POLISH = "en", "pl"
TABS = (ENGLISH, POLISH)  # source list language tabs, the first one opens
MAX_AUDIO_FLAGS = 3       # longer Torrentio flag lines are subtitle tracks (see _polish)

# Short codes ("EN", "PL", "ITA") only in capitals: lower-case they are ordinary words.
NAME_LANGUAGES = {
    "en": re.compile(r"(?i:\beng(?:lish)?\b)|\bEN\b"),
    "pl": re.compile(r"(?i:\b(?:pol(?:ish)?|lektor|dubbing[ ._-]?pl|pl[ ._-]?dub(?:bing)?)\b)|\bPL\b"),
    "ru": re.compile(r"(?i:\brus(?:sian)?\b)"),
    "uk": re.compile(r"(?i:\b(?:ukr|ukrainian)\b)"),
    "it": re.compile(r"(?i:\bital(?:ian|iano)\b)|\bITA\b"),
    "es": re.compile(r"(?i:\b(?:spanish|espa[nñ]ol|latino|castellano)\b)|\bSPA\b"),
    "fr": re.compile(r"(?i:\b(?:french|fran[cç]ais|truefrench|vff?|vf2)\b)"),
    "de": re.compile(r"(?i:\b(?:german|deutsch)\b)|\bGER\b"),
    "pt": re.compile(r"(?i:\b(?:portuguese|portugu[eê]s|pt[ -]?br|brazilian|dublado)\b)"),
    "hi": re.compile(r"(?i:\bhindi\b)|\bHIN\b"),
    "ta": re.compile(r"(?i:\btamil\b)"),
    "te": re.compile(r"(?i:\btelugu\b)"),
    "zh": re.compile(r"(?i:\b(?:chinese|mandarin|cantonese)\b)"),
    "ko": re.compile(r"(?i:\bkorean\b)"),
    "ja": re.compile(r"(?i:\bjapanese\b)|\bJPN\b"),
    "tr": re.compile(r"(?i:\bturkish\b)"),
    "ar": re.compile(r"(?i:\barabic\b)"),
    "hu": re.compile(r"(?i:\bhungarian\b)|\bHUN\b"),
    "cs": re.compile(r"(?i:\bczech\b)|\bCZE\b"),
}
# Polish subtitles ("Napisy PL", "PLSUB") say nothing about the audio. A "PL" before "napisy"
# is kept: it often belongs to the audio ("Dubbing PL Napisy PL").
_POLISH_SUBTITLES = re.compile(r"(?i:\bnapisy(?:[ ._-]?pl)?\b|\bpl[ ._-]?sub(?:s|bed)?\b)")
_MULTI = re.compile(r"\bmulti\b|multi[ ._-]?audio|dual[ ._-]?audio|\bdual\b", re.I)


def _name_languages(text, title=None):
    # The scene group tag ("-GER", "-HUN") and the title / episode name ("The.Italian.Job",
    # "The.Chinese.Restaurant") are never audio evidence.
    text = matcher.without_titles(matcher.without_group(text).replace("_", " "), title)
    text = matcher.SUBTITLE_INFO.sub(" ", _POLISH_SUBTITLES.sub(" ", text))
    found = {code for code, pattern in NAME_LANGUAGES.items() if pattern.search(text)}
    if _MULTI.search(text):
        found.add(MULTI)
    return found


def languages_of(candidate, title=None):
    """Language codes (and MULTI) the release states, from its flags and names. `title` is the
    title (or titles: show and episode name); their words are never language evidence."""
    found = set(candidate.languages or [])
    found |= _name_languages(candidate.release_name, title)
    found |= _name_languages(candidate.file_name, title)
    return found


def allowed(candidate, wanted=RELEASE_LANGUAGES, title=None):
    found = languages_of(candidate, title)
    return not found or MULTI in found or bool(found & set(wanted))


def split(candidates, wanted=RELEASE_LANGUAGES, title=None):
    """(kept candidates in order, number hidden)."""
    kept = [c for c in candidates if allowed(c, wanted, title)]
    return kept, len(candidates) - len(kept)


def _polish(candidate, title=None):
    """Polish audio: stated in the release / file name, or a 🇵🇱 flag in a short flag line.
    A long flag line ("en ja it pt es ko zh fr de nl pl cs hu tr" on English-only Disney+
    WEB-DLs, live 2026-10-20) lists the subtitle tracks, not the audio."""
    if POLISH in _name_languages(candidate.release_name, title) | _name_languages(candidate.file_name, title):
        return True
    flags = candidate.languages or []
    return POLISH in flags and len(flags) <= MAX_AUDIO_FLAGS


def in_tab(candidate, tab, title=None):
    """True when the release belongs in that language tab (see the module doc)."""
    if tab == POLISH:
        return _polish(candidate, title)
    return allowed(candidate, (tab,), title)


def tabs(candidates, title=None):
    """({tab: candidates in order} for every tab in TABS, number in no tab)."""
    out = {tab: [c for c in candidates if in_tab(c, tab, title)] for tab in TABS}
    listed = {id(c) for group in out.values() for c in group}
    return out, sum(1 for c in candidates if id(c) not in listed)
