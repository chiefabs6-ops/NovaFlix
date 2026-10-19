"""Data shapes shared between layers. Optional fields stay None when unknown
and are shown as absent, never guessed (DEC-004)."""

from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class Candidate:
    """One playable option for an episode, from any discovery provider (DEC-003)."""
    origin: str                       # "rdcloud" (the owner's TorBox account) | "torrentio"
    release_name: str
    info_hash: Optional[str] = None
    file_name: Optional[str] = None
    file_idx: Optional[int] = None    # index hint from Torrentio
    size_bytes: Optional[int] = None
    seeders: Optional[int] = None
    site: Optional[str] = None        # indexer that listed it, e.g. "1337x"
    resolution: Optional[str] = None
    codec: Optional[str] = None
    release_group: Optional[str] = None
    audio: Optional[str] = None       # "dub" | "dual" | None (unknown)
    match: str = "exact"              # "exact" | "best_guess"
    status: str = "not_checked"       # "ready" (already in the account) | "not_checked"
    rd_torrent_id: Optional[str] = None
    rd_file_id: Optional[int] = None
    pinned: bool = False
    languages: List[str] = field(default_factory=list)  # codes from Torrentio's flag line ("en", "ru", ...)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)
