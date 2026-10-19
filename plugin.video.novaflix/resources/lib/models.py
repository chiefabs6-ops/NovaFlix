"""Data shapes shared between layers. Optional fields stay None when unknown
and are shown as absent, never guessed (DEC-004)."""

from dataclasses import asdict, dataclass, field
from typing import List, Optional

# AniList formats shown in catalog lists (DEC-014). OVA, SPECIAL, MUSIC and
# non-anime formats appear only under a show's related entries.
CATALOG_FORMATS = ("TV", "TV_SHORT", "ONA", "MOVIE")
ANIME_FORMATS = ("TV", "TV_SHORT", "MOVIE", "SPECIAL", "OVA", "ONA", "MUSIC")


@dataclass
class ShowRef:
    anilist_id: int
    relation: str
    format: Optional[str]
    title: str
    poster: Optional[str] = None
    mal_id: Optional[int] = None


@dataclass
class RelationNode:
    """One franchise entry with its own relation links (M14). start = (year, month, day), 0 when unknown."""
    anilist_id: int
    title: str
    format: Optional[str]
    mal_id: Optional[int] = None
    poster: Optional[str] = None
    start: Optional[tuple] = None
    edges: List[tuple] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        data["start"] = tuple(data["start"]) if data.get("start") else None
        data["edges"] = [tuple(e) for e in data.get("edges", [])]
        return cls(**data)


@dataclass
class Show:
    anilist_id: int
    title: str
    title_romaji: Optional[str] = None
    title_english: Optional[str] = None
    title_native: Optional[str] = None
    synonyms: List[str] = field(default_factory=list)
    mal_id: Optional[int] = None
    format: Optional[str] = None
    status: Optional[str] = None
    episodes_total: Optional[int] = None
    duration_min: Optional[int] = None
    season: Optional[str] = None
    year: Optional[int] = None
    score: Optional[int] = None
    genres: List[str] = field(default_factory=list)
    description: Optional[str] = None
    poster: Optional[str] = None
    banner: Optional[str] = None
    start_date: Optional[str] = None
    next_episode: Optional[int] = None
    next_airing_at: Optional[int] = None
    relations: List[ShowRef] = field(default_factory=list)

    @property
    def is_movie(self):
        return self.format == "MOVIE"

    @property
    def aired_episodes(self):
        """Episodes that have aired, or None if unknown."""
        if self.next_episode:
            return self.next_episode - 1
        if self.status == "FINISHED":
            return self.episodes_total
        if self.status == "NOT_YET_RELEASED":
            return 0
        return None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        data["relations"] = [ShowRef(**r) for r in data.get("relations", [])]
        return cls(**data)


@dataclass
class Episode:
    anilist_id: int
    number: int
    title: Optional[str] = None
    air_date: Optional[str] = None
    thumbnail: Optional[str] = None
    overview: Optional[str] = None
    runtime_min: Optional[int] = None
    absolute_number: Optional[int] = None
    tvdb_season: Optional[int] = None
    tvdb_episode: Optional[int] = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class Candidate:
    """One playable option for an episode, from any discovery provider (DEC-003)."""
    origin: str                       # "rdcloud" | "torrentio" | "nyaa"
    release_name: str
    info_hash: Optional[str] = None
    file_name: Optional[str] = None
    file_idx: Optional[int] = None    # index hint from Torrentio
    size_bytes: Optional[int] = None
    seeders: Optional[int] = None
    site: Optional[str] = None        # indexer that listed it, e.g. "NyaaSi"
    resolution: Optional[str] = None
    codec: Optional[str] = None
    release_group: Optional[str] = None
    audio: Optional[str] = None       # "dub" | "dual" | None (unknown)
    match: str = "exact"              # "exact" | "best_guess"
    status: str = "not_checked"       # "ready" (already in RD) | "not_checked"
    rd_torrent_id: Optional[str] = None
    rd_file_id: Optional[int] = None
    pinned: bool = False
    languages: List[str] = field(default_factory=list)  # codes from Torrentio's flag line ("en", "ru", ...)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)
