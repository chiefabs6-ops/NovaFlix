# NovaFlix TMDB Catalog (Plan 2 of 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build NovaFlix's metadata layer for real TV shows and movies on TMDB. It covers lists, search, genres, title details, seasons, episodes, "more like this", movie collections and "what's the next episode", all cached and tested against recorded TMDB responses.

**Architecture:** A new data model (`resources/lib/media.py`), a thin TMDB client (`metadata/tmdb.py`) and a cached facade (`metadata/library.py`), built next to the anime modules. Nothing in the UI uses them yet. Plan 4 wires the GUI to `Library` and deletes AniList, ani.zip, dubs, AnimeSchedule, AniSkip, franchise and MyAnimeList. So 0.1.0 keeps working untouched until then, and this plan is not released on its own.

**Tech Stack:** Python 3 stdlib (`net/http.py`, `storage/cache.py`), pytest with `tests/helpers.FakeNet`, TMDB API v3.

**Spec:** Owner decisions in chat on 2026-10-19 (TMDB for metadata; the owner has a TMDB account and key; keep the AniVerse design; English now, Polish later). Roadmap and constraints: `docs/superpowers/plans/2026-10-19-novaflix-foundation.md`.

## Global Constraints

- **API:**
  - Base `https://api.themoviedb.org/3`.
  - Images `https://image.tmdb.org/t/p/{size}{path}`: posters `w342`, backdrops `w1280`, episode stills `w300`.
  - Every request sends `language=en-US`. List calls for movies in cinemas and upcoming also send `region=IE`.
- **Credential:** the setting `tmdb_token`, a hidden string in a new "TMDB" settings category.
  - A 32-hex value is a v3 API key: send it as the query parameter `api_key`.
  - Anything else is a Read Access Token: send it as `Authorization: Bearer <token>`.
  - Register it with `redact.register_secret` before the first request.
  - It never appears in logs, fixtures, commits or chat.
- **Attribution:** TMDB's terms require the text "This product uses the TMDB API but is not endorsed or certified by TMDB." It goes in the TMDB settings category.
- **Rate limit:** `http.RATE_LIMITS["api.themoviedb.org"] = 120` (requests/min per process).
- **Unknown values stay `None`** and are shown as absent, never guessed (DEC-004).
- **Existing behaviour unchanged:** no change to anime modules, GUI, views or user.db in this plan. The full suite stays green.
- **Test command:** `.venv\Scripts\python -m pytest -p no:cacheprovider -o addopts=""`. Known flaky: `tests/test_phone_keyboard.py` socket tests; rerun once.

## Review Focus

1. **Missing or rejected token:**
   - No key → `errors.AuthError("TMDB key missing")` before any network call.
   - HTTP 401 → `AuthError`.
   - Pinned by `test_tmdb.py::test_missing_token_raises_before_network` and `::test_rejected_token_is_auth_error` (Task 3).
2. **Token leaking into logs or errors.** Pinned by `test_tmdb.py::test_token_is_redacted_in_errors` (Task 3).
3. **Titles with missing fields** (no poster, no release date, no IMDb id, `null` runtime, future `first_air_date`) must parse to `None`, not crash. Pinned by `test_media_parse.py::test_sparse_title_parses_with_nones` (Task 2).
4. **Episodes not aired yet** are hidden, but a season whose episodes all lack air dates still lists them. Pinned by `test_library.py::test_episodes_hide_unaired` and `::test_episodes_without_dates_are_listed` (Task 4).
5. **Up next across seasons:**
   - Last episode of season 1 → S2E1 when S2E1 has aired.
   - `None` when S2 hasn't aired or doesn't exist.
   - Specials (season 0) are never "next".
   - Pinned by `test_library.py::test_next_episode_*` (Task 4).

---

### Task 1: Recorded TMDB fixtures, settings and secret scan

**Owner step first.** Create `C:\Users\danze\Desktop\Kodi Add-On\NovaFlix\.env` (already git-ignored) with one line: `TMDB_TOKEN=<your Read Access Token>`. The executor never prints this file.

**Files:**
- Create: `tools/record_tmdb.py` (dev only, not packaged)
- Create: `tests/fixtures/tmdb/*.json` (written by the recorder)
- Modify: `tools/build.py`
  - Add the secret pattern `("JWT-style token (TMDB read token)", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"))`.
  - The 32-hex pattern already covers v3 keys.
- Modify: `plugin.video.novaflix/resources/settings.xml` and `strings.po`
  - New category `tmdb` (label 30400 "TMDB") holding setting `tmdb_token` (label 30401 "TMDB API key or Read Access Token", help 30402: the attribution sentence above, then " Get a free key at themoviedb.org → Settings → API.").
  - Control: `edit`, `hidden=true`, `allowempty`.
- Modify: `plugin.video.novaflix/resources/lib/net/http.py` (`RATE_LIMITS` entry).
- Test: `tests/test_build.py`, `tests/test_settings_actions.py`

**Recorder `tools/record_tmdb.py`:**
- Reads `TMDB_TOKEN` from `.env`. Calls with `requests`-free `urllib` and the auth rule above.
- Removes from every saved response any string equal to the token.
- Cuts every `results` array to its first 6 items and `parts` to 8. `page` and `total_pages` stay.
- Writes pretty JSON. Records these (name → path, params):
  - `trending_all_week.json` → `/trending/all/week`
  - `movie_popular.json` → `/movie/popular`
  - `tv_popular.json` → `/tv/popular`
  - `movie_now_playing.json` → `/movie/now_playing?region=IE`
  - `movie_upcoming.json` → `/movie/upcoming?region=IE`
  - `tv_airing_today.json` → `/tv/airing_today`
  - `movie_top_rated.json`, `tv_top_rated.json`
  - `genre_movie.json` → `/genre/movie/list`, `genre_tv.json` → `/genre/tv/list`
  - `discover_movie_28.json` → `/discover/movie?with_genres=28&sort_by=popularity.desc`
  - `search_multi_dune.json` → `/search/multi?query=dune`
  - `movie_438631.json` → `/movie/438631?append_to_response=external_ids,recommendations` (Dune, 2021; in a collection)
  - `collection.json` → `/collection/<belongs_to_collection.id from movie_438631.json>` (Dune collection)
  - `tv_1396.json` → `/tv/1396?append_to_response=external_ids,recommendations` (Breaking Bad, ended)
  - `tv_1396_season_1.json`, `tv_1396_season_2.json`
  - `tv_456.json` (The Simpsons, still running) and `tv_456_season_<last season number in tv_456.json>.json`
  - `unauthorized.json` → the body TMDB returns for `Authorization: Bearer invalid` (status 401)
- Prints only file names and sizes.

- [ ] **Step 1: Write the failing tests:**

```python
# tests/test_build.py
def test_scanner_finds_jwt_tokens():
    fake = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
    assert [k for k, _ in build.find_secrets(f"x = {fake}")] == ["JWT-style token (TMDB read token)"]

def test_recorded_tmdb_fixtures_hold_no_secrets():
    for name in os.listdir(os.path.join(ROOT, "tests", "fixtures", "tmdb")):
        assert build.find_secrets(open(path).read()) == [], name

# tests/test_settings_actions.py
def test_tmdb_settings_category():
    # settings.xml has <category id="tmdb" label="30400"> with setting tmdb_token (type string, hidden edit control)
    # strings 30400-30402 exist; 30402 contains "not endorsed or certified by TMDB"
```

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement** the scanner pattern, settings, strings, the rate limit and `tools/record_tmdb.py`.
- [ ] **Step 4: Record.** Run `.venv\Scripts\python tools\record_tmdb.py`. Expected: 20 file names with sizes, no errors, and the token never printed. Then run `git status`: `.env` is not listed.
- [ ] **Step 5: Run the full suite.** Expected: all pass.
- [ ] **Step 6: Commit** (`feat(tmdb): settings, recorded fixtures, JWT secret scan`).

### Task 2: Media model and TMDB parsing

**Files:**
- Create: `plugin.video.novaflix/resources/lib/media.py`
- Test: `tests/test_media_parse.py`

**Interfaces (produces):**

```python
MOVIE, TV = "movie", "tv"

@dataclass
class SeasonRef:      # number, name, episode_count: Optional[int], air_date: Optional[str], poster: Optional[str]

@dataclass
class Title:
    media_type: str; tmdb_id: int; title: str
    original_title: Optional[str] = None; year: Optional[int] = None; date: Optional[str] = None  # release / first air date
    overview: Optional[str] = None; poster: Optional[str] = None; backdrop: Optional[str] = None
    genres: List[str]; rating: Optional[float] = None   # vote_average, None when vote_count == 0
    runtime_min: Optional[int] = None; status: Optional[str] = None; imdb_id: Optional[str] = None
    seasons: List[SeasonRef]          # TV, season 0 (specials) kept but sorted last
    next_air: Optional[tuple] = None  # TV: (season, episode, "YYYY-MM-DD") from next_episode_to_air
    last_aired: Optional[tuple] = None  # TV: (season, episode) from last_episode_to_air
    collection: Optional[tuple] = None  # movie: (collection_id, name)
    key -> property "movie:438631" / "tv:1396"
    is_movie -> property
    to_dict() / from_dict()

@dataclass
class Episode:        # tmdb_id (show), season, number, title, overview, air_date, still, runtime_min, rating

@dataclass
class Collection:     # tmdb_id, name, overview, poster, backdrop, parts: List[Title] (release order, undated last)

def image(path, size) -> Optional[str]   # None for falsy path
def title_from(data: dict, media_type: Optional[str] = None) -> Optional[Title]
    # list items, details, search/multi (uses data["media_type"]; returns None for "person")
    # genres from details "genres" [{name}] or list "genre_ids" -> names via the genre map argument below
def titles_from(results: list, genre_names: dict = None, media_type=None) -> List[Title]   # skips None
def episode_from(data: dict, tmdb_id: int) -> Episode
def collection_from(data: dict) -> Collection
```

- [ ] **Step 1: Write the failing tests.** Read the expected values from the fixture in each test, never hard-code values that TMDB may change. For example:

```python
def test_movie_details_parse():
    raw = fixture("tmdb/movie_438631.json"); t = media.title_from(raw, media.MOVIE)
    assert t.key == "movie:438631" and t.title == raw["title"] and t.year == int(raw["release_date"][:4])
    assert t.imdb_id == raw["external_ids"]["imdb_id"] and t.imdb_id.startswith("tt")
    assert t.poster == "https://image.tmdb.org/t/p/w342" + raw["poster_path"]
    assert t.backdrop.startswith("https://image.tmdb.org/t/p/w1280/")
    assert t.collection == (raw["belongs_to_collection"]["id"], raw["belongs_to_collection"]["name"]) and t.runtime_min == raw["runtime"]
def test_tv_details_parse():          # tv_1396: seasons sorted 1..5 then 0; imdb_id; status "Ended"; next_air None
def test_running_show_has_next_air(): # tv_456: next_air == (s, e, date) from next_episode_to_air when present, else None
def test_search_multi_skips_people_and_keeps_both_types():
def test_list_items_get_genre_names(): # genre_ids mapped through genre_movie.json names
def test_sparse_title_parses_with_nones():
    t = media.title_from({"id": 5, "media_type": "tv", "name": "X"})
    assert (t.title, t.year, t.poster, t.imdb_id, t.rating, t.seasons) == ("X", None, None, None, None, [])
def test_rating_is_none_without_votes():   # {"vote_average": 0, "vote_count": 0} -> None
def test_title_round_trips_through_dict():
def test_season_episodes_parse():     # tv_1396_season_2: numbers 1..N, still w300 URL, air_date strings
def test_collection_parts_in_release_order():
```

- [ ] **Step 2: Run them and confirm they fail** (`ModuleNotFoundError: resources.lib.media`).
- [ ] **Step 3: Implement `media.py`.** Year comes from the first 4 characters of `release_date` / `first_air_date` when non-empty.
- [ ] **Step 4: Run the tests and the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`feat(tmdb): title, season, episode and collection model`).

### Task 3: TMDB client

**Files:**
- Create: `plugin.video.novaflix/resources/lib/metadata/tmdb.py`
- Test: `tests/test_tmdb.py`

**Interfaces (produces).** Each function takes the token explicitly, so the client never reads Kodi settings:

```python
API = "https://api.themoviedb.org/3"; LANGUAGE = "en-US"; REGION = "IE"
LISTS = {"trending": "/trending/all/week", "popular_movies": "/movie/popular", "popular_tv": "/tv/popular",
         "now_playing": "/movie/now_playing", "upcoming": "/movie/upcoming", "airing_today": "/tv/airing_today",
         "top_movies": "/movie/top_rated", "top_tv": "/tv/top_rated"}
REGIONAL = {"now_playing", "upcoming"}

def get(token, path, **params) -> dict          # auth rule, language, AuthError on 401 or empty token
def list_page(token, name, page=1) -> (List[Title], more: bool)     # more = page < total_pages
def genres(token, media_type) -> {id: name}
def discover(token, media_type, genre_id, page=1) -> (List[Title], bool)
def search(token, text, page=1) -> (List[Title], bool)               # /search/multi, people dropped
def details(token, media_type, tmdb_id) -> (Title, List[Title])     # append external_ids,recommendations
def season(token, tmdb_id, number) -> List[Episode]
def collection(token, collection_id) -> Collection
```

`list_page` maps `genre_ids` to names. It uses `genres()` for both types, merged and fetched once per call: a cached `Library` (Task 4) passes them in through an optional `genre_names` argument, so `list_page(token, name, page=1, genre_names=None)`.

- [ ] **Step 1: Write the failing tests** with `FakeNet().route("/3/movie/popular", fixture(...))` and similar routes:

```python
def test_missing_token_raises_before_network():    # get("", "/movie/popular") -> AuthError; FakeNet.calls == []
def test_bearer_token_header_and_language():       # token "eyJ..." -> headers Authorization "Bearer eyJ..."; url has language=en-US
def test_v3_key_goes_in_query():                   # 32-hex token -> url contains api_key=..., no Authorization header
def test_rejected_token_is_auth_error():           # route status 401 with unauthorized.json -> AuthError
def test_token_is_redacted_in_errors():            # 500 response -> raised error text and xbmc.log_records lack the token
def test_regional_lists_send_region():             # now_playing url has region=IE; popular_movies has none
def test_list_page_reports_more_pages():
def test_details_returns_title_and_recommendations():  # recommendations parsed as Titles of the right types
def test_search_returns_movies_and_shows_only():
def test_season_and_collection():
```

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement `tmdb.py`** over `http.get` (its retries and timeouts stay as they are).
- [ ] **Step 4: Run the tests and the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`feat(tmdb): API client`).

### Task 4: Library facade (cache, aired episodes, up next)

**Files:**
- Create: `plugin.video.novaflix/resources/lib/metadata/library.py`
- Test: `tests/test_library.py`

**Interfaces (produces), consumed by Plans 3 and 4:**

```python
class Library:
    def __init__(self, directory=None, token=None)   # token default: ui.setting("tmdb_token"); directory default paths.profile_dir()
    def list(self, name, page=1) -> (List[Title], bool)          # tmdb.LISTS names
    def genres(self, media_type) -> [(id, name)]                 # sorted by name
    def by_genre(self, media_type, genre_id, page=1) -> (List[Title], bool)
    def search(self, text, page=1) -> (List[Title], bool)
    def title(self, media_type, tmdb_id) -> Title
    def cached_title(self, media_type, tmdb_id) -> Optional[Title]   # never the network
    def more_like_this(self, media_type, tmdb_id) -> List[Title]
    def collection(self, collection_id) -> Collection
    def episodes(self, title, season) -> List[Episode]           # aired only (air_date <= today); undated listed
    def next_episode(self, title, season, episode) -> Optional[tuple]  # (season, episode) that has aired, or None
```

**Cache keys and TTLs** (`storage/cache.Cache`):
- `tmdb:list:{name}:{page}`: 6 h, but 1 h for `now_playing` and `airing_today`.
- `tmdb:genres:{type}`: 7 d.
- `tmdb:search:{text lower}:{page}`: 24 h.
- `tmdb:title:{key}`: 24 h, and it stores the recommendations too.
- `tmdb:season:{id}:{n}`: 6 h while `title.status` is "Returning Series" or "In Production", otherwise 30 d.
- `tmdb:collection:{id}`: 7 d.

Failed calls are never cached.

**`next_episode` rule:**
- Return the next number in the same season if it exists in `episodes(title, season)`.
- Otherwise return `(s, 1)` for the next season `s > season` (`s >= 1`) in `title.seasons` when `episodes(title, s)` contains episode 1.
- Otherwise return `None`.
- Never return season 0.

- [ ] **Step 1: Write the failing tests:**

```python
def test_lists_are_cached():                 # second Library().list("popular_movies") makes no new request
def test_failed_call_is_not_cached():        # first call 500 -> raises; second call 200 -> data
def test_title_and_more_like_this_share_one_request():
def test_episodes_hide_unaired(monkeypatch): # library._today patched to "2009-03-15": only S2 episodes with air_date <= it
def test_episodes_without_dates_are_listed():
def test_next_episode_within_season():       # BB (1, 3) -> (1, 4)
def test_next_episode_crosses_season():      # BB (1, 7) -> (2, 1)   (season 1 has 7 episodes in tv_1396_season_1)
def test_next_episode_none_at_series_end():  # BB last season last episode -> None (route season 6 -> 404 not needed: no season 6 in seasons)
def test_next_episode_none_when_next_season_unaired(monkeypatch):  # _today before S2E1 air date -> None
def test_next_episode_never_specials():
def test_missing_token_needs_no_network():   # Library(token="").list(...) -> AuthError, no request
```

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement `library.py`.** `_today()` returns the local date as an ISO string, so tests can patch it.
- [ ] **Step 4: Run the tests and the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`feat(tmdb): cached library with aired episodes and up next`).

### Task 5: Live smoke check (owner key, PC only)

- [ ] **Step 1:** Run `.venv\Scripts\python -c "..."` with `tools/record_tmdb.py`'s `.env` reading. Build `Library(directory=<temp dir>, token=<from .env>)` with the fakes path set as in `tests/conftest.py`. Print the counts and the first titles of `list("trending")`, `search("severance")`, `episodes(title("tv", 1396), 2)` and `next_episode(..., 1, 7)`. Expected: non-empty lists, `(2, 1)`, and no token in the output.
- [ ] **Step 2:** Add a ledger note with the printed counts. No commit needed.
