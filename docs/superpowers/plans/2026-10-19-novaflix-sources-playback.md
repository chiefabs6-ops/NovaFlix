# NovaFlix Sources & Playback (Plan 3 of 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Play a TMDB movie or TV episode through TorBox. Torrentio finds releases by IMDb id, English-only releases are kept, the owner picks a source, and the existing resolver plays it. The service tracks progress per title and season/episode, and Up next continues into the next season.

**Architecture:** A new plugin route `watch` (`type`, `id`, `s`, `e`, `resume`, `refresh`) runs next to AniVerse's `play` route. Shared lower layers are extended, not copied: Torrentio parsing, matcher, ranking, pre-check, resolver, the source-list loop and the resolve loop. Title playback gets its own storage tables (user.db v5) and its own session type in the player monitor. The anime path keeps working until Plan 4 wires the GUI to `watch` and deletes it, together with the Real-Debrid client and its fake-based tests.

**Tech Stack:** Python 3 stdlib, pytest with `tests/helpers.FakeNet` and `tests/test_torbox.FakeTorBox`, Torrentio (public), the Plan 2 `Library`.

**Spec:**
- Owner decisions in chat, 2026-10-19: TorBox only; English-only releases now, Polish later; owner picks the source (DEC-004).
- Roadmap: `docs/superpowers/plans/2026-10-19-novaflix-foundation.md`.
- Catalog interfaces: `docs/superpowers/plans/2026-10-19-novaflix-tmdb-catalog.md`.

## Global Constraints

- **Torrentio URLs:** series `{base}/stream/series/{imdb_id}:{season}:{episode}.json`, movie `{base}/stream/movie/{imdb_id}.json`. `base` comes from the existing `torrentio_url` setting. No debrid key is ever sent (SEC-12).
- **Release languages:** `RELEASE_LANGUAGES = ("en",)` in `sources/language.py`. Polish (`"pl"`) is added later by changing this one tuple; the filter must already handle any set.
- **Movies in history:** stored as `season = 0, episode = 0`. Episodes use TMDB season/episode numbers.
- **Hand-off:** the payload stays IDs only (SEC-15) in property `novaflix.playing`. Title payload: `{"type", "id", "season", "episode", "resume_s"?, "cleanup_torrent"?}`.
- **Existing behaviour unchanged:** anime `play` playback, history and tests keep passing until Plan 4. user.db migrations v1–v4 are released and never edited; v5 is appended.
- **Test command:** `.venv\Scripts\python -m pytest -p no:cacheprovider -o addopts=""`. Known flaky: `tests/test_phone_keyboard.py` socket tests (rerun once).

## Review Focus

1. **Release language evidence:**
   - Torrentio flags 🇬🇧 + 🇷🇺 (Russian voice-over plus the original) → kept.
   - Only 🇵🇹 → hidden. No flags and no language words → kept.
   - A name saying "ITA" only → hidden. "ITA-ENG" → kept.
   - Pinned by `test_language.py` cases (Task 3) taken from the recorded fixture.
2. **Sample files inside season packs** (`Sample/...s02e03.mkv`) must never be picked as the episode, or make the file choice ambiguous. Pinned by `test_matcher.py::test_sample_is_extra` (Task 2).
3. **Title without an IMDb id** (new or obscure titles): the source list says sources can't be searched, rather than failing silently or crashing. Pinned by `test_watch.py::test_title_without_imdb_id_explains` (Task 6).
4. **Up next on the last aired episode, or for a movie:** no prompt, no error. Pinned by `test_title_monitor.py::test_no_up_next_after_last_aired` (Task 7).
5. **Existing NovaFlix 0.1.0 profile** (user.db at v4 with anime rows) upgrading to v5: old rows kept, new tables empty. Pinned by `test_watching.py::test_v4_database_upgrades_in_place` (Task 5).

---

### Task 1: Torrentio by IMDb id, with languages

**Files:**
- Create: `tools/record_streams.py` (dev only). It saves `tests/fixtures/torrentio/series_tt0903747_2_3.json` and `movie_tt1160419.json` from the public Torrentio host: Breaking Bad S2E3 and Dune (2021). It cuts `streams` to 40 per file and stores raw JSON as UTF-8.
- Modify: `plugin.video.novaflix/resources/lib/sources/torrentio.py`, `resources/lib/models.py` (`Candidate`)
- Test: `tests/test_streams_imdb.py`

**Interfaces (produces):**
- `torrentio.imdb_url(base, imdb_id, season, episode, is_movie) -> str`
- `Candidate.languages: List[str] = []`: language codes from Torrentio's flag line, in order, with no duplicates.
- `torrentio.FLAGS`: maps flag emoji to a code. 🇬🇧/🇺🇸 → `en`, 🇵🇱 → `pl`, 🇷🇺 → `ru`, 🇺🇦 → `uk`, 🇮🇹 → `it`, 🇪🇸/🇲🇽 → `es`, 🇫🇷 → `fr`, 🇩🇪 → `de`, 🇵🇹/🇧🇷 → `pt`, 🇮🇳 → `hi`, 🇯🇵 → `ja`, 🇰🇷 → `ko`, 🇨🇳 → `zh`, 🇹🇷 → `tr`, 🇳🇱 → `nl`, 🇭🇺 → `hu`, 🇨🇿 → `cs`. Unknown flags are ignored.
- `parse_streams(...)` fills `languages`. Its signature and the anime behaviour are unchanged.

- [ ] **Step 1: Write the failing tests:**

```python
def test_imdb_urls():
    assert torrentio.imdb_url(None, "tt0903747", 2, 3, False) == "https://torrentio.strem.fun/stream/series/tt0903747:2:3.json"
    assert torrentio.imdb_url("https://h/", "tt1160419", None, None, True) == "https://h/stream/movie/tt1160419.json"
def test_series_streams_match_episode_and_carry_languages():
    raw = fixture("torrentio/series_tt0903747_2_3.json")
    found = torrentio.parse_streams(raw, 3, None, (2, 3), False)
    assert found and all(c.match in ("exact", "best_guess") for c in found)
    # every stream whose flag line holds the UK flag has "en" in languages
def test_movie_streams_skip_extras():
def test_streams_without_flags_have_no_languages():
```

- [ ] **Step 2: Record the fixtures.** Run `.venv\Scripts\python tools\record_streams.py`. Expected: 2 file names with sizes.
- [ ] **Step 3: Run the tests and confirm they fail.**
- [ ] **Step 4: Implement.** Flags are read from the lines after the stats line (the existing `languages` text).
- [ ] **Step 5: Run the full suite.** Expected: all pass.
- [ ] **Step 6: Commit** (`feat(sources): Torrentio by IMDb id with release languages`).

### Task 2: Matcher for mainstream names

**Files:**
- Modify: `resources/lib/sources/matcher.py`
- Test: `tests/test_matcher.py`

- [ ] **Step 1: Write the failing tests:**

```python
def test_double_episode_file_matches_both():   # "Show.S01E01E02.1080p.mkv" -> episode_range (1, 2); matches 2 with tvdb (1, 2)
def test_sample_is_extra():                     # "Sample/breaking.bad.s02e03.sample.mkv" and "...-sample.mkv" -> is_extra
def test_season_pack_name_is_batch():           # "Breaking.Bad.S02.1080p.BluRay.x265-RARBG" -> season 2, is_batch, episode None
def test_complete_series_range_is_batch():      # "Breaking Bad COMPLETE S01-S05 2160p" -> is_batch; matches(..., tvdb=(2, 3)) is None (best guess)
```

- [ ] **Step 2: Run them and confirm they fail.** Only the new cases should fail; existing matcher tests must already pass.
- [ ] **Step 3: Implement.**
  - Add `S(\d{1,2})E(\d{1,4})E(\d{1,4})` as an episode range.
  - Add `Sample` to `_EXTRA`, matching a path component or the `sample` word.
  - Read `S01-S05` as a batch with no single season.
- [ ] **Step 4: Run the full suite.** Expected: all pass, including every existing anime matcher test.
- [ ] **Step 5: Commit** (`feat(matcher): double episodes, samples, multi-season packs`).

### Task 3: English-only release filter

**Files:**
- Create: `resources/lib/sources/language.py`
- Modify: `strings.po` (30403: `"%d releases in other languages hidden"`)
- Test: `tests/test_language.py`

**Interfaces (produces):**

```python
RELEASE_LANGUAGES = ("en",)
NAME_LANGUAGES = {"en": r"\b(?:eng|english)\b", "pl": r"\b(?:pl|pol|polish|lektor|dubbing pl)\b", ...}  # plus the
#   non-English words matcher._OTHER_LANGUAGE already knows, each mapped to its code
def languages_of(candidate) -> set     # codes from candidate.languages, plus codes found in release/file name
                                       # (subtitle mentions removed with matcher._SUBTITLE_INFO first);
                                       # "multi" when the name says MULTi / Multi Audio / Dual Audio
def allowed(candidate, wanted=RELEASE_LANGUAGES) -> bool
    # True when no language evidence at all, or any wanted code present, or "multi" present
def split(candidates, wanted=RELEASE_LANGUAGES) -> (kept: list, hidden: int)
```

- [ ] **Step 1: Write the failing tests.** Build them from `series_tt0903747_2_3.json` (parsed with Task 1) plus literal names:
  - flags 🇬🇧/🇷🇺 kept; only 🇵🇹 hidden; no flags kept
  - `"Breaking.Bad.S02E01-13.1080p.NF.WEB-DL.ITA-ENG"` kept; `"Film.2021.1080p.ITA.AC3"` hidden
  - `"Dune.2021.MULTi.VFF.2160p"` kept; `"[SUB ITA] Show S01E01"` kept (subtitles only, no audio evidence)
  - with `wanted=("en", "pl")`: `"Film.2021.PL.1080p.WEB-DL"` kept; with `("en",)` hidden
  - `split()` counts the hidden ones
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement `language.py`.**
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`feat(sources): English-only release filter`).

### Task 4: Discovery for titles

**Files:**
- Modify: `resources/lib/sources/discovery.py`, `resources/lib/sources/rdcloud.py`
- Test: `tests/test_discovery_titles.py`

**Interfaces:**
- Consumes: `media.Title` (Plan 2).
- Produces:
  - `discovery.Wanted` gains `imdb_id: Optional[str] = None` and `season: Optional[int] = None`. `is_movie` keeps using `show.is_movie`, which both `Show` and `Title` have.
  - `discovery.for_title(title, season=None, episode=None) -> Wanted`. Movie: `number=1, tvdb=None`. Episode: `number=episode, tvdb=(season, episode), absolute=None`.
  - `from_torrentio` uses `imdb_url` when `wanted.imdb_id` is set and returns `SKIPPED` when a title has no IMDb id.
  - `from_nyaa` returns `SKIPPED` for titles (`wanted.imdb_id` set or `show` is a `Title`).
  - `rdcloud.title_keys(show)` reads `title_english`, `title_romaji`, `title`, `original_title`, `synonyms` with `getattr` defaults.

- [ ] **Step 1: Write the failing tests:**
  - `for_title` for Dune and for Breaking Bad S2E3
  - discover with `FakeNet` routes `torrentio.strem.fun/stream/series/tt0903747:2:3`, which calls no Nyaa and no kitsu URL
  - a title with no `imdb_id` → torrentio `SKIPPED`
  - TorBox account torrents named `Breaking.Bad.S02...` are found by `rdcloud.matching_torrents` for the Title
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: all pass, and the anime discovery tests are unchanged.
- [ ] **Step 5: Commit** (`feat(sources): discovery for TMDB titles`).

### Task 5: Watch history for titles (user.db v5)

**Files:**
- Modify: `resources/lib/storage/migrations.py` (append v5)
- Create: `resources/lib/storage/watching.py`
- Test: `tests/test_watching.py`

**v5 SQL:**

```sql
CREATE TABLE watch_history (
    media_type TEXT NOT NULL, tmdb_id INTEGER NOT NULL, season INTEGER NOT NULL, episode INTEGER NOT NULL,
    position_s REAL NOT NULL DEFAULT 0, duration_s REAL NOT NULL DEFAULT 0, watched INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL, PRIMARY KEY (media_type, tmdb_id, season, episode));
CREATE INDEX watch_history_updated ON watch_history (updated_at);
CREATE TABLE title_prefs (
    media_type TEXT NOT NULL, tmdb_id INTEGER NOT NULL, title TEXT, poster TEXT, backdrop TEXT, year INTEGER,
    last_release_group TEXT, last_resolution TEXT, updated_at REAL NOT NULL, PRIMARY KEY (media_type, tmdb_id));
```

**Interfaces (produces).** `WatchHistory(directory)`, with the same rules as `storage/history.History`: watched at ≥ 90 %, no resume point under 60 s, a rewatch never un-marks.

```python
save_position(media_type, tmdb_id, season, episode, position_s, duration_s) -> bool   # True if now watched
mark(media_type, tmdb_id, season, episode, watched)
states(media_type, tmdb_id) -> {(season, episode): (position_s, duration_s, watched)}
remember_title(title)                                   # title, poster, backdrop, year into title_prefs
remember_choice(media_type, tmdb_id, candidate)         # release group + resolution (DEC-024)
last_choice(media_type, tmdb_id) -> (group, resolution) | (None, None)
continue_watching(limit=50) -> [dict(media_type, tmdb_id, title, poster, backdrop, year, season, episode,
                                     position_s, duration_s, watched, updated_at)]   # latest row per title
```

- [ ] **Step 1: Write the failing tests:**
  - position, watched and resume rules (mirroring `test_history.py`)
  - a movie stored at (0, 0)
  - `continue_watching` returns one row per title, newest first
  - `remember_choice` / `last_choice`
  - `test_v4_database_upgrades_in_place`: build a v4 user.db by running `USER_MIGRATIONS[:4]`, insert an anime history row, open through `WatchHistory`. Expected: `PRAGMA user_version == 5`, the anime row is still there, and `watch_history` is empty.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement** the migration and `watching.py`.
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`feat(storage): watch history for movies and episodes`).

### Task 6: `watch` route: source list and play

**Files:**
- Modify: `resources/lib/views/sources.py`. Extract the `_choose` while-loop into `pick_source(request, rd, wanted, candidates, filters, dub_only, last_group, last_resolution, heading_base, play) -> bool`. `play(rd, picked) -> play.PLAYED | play.BACK | play.STOP`. The anime `_choose` calls it unchanged in behaviour.
- Modify: `resources/lib/views/play.py`. Extract the resolve loop of `play_candidate` into `resolve_choice(resolver, candidate, wanted, heading) -> (url, filename) | BACK | STOP`. `play_candidate` uses it.
- Create: `resources/lib/views/watch.py`
- Modify: `router.py`: `"watch": "resources.lib.views.watch:choose"`, and add `"watch"` to `PLAYABLE`
- Modify: `strings.po`:
  - 30404 `"S%d E%d"`
  - 30405 `"This title has no IMDb id on TMDB yet, so sources can't be searched."`
  - 30406 `"No English release found."`
- Test: `tests/test_watch.py`, using `FakeTorBox` from `test_torbox.py` plus `FakeNet` routes for TMDB and Torrentio fixtures, with the TorBox key and `tmdb_token` set in `xbmcaddon.settings`.

**Interfaces (produces):**

```python
def watch_url(media_type, tmdb_id, season=None, episode=None, resume=None) -> str   # router.build_url("watch", ...)
def choose(request)                     # params type, id, s, e, resume, refresh
def presearch(title, season, episode, cancelled=lambda: False)   # fills the source cache, no UI (Up next)
def _cache_key(title, season, episode) -> "sources:t1:{key}:{season or 0}:{episode or 0}"
```

**`choose` flow:**
1. Get the title from `Library`. No IMDb id → `ui.ok(30405)` and resolve failed.
2. `discovery.for_title`, then the cached or new discovery (same cache TTL and "don't cache all-failed" rule as `sources._discover`).
3. `language.split`. When everything is hidden → `ui.ok(30406)`. Otherwise the heading says how many were hidden (30403).
4. `sources.pick_source` with `dub_only=False` and `last_choice`.
5. `play` resolves with `resolve_choice`, then sets the hand-off, `remember_choice`, `remember_title`, and `ui.resolve`. Info: movie `MediaType=movie`, `Title`, `Year`. Episode `MediaType=episode`, `TvShowTitle`, `Season`, `Episode`, `Title` = episode name when known.

- [ ] **Step 1: Write the failing tests:**

```python
def test_watch_episode_plays_and_hands_off_ids_only():    # BB S2E3: setResolvedUrl True; handoff == {"type": "tv", "id": 1396, "season": 2, "episode": 3, ...}
def test_watch_movie_plays_largest_video():
def test_title_without_imdb_id_explains():                # ok dialog 30405; resolve failed; no Torrentio call
def test_other_language_releases_hidden_with_count():     # select heading mentions the hidden count; no 🇵🇹-only row listed
def test_all_other_language_says_so():
def test_cached_sources_open_without_network():           # second choose: no Torrentio call
def test_presearch_fills_cache_silently():
def test_anime_play_route_still_works():                  # an existing test_playback scenario re-run through the refactored loop
```

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement** the two extractions first. Run `tests/test_playback.py tests/test_sources.py`: all must pass before `watch.py` is written. Then write `watch.py` and the route.
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`feat(watch): source list and playback for movies and episodes`).

### Task 7: Player monitor for titles

**Files:**
- Modify: `resources/lib/playback/session.py`. Add `TitleSession(Session)` with fields `media_type, tmdb_id, season`. `next_ref` (season, episode) replaces `episode + 1`: `prepare(duration, skips, next_ref)` sets `next_episode = next_ref` when given.
- Modify: `resources/lib/playback/monitor.py`
  - `onAVStarted` builds a `TitleSession` when the payload has `"type"`.
  - `_prepare` skips AniSkip for titles (`skips=[]`).
  - Next episode: `Library(self._dir).next_episode(title, season, episode)`. A movie, or `None`, means no Up next.
  - `_save` uses `WatchHistory.save_position`, and never MAL.
  - `_offer_next` pre-searches with `watch.presearch` and shows `30218`-style text using `"S%d E%d"` (30404). Its button runs `watch_url(...)`.
  - A playback error offers the same `watch_url`.
  - "End episode" for a title only stops playback. Returning to the title page arrives with Plan 4's GUI.
- Test: `tests/test_title_monitor.py`. Reuse the fake player setup in `tests/test_player_monitor.py` and `tests/test_playback.py`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_title_session_saves_to_watch_history():      # 35 s ticks -> WatchHistory.states has (2, 3) position
def test_up_next_crosses_season():                     # BB (1, 7) -> prompt text "S2 E1", button opens watch url s=2 e=1
def test_no_up_next_after_last_aired():                # last aired episode -> no prompt, no error logged
def test_movie_has_no_up_next():
def test_title_playback_error_offers_watch_url():
def test_anime_session_unchanged():                    # existing anime payload still builds Session and saves History
```

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`feat(playback): monitor tracks movies and episodes, Up next across seasons`).

### Task 8: PC check (owner, manual)

The PC's Kodi needs the TorBox key and the TMDB key in NovaFlix settings. Install the branch build with `.venv\Scripts\python tools\dev_kodi.py install`.

- [ ] **Step 1:** Run `.venv\Scripts\python tools\dev_kodi.py open "watch?type=tv&id=1396&s=1&e=7"`. Expected: the source list for Breaking Bad S1 E7 opens. It shows no Russian-only or Portuguese-only rows, and the heading mentions the hidden ones.
- [ ] **Step 2:** Pick a source. Expected: it plays with English audio, and the Kodi info shows Breaking Bad, season 1, episode 7.
- [ ] **Step 3:** Seek to about 2 minutes before the end. Expected: the Up next popup says "S2 E1", and **Choose source** opens the S2 E1 list straight away (pre-searched).
- [ ] **Step 4:** Run `.venv\Scripts\python tools\dev_kodi.py open "watch?type=movie&id=438631"`. Expected: the Dune (2021) list opens, a source plays, and there's no Up next near the end.
- [ ] **Step 5:** Open AniVerse and play any episode. Expected: it works as before (Plan 3 changes nothing there).
