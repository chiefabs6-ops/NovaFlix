"""Movies and TV shows as NovaFlix uses them, parsed from TMDB responses (Plan 2).

Optional fields stay None when TMDB does not know them and are shown as absent,
never guessed (DEC-004).
"""

from dataclasses import asdict, dataclass, field, fields
from typing import List, Optional

MOVIE, TV = "movie", "tv"
IMAGES = "https://image.tmdb.org/t/p/"
POSTER, BACKDROP, STILL, LOGO = "w342", "w1280", "w300", "w500"


LANGUAGES = {"en": "English", "ko": "Korean", "ja": "Japanese", "zh": "Chinese", "cn": "Chinese", "hi": "Hindi",
             "fr": "French", "es": "Spanish", "de": "German", "it": "Italian", "pt": "Portuguese", "pl": "Polish",
             "ru": "Russian", "tr": "Turkish", "sv": "Swedish", "da": "Danish", "no": "Norwegian", "nl": "Dutch",
             "th": "Thai", "ar": "Arabic", "uk": "Ukrainian", "hu": "Hungarian", "cs": "Czech", "ta": "Tamil",
             "te": "Telugu"}


def language_name(code):
    """English name of a TMDB / release language code; unknown codes in capitals."""
    if not code:
        return ""
    return LANGUAGES.get(code, code.upper())


def image(path, size):
    return f"{IMAGES}{size}{path}" if path else None


def _year(date):
    return int(date[:4]) if date and len(date) >= 4 and date[:4].isdigit() else None


@dataclass
class SeasonRef:
    number: int
    name: Optional[str] = None
    episode_count: Optional[int] = None
    air_date: Optional[str] = None
    poster: Optional[str] = None


@dataclass
class Title:
    media_type: str
    tmdb_id: int
    title: str
    original_title: Optional[str] = None
    year: Optional[int] = None
    date: Optional[str] = None           # release date (movie) or first air date (TV)
    overview: Optional[str] = None
    poster: Optional[str] = None
    backdrop: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    rating: Optional[float] = None       # TMDB vote average; None without votes
    runtime_min: Optional[int] = None
    status: Optional[str] = None
    imdb_id: Optional[str] = None
    seasons: List[SeasonRef] = field(default_factory=list)  # TV: 1..N, then specials (0)
    next_air: Optional[tuple] = None     # TV: (season, episode, "YYYY-MM-DD")
    last_aired: Optional[tuple] = None   # TV: (season, episode)
    collection: Optional[tuple] = None   # movie: (collection id, name)
    original_language: Optional[str] = None  # TMDB code, e.g. "en", "ko"
    logo: Optional[str] = None           # title logo image (details only), shown in place of the title text

    @property
    def key(self):
        return f"{self.media_type}:{self.tmdb_id}"

    @property
    def is_movie(self):
        return self.media_type == MOVIE

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in data.items() if k in known}  # a newer version's cache entries (rollback)
        data["seasons"] = [SeasonRef(**s) for s in data.get("seasons", [])]
        for key in ("next_air", "last_aired", "collection"):
            data[key] = tuple(data[key]) if data.get(key) else None
        return cls(**data)


@dataclass
class Episode:
    tmdb_id: int                         # the show
    season: int
    number: int
    title: Optional[str] = None
    overview: Optional[str] = None
    air_date: Optional[str] = None
    still: Optional[str] = None
    runtime_min: Optional[int] = None
    rating: Optional[float] = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class Collection:
    tmdb_id: int
    name: str
    overview: Optional[str] = None
    poster: Optional[str] = None
    backdrop: Optional[str] = None
    parts: List[Title] = field(default_factory=list)  # release order, undated last

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        data["parts"] = [Title.from_dict(p) for p in data.get("parts", [])]
        return cls(**data)


def _numbers(data, *keys):
    """The values as a tuple when all are ints, else None (TMDB sometimes sends nulls or leaves keys out)."""
    values = tuple((data or {}).get(k) for k in keys)
    return values if all(isinstance(v, int) for v in values) else None


def _rating(data):
    return data.get("vote_average") if data.get("vote_average") and data.get("vote_count") else None


def _seasons(data):
    out = [SeasonRef(number=s["season_number"], name=s.get("name"), episode_count=s.get("episode_count"),
                     air_date=s.get("air_date"), poster=image(s.get("poster_path"), POSTER))
           for s in data.get("seasons") or [] if isinstance(s.get("season_number"), int)]
    return sorted(out, key=lambda s: (s.number == 0, s.number))


def _logo(data):
    """The English title logo, else one without a language; None when TMDB has neither."""
    logos = (data.get("images") or {}).get("logos") or []
    for wanted in ("en", None):
        for logo in logos:
            if logo.get("iso_639_1") == wanted and logo.get("file_path"):
                return image(logo["file_path"], LOGO)
    return None


def title_from(data, media_type=None, genre_names=None):
    """A Title from a list item, details or search/multi result; None for people and unknown types."""
    media_type = data.get("media_type") or media_type
    if media_type not in (MOVIE, TV) or data.get("id") is None:
        return None
    movie = media_type == MOVIE
    date = (data.get("release_date") if movie else data.get("first_air_date")) or None
    if data.get("genres"):
        genres = [g["name"] for g in data["genres"] if g.get("name")]
    else:
        genres = [genre_names[i] for i in data.get("genre_ids") or [] if genre_names and i in genre_names]
    imdb = data.get("imdb_id") or (data.get("external_ids") or {}).get("imdb_id") or None
    runtime = data.get("runtime") if movie else next(iter(data.get("episode_run_time") or []), None)
    nxt = _numbers(data.get("next_episode_to_air"), "season_number", "episode_number")
    last = _numbers(data.get("last_episode_to_air"), "season_number", "episode_number")
    collection = data.get("belongs_to_collection") or {}
    return Title(
        media_type=media_type,
        tmdb_id=int(data["id"]),
        title=(data.get("title") if movie else data.get("name")) or data.get("original_title")
        or data.get("original_name") or "?",
        original_title=(data.get("original_title") if movie else data.get("original_name")) or None,
        year=_year(date),
        date=date,
        overview=data.get("overview") or None,
        poster=image(data.get("poster_path"), POSTER),
        backdrop=image(data.get("backdrop_path"), BACKDROP),
        genres=genres,
        rating=_rating(data),
        runtime_min=runtime or None,
        status=data.get("status") or None,
        imdb_id=imdb,
        seasons=[] if movie else _seasons(data),
        next_air=nxt + (data["next_episode_to_air"].get("air_date"),) if nxt else None,
        last_aired=last,
        collection=(collection["id"], collection.get("name")) if isinstance(collection.get("id"), int) else None,
        original_language=data.get("original_language") or None,
        logo=_logo(data),
    )


def titles_from(results, genre_names=None, media_type=None):
    return [t for t in (title_from(r, media_type, genre_names) for r in results or []) if t]


def episode_from(data, tmdb_id):
    return Episode(
        tmdb_id=int(tmdb_id),
        season=data["season_number"],
        number=data["episode_number"],
        title=data.get("name") or None,
        overview=data.get("overview") or None,
        air_date=data.get("air_date") or None,
        still=image(data.get("still_path"), STILL),
        runtime_min=data.get("runtime") or None,
        rating=_rating(data),
    )


def episodes_from(results, tmdb_id):
    """Episodes of a season response; entries without int season/episode numbers are skipped."""
    return [episode_from(e, tmdb_id) for e in results or [] if _numbers(e, "season_number", "episode_number")]


def collection_from(data):
    parts = titles_from(data.get("parts"), media_type=MOVIE)
    parts.sort(key=lambda t: (t.date is None, t.date or ""))
    return Collection(tmdb_id=int(data["id"]), name=data.get("name") or "?", overview=data.get("overview") or None,
                      poster=image(data.get("poster_path"), POSTER), backdrop=image(data.get("backdrop_path"), BACKDROP),
                      parts=parts)
