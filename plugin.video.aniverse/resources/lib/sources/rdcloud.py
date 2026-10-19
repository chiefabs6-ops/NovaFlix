"""Episodes already in the owner's Real-Debrid account (DEC-003, path 1).

Lists /torrents, keeps downloaded torrents whose name contains one of the
show's titles, then inspects at most MAX_INSPECT of them with
/torrents/info/{id} to find the episode file. Nothing here adds or deletes.
"""

import re

from resources.lib.models import Candidate
from resources.lib.sources import matcher

MAX_INSPECT = 5


def _compact(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def title_keys(show):
    keys = {_compact(t) for t in [show.title_english, show.title_romaji, show.title, *show.synonyms[:3]] if t}
    return {k for k in keys if len(k) >= 4}


def matching_torrents(torrents, show):
    keys = title_keys(show)
    hits = []
    for t in torrents:
        if t.get("status") != "downloaded":
            continue
        name = _compact(t.get("filename") or t.get("original_filename"))
        if any(k in name for k in keys):
            hits.append(t)
    return hits[:MAX_INSPECT]


def candidates_from_info(info, number, absolute=None, tvdb=None, is_movie=False):
    """Episode files inside one downloaded torrent. Only selected files have links."""
    out = []
    pack_rel = matcher.parse(info.get("filename") or "")
    for f in info.get("files") or []:
        path = f.get("path") or ""
        if not f.get("selected") or not matcher.is_video(path):
            continue
        rel = matcher.parse(path)
        verdict = None if is_movie else matcher.matches(rel, number, absolute, tvdb)
        if verdict is False or (verdict is None and not is_movie):
            continue
        out.append(Candidate(
            origin="rdcloud",
            release_name=info.get("filename") or path,
            info_hash=(info.get("hash") or "").lower() or None,
            file_name=path.lstrip("/"),
            size_bytes=f.get("bytes"),
            resolution=rel.resolution or pack_rel.resolution,
            codec=rel.codec or pack_rel.codec,
            release_group=pack_rel.group or rel.group,
            audio=rel.audio or pack_rel.audio,
            match="exact",
            status="ready",
            rd_torrent_id=info.get("id"),
            rd_file_id=f.get("id"),
        ))
    if is_movie and len(out) > 1:
        out.sort(key=lambda c: c.size_bytes or 0, reverse=True)
        out = out[:1]  # a movie torrent's largest video is the film; extras are smaller
    return out
