"""Release-language filter (Plan 3): keep releases whose audio can be in a wanted language.

Evidence: Torrentio's flag line (Candidate.languages) and words in the release / file name.
Subtitle mentions are removed first; they say nothing about the audio. A release with no
evidence at all is kept: most plain English releases carry none. "MULTi", "Dual Audio" count
as possibly wanted. Polish is added later by widening RELEASE_LANGUAGES to ("en", "pl").
"""

import re

from resources.lib.sources import matcher

RELEASE_LANGUAGES = ("en",)
MULTI = "multi"

# Short codes ("EN", "PL", "ITA") only in capitals: lower-case they are ordinary words.
NAME_LANGUAGES = {
    "en": re.compile(r"(?i:\beng(?:lish)?\b)|\bEN\b"),
    "pl": re.compile(r"(?i:\b(?:pol(?:ish)?|lektor|dubbing[ ._-]?pl)\b)|\bPL\b"),
    "ru": re.compile(r"(?i:\brus(?:sian)?\b)"),
    "uk": re.compile(r"(?i:\b(?:ukr|ukrainian)\b)"),
    "it": re.compile(r"(?i:\bital(?:ian|iano)\b)|\bITA\b|\bIta\b"),
    "es": re.compile(r"(?i:\b(?:spanish|espa[nñ]ol|latino|castellano)\b)|\bSPA\b|\bSpa\b"),
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
_MULTI = re.compile(r"\bmulti\b|multi[ ._-]?audio|dual[ ._-]?audio|\bdual\b", re.I)


def _without_title(text, title):
    """The name with the title's own words removed ("The.Italian.Job" is not Italian audio)."""
    words = re.findall(r"\w+", title or "")
    article = ""
    if len(words) > 1 and words[0].lower() in ("the", "a", "an"):
        article = rf"(?:{re.escape(words.pop(0))}[ ._-]+)?"  # release names often drop it
    if not words:
        return text
    return re.sub(article + r"[ ._-]+".join(map(re.escape, words)), " ", text, flags=re.I)


def _name_languages(text, title=None):
    text = _without_title((text or "").replace("_", " "), title)
    text = matcher._SUBTITLE_INFO.sub(" ", text)
    found = {code for code, pattern in NAME_LANGUAGES.items() if pattern.search(text)}
    if _MULTI.search(text):
        found.add(MULTI)
    return found


def languages_of(candidate, title=None):
    """Language codes (and MULTI) the release states, from its flags and names. `title` is the
    movie or show title; its own words are never language evidence."""
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
