"""Grouping, sorting, filters, dub view and "same as last episode" pin
(DEC-021..DEC-025). Pure functions."""

from dataclasses import dataclass, field
from typing import List, Optional

from resources.lib.sources.matcher import RESOLUTION_ORDER

GROUP_ORDER = {"rdcloud": 0, "torrentio": 1, "nyaa": 2}


@dataclass
class Filters:
    min_resolution: Optional[str] = None   # e.g. "720p"; None = any
    max_size_gb: float = 0                 # 0 = no limit
    excluded_codecs: List[str] = field(default_factory=list)


@dataclass
class SourceList:
    shown: list
    hidden_by_filters: int
    hidden_non_dub: int


def dedupe(candidates):
    """One entry per (torrent, file); earlier providers win (RD account > Torrentio > Nyaa)."""
    in_account, seen, out = set(), set(), []
    for c in sorted(candidates, key=lambda c: GROUP_ORDER.get(c.origin, 9)):
        if c.origin == "rdcloud":
            key = ("rd", c.rd_torrent_id, c.rd_file_id)
            if c.info_hash:
                in_account.add(c.info_hash)
        else:
            if c.info_hash in in_account:
                continue  # already listed as ready in the owner's account
            key = ("hash", c.info_hash or c.release_name)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def passes(c, filters):
    """Filters only act on known values; unknown values are never filtered (DEC-023)."""
    if filters.min_resolution and c.resolution:
        if RESOLUTION_ORDER.get(c.resolution, 0) < RESOLUTION_ORDER.get(filters.min_resolution, 0):
            return False
    if filters.max_size_gb and c.size_bytes and c.size_bytes > filters.max_size_gb * 1e9:
        return False
    if c.codec and c.codec in filters.excluded_codecs:
        return False
    return True


def _sort_key(c):
    return (GROUP_ORDER.get(c.origin, 9), 0 if c.pinned else 1,
            -RESOLUTION_ORDER.get(c.resolution, -1), -(c.size_bytes or 0))


def build(candidates, filters, dub_only, last_group=None, last_resolution=None):
    unique = dedupe(candidates)
    for c in unique:
        c.pinned = bool(last_group and c.release_group and c.release_group.lower() == last_group.lower()
                        and (not last_resolution or c.resolution == last_resolution))
    filtered = [c for c in unique if passes(c, filters)]
    hidden_by_filters = len(unique) - len(filtered)
    if dub_only:
        dubbed = [c for c in filtered if c.audio in ("dub", "dual")]
        hidden_non_dub = len(filtered) - len(dubbed)
        filtered = dubbed
    else:
        hidden_non_dub = 0
    return SourceList(sorted(filtered, key=_sort_key), hidden_by_filters, hidden_non_dub)
