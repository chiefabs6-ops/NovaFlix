"""Audio and subtitle choice at playback start (DEC-026, DEC-027).

Works on the stream lists Kodi's JSON-RPC Player.GetProperties returns:
audio {index, language, name, isdefault, ...}, subtitles {index, language,
name, isforced, ...}. Track tags can be missing or wrong, so anything unclear
leaves Kodi's own choice alone (audio) or turns subtitles off.
"""

import re

LANGUAGES = {
    "eng": {"eng", "en", "english"},
    "jpn": {"jpn", "ja", "jp", "japanese"},
}
SIGNS = re.compile(r"sign|song|forced", re.I)


def _is(stream, language):
    names = LANGUAGES.get(language, {language})
    tag = (stream.get("language") or "").strip().lower()
    if tag in names:
        return True
    # Untagged tracks: fall back to the track name ("English", "English Dub").
    return not tag and any(re.search(rf"\b{n}\b", stream.get("name") or "", re.I) for n in names if len(n) > 3)


def pick_audio(streams, language, current=None):
    """Index of the audio stream to switch to, or None to leave Kodi's choice."""
    if not language:
        return None
    matches = [s for s in streams if _is(s, language)]
    if not matches:
        return None  # DEC-027: language absent -> Kodi default, no guessing
    if current is not None and any(s.get("index") == current for s in matches):
        return None
    best = next((s for s in matches if s.get("isdefault")), matches[0])
    return best.get("index")


def audio_is(streams, index, language):
    stream = next((s for s in streams if s.get("index") == index), None)
    return stream is not None and _is(stream, language)


def pick_subtitle(subtitles):
    """With English audio (DEC-026 Q21a): ("on", index) for a single clear English
    Signs & Songs / forced track, otherwise ("off", None)."""
    english = [s for s in subtitles if _is(s, "eng")]
    candidates = [s for s in english if s.get("isforced") or SIGNS.search(s.get("name") or "")]
    if len(candidates) > 1:
        named = [s for s in candidates if SIGNS.search(s.get("name") or "")]
        candidates = named if len(named) == 1 else [s for s in candidates if s.get("isforced") and s in named]
    if len(candidates) == 1:
        return "on", candidates[0].get("index")
    return "off", None
