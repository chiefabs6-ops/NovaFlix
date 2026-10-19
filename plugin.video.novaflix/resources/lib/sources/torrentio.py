"""Stremio-protocol aggregator (Torrentio-compatible), torrent-only (DEC-003).

GET {base}/stream/series/kitsu:{kitsu_id}:{episode}.json  (movies: /stream/movie/kitsu:{id}.json)
No debrid options are configured, so the owner's Real-Debrid token is never
sent (SEC-12). Stream "title" lines (fixture torrentio_46474_3.json):
  1 release name, 2 file name (packs), 3 "👤 seeders 💾 size ⚙️ site", 4 languages.
"""

import re

from resources.lib.models import Candidate
from resources.lib.sources import matcher

DEFAULT_BASE = "https://torrentio.strem.fun"
_UNITS = {"B": 1, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12,
          "KIB": 1024, "MIB": 1024 ** 2, "GIB": 1024 ** 3, "TIB": 1024 ** 4}


def parse_size(text):
    m = re.search(r"([\d.]+)\s*([KMGT]i?B|B)\b", text or "", re.I)
    if not m:
        return None
    return int(float(m.group(1)) * _UNITS[m.group(2).upper()])


def url(base, kitsu_id, number, is_movie):
    base = (base or DEFAULT_BASE).rstrip("/")
    if is_movie:
        return f"{base}/stream/movie/kitsu:{int(kitsu_id)}.json"
    return f"{base}/stream/series/kitsu:{int(kitsu_id)}:{int(number)}.json"


def _audio(release, file_name, languages):
    """English-dub evidence only (DEC-025).

    Flags alone are NOT evidence: on subtitle-only releases Torrentio lists the
    subtitle languages as flags ("Multi Subs / 🇬🇧 / 🇷🇺 ...", live 2026-10-11).
    Torrentio writes "Dubbed" only when an audio dub is present.
    """
    dubbed = bool(re.search(r"\bdubbed\b", languages, re.I))
    text = f"{release} {file_name or ''}"
    if matcher.other_language_only(text):
        return None  # the 🇬🇧 flag can come from English subtitles ("[SUB PT-BR ENG]")
    if dubbed and "🇬🇧" in languages:
        return "dub"
    stated = matcher.audio_of(text)
    if stated:
        return stated
    if dubbed and re.search(r"dual audio", languages, re.I):
        return "dual"
    return None


def parse_streams(data, number, absolute=None, tvdb=None, is_movie=False):
    out = []
    for stream in (data or {}).get("streams") or []:
        info_hash = (stream.get("infoHash") or "").lower()
        if not re.fullmatch(r"[0-9a-f]{40}", info_hash):
            continue
        lines = (stream.get("title") or "").split("\n")
        release = lines[0].strip() if lines else ""
        hints = stream.get("behaviorHints") or {}
        file_name = hints.get("filename") or (lines[1].strip() if len(lines) > 1 and "👤" not in lines[1] else None)
        stats_index = next((i for i, l in enumerate(lines) if "👤" in l or "💾" in l), None)
        stats = lines[stats_index] if stats_index is not None else ""
        # Languages follow the stats line; file names (which may contain "/") come before it.
        languages = " ".join(lines[stats_index + 1:]) if stats_index is not None else ""

        file_rel = matcher.parse(file_name or release)
        pack_rel = matcher.parse(release)
        if is_movie:
            verdict = not file_rel.is_extra  # the film itself, never its extras
        else:
            verdict = matcher.matches(file_rel, number, absolute, tvdb)
        if verdict is False:
            continue  # aggregator offered a file for a different episode

        seeders = re.search(r"👤\s*(\d+)", stats)
        site = re.search(r"⚙️\s*(\S+)", stats)
        resolution_hint = (stream.get("name") or "").split("\n")[-1]
        out.append(Candidate(
            origin="torrentio",
            release_name=release or (file_name or "?"),
            info_hash=info_hash,
            file_name=file_name,
            file_idx=stream.get("fileIdx") if isinstance(stream.get("fileIdx"), int) else None,
            size_bytes=parse_size(stats),
            seeders=int(seeders.group(1)) if seeders else None,
            site=site.group(1) if site else None,
            resolution=file_rel.resolution or pack_rel.resolution or matcher.parse(resolution_hint).resolution,
            codec=file_rel.codec or pack_rel.codec,
            release_group=pack_rel.group or file_rel.group,
            audio=_audio(release, file_name, languages),
            match="exact" if verdict else "best_guess",
        ))
    return out
