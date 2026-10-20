"""Grouping, sorting, filters, dub view and "same as last episode" pin
(DEC-021..DEC-025), cinema-recording filter and quality tabs. Pure functions."""

from dataclasses import dataclass, field
from typing import List, Optional

from resources.lib.sources import quality
from resources.lib.sources.matcher import RESOLUTION_ORDER

GROUP_ORDER = {"rdcloud": 0, "torrentio": 1}


@dataclass
class Filters:
    min_resolution: Optional[str] = None   # e.g. "720p"; None = any
    max_size_gb: float = 0                 # 0 = no limit
    excluded_codecs: List[str] = field(default_factory=list)
    hide_cam: bool = True                  # cinema recordings (CAM, TS, TELESYNC...)
    hide_hardsubs: bool = False            # burned-in subtitles (KORSUB, HC)


@dataclass
class SourceList:
    shown: list
    hidden_by_filters: int                 # all filters, cinema recordings included
    hidden_non_dub: int
    hidden_cam: int = 0

    def tiers(self):
        """{tier: count} of the shown sources, in quality.TIERS order, empty tiers left out."""
        return tier_counts(self.shown)


# Orders the owner can pick in the source list. "best" also keeps the owner's account and
# the "same as last episode" pin on top.
BEST, RESOLUTION, SOURCE, HDR, SIZE = "best", "resolution", "source", "hdr", "size"
SORTS = [BEST, RESOLUTION, SOURCE, HDR, SIZE]


def dedupe(candidates):
    """One entry per (torrent, file); earlier providers win (TorBox account > Torrentio)."""
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


def quality_of(c, titles=None, year=None):
    """The candidate's quality.Quality, worked out once per candidate."""
    if c.quality is None:
        c.quality = quality.of_candidate(c, titles, year)
    return c.quality


def tier_counts(candidates):
    counts = {}
    for c in candidates:
        tier = quality_of(c).tier
        counts[tier] = counts.get(tier, 0) + 1
    return {t: counts[t] for t in quality.TIERS if t in counts}


def is_cam(c, filters):
    return filters.hide_cam and quality_of(c).is_cam


def passes(c, filters):
    """Filters only act on known values; unknown values are never filtered (DEC-023)."""
    q = quality_of(c)
    if filters.hide_cam and q.is_cam:
        return False
    if filters.hide_hardsubs and q.hardsub:
        return False
    resolution = q.resolution or c.resolution
    if filters.min_resolution and resolution:
        if RESOLUTION_ORDER.get(resolution, 0) < RESOLUTION_ORDER.get(filters.min_resolution, 0):
            return False
    if filters.max_size_gb and c.size_bytes and c.size_bytes > filters.max_size_gb * 1e9:
        return False
    if c.codec and c.codec in filters.excluded_codecs:
        return False
    return True


def _sort_key(sort):
    w = quality.WEIGHTS

    def key(c):
        q = quality_of(c)
        size, points = -(c.size_bytes or 0), -quality.score(q)
        if sort == RESOLUTION:
            return (q.suspect, -quality.RESOLUTION_RANK.get(q.resolution, -1), points, size)
        if sort == SOURCE:
            return (q.suspect, -w["source"].get(q.source, w["source"][None]), points, size)
        if sort == HDR:
            return (q.suspect, -max((w["hdr"].get(h, 0) for h in q.hdr), default=-1), points, size)
        if sort == SIZE:
            return (q.suspect, size)
        return (q.suspect, GROUP_ORDER.get(c.origin, 9), 0 if c.pinned else 1, points, size)
    return key


def build(candidates, filters, dub_only, last_group=None, last_resolution=None, titles=None, sort=BEST,
          year=None):
    """titles: the movie/show/episode names (their words are never quality tags).
    year: a movie's release year; releases naming another year are listed last."""
    unique = dedupe(candidates)
    for c in unique:
        quality_of(c, titles, year)
        c.pinned = bool(last_group and c.release_group and c.release_group.lower() == last_group.lower()
                        and (not last_resolution or c.resolution == last_resolution))
    filtered = [c for c in unique if passes(c, filters)]
    hidden_by_filters = len(unique) - len(filtered)
    hidden_cam = sum(1 for c in unique if is_cam(c, filters))
    if dub_only:
        dubbed = [c for c in filtered if c.audio in ("dub", "dual")]
        hidden_non_dub = len(filtered) - len(dubbed)
        filtered = dubbed
    else:
        hidden_non_dub = 0
    return SourceList(sorted(filtered, key=_sort_key(sort)), hidden_by_filters, hidden_non_dub, hidden_cam)
