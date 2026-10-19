# NovaFlix Next-Episode Availability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Continue Watching cards and the title page say whether the next episode can be watched:
- "S2 E4 · Available", "S2 E4 · No English audio" or "S2 E4 · Airs Sat 25 Oct";
- "S2 E4 · Not available" or "S2 E4 · Availability unknown".

The checks are the same ones AniVerse did, for TMDB titles.

**Architecture:** Port AniVerse's three parts (`AniVerse/plugin.video.aniverse/resources/lib/sources/availability.py`, `gui/checks.py`, and the availability parts of `gui/show.py` and `gui/cards.py`; read them first):
- `sources/availability.py`: one check per (title, season, episode). Cheapest first: TMDB air dates, then the saved source list, then a background search that saves the source list for playback.
- `gui/checks.py`: runs checks for the cards on screen and updates their label and action in place.
- The title page: shows the Play episode's state under the buttons, and dots on episodes with a saved result.

The skins already have every state (`ListItem.Property(avail)`, `Window.Property(avail)`/`avail_line`), so no XML changes.

**Tech Stack:** Python 3 stdlib, existing `Library`, `discovery`, `language`, `ranking`, `Cache`, GUI `Loader`.

**Spec:**
- Owner, 2026-10-19: "same set up AniVerse has", for movies and shows.
- Earlier decisions:
  - English-only releases; non-English titles list their own releases with "No English audio" (Plan 4).
  - Caught-up ended shows leave Continue Watching (Plan 4).

## Global Constraints

- **State values** (the skins' `avail` property). Same strings as AniVerse:
  - `available`: an English release passes the filters.
  - `sub_only`: shown as "No English audio". Only non-English releases pass the filters, which is still playable.
  - `upcoming`: not aired. Carries the air date when TMDB has one.
  - `unavailable`: aired, the providers answered, nothing passes.
  - `unknown`: a provider or TMDB failed.
  - `checking`: GUI only, while a check runs.
- **Labels** (new strings 30442–30448, "S%d E%d" prefix like 30421):
  - 30442 `"S%d E%d · Checking..."`
  - 30443 `"S%d E%d · Available"`
  - 30444 `"S%d E%d · No English audio"`
  - 30445 `"S%d E%d · Airs %s"`
  - 30446 `"S%d E%d · Not aired yet"`
  - 30447 `"S%d E%d · Not available"`
  - 30448 `"S%d E%d · Availability unknown"`
  - Title-page wording (more room), as AniVerse's 30314/30315: 30449 `"S%d E%d · No streams currently available"`, 30450 `"S%d E%d · Could not check streams right now (try again later)"`.
  - Day format `"%a %d %b"` (AniVerse `cards._day`), from a TMDB `YYYY-MM-DD`.
- **Search and cache:**
  - The search is the `watch` route's: `discovery.discover(for_title(...))` → `language.split` → `ranking.build(..., dub_only=False)`.
  - The result is saved under `watch._cache_key`, with the same TTL and the same "never cache all-failed" rule, so playing afterwards opens at once.
- **Limits:** at most 2 searches at once (`SEARCHES_AT_ONCE = 2`). An all-failed search is remembered as `unknown` for 10 minutes (`FAILED_TTL = 600`). Grids check the rows on screen as the owner scrolls (AniVerse: `MAX_CHECKS = 20`, `GRID_COLUMNS = 6`, `GRID_AHEAD = 18`).
- **Card actions after a result:**
  - `available` / `sub_only` → `("watch", …)`;
  - `unavailable` / `unknown` → `("search", media_type, tmdb_id, season, episode)`, which runs `actions.search_again`;
  - `upcoming` → `("title", media_type, tmdb_id)`.
- **No network or SQLite on the GUI thread:** checks run in `Loader` jobs; saved results are read in the job too.
- **Test command:** `.venv\Scripts\python -m pytest -p no:cacheprovider -o addopts=""`. Known flaky: `tests/test_phone_keyboard.py` sockets (rerun once).

## Review Focus

1. **Running show, next episode not aired:**
   - Continue Watching keeps the show with "S2 E5 · Airs Sat 25 Oct", or "Not aired yet" when TMDB has no date. It no longer drops it as caught up.
   - The card opens the title page.
   - Pinned by `test_gui_lists.py::test_continue_running_show_shows_next_air_date` (Task 3).
2. **One failing check** (TMDB down, Torrentio 500) only marks its own card `unknown`. Other cards and the window carry on. Pinned by `test_checks.py::test_one_failure_stays_on_its_card` (Task 2).
3. **Result arriving after the owner left the screen** is applied to nothing and raises nothing. Pinned by `test_checks.py::test_result_after_reset_is_ignored` (Task 2).
4. **Checking twice:** the "continue:local" row then the full "continue" row, or the same episode on Home and in the grid, never searches the same episode twice in one screen load. Pinned by `test_checks.py::test_each_episode_checked_once` (Task 2).
5. **A saved source list from the `watch` route** (played before) gives the state with no network. Pinned by `test_availability.py::test_saved_sources_need_no_network` (Task 1).

---

### Task 1: Availability check for a title episode

**Files:**
- Create: `plugin.video.novaflix/resources/lib/sources/availability.py`
- Modify: `views/watch.py`: expose `discover_and_save(wanted, title, season, episode, found_settings, cache, cancelled)`, which is the existing `_discover`; keep `_discover` as an alias or rename the callers.
- Modify: `strings.po` (30442–30450)
- Test: `tests/test_availability.py`

**Interfaces (produces):**

```python
AVAILABLE, NO_ENGLISH, UPCOMING, UNAVAILABLE, UNKNOWN = "available", "sub_only", "upcoming", "unavailable", "unknown"

@dataclass
class Availability:
    state: str
    air_date: str = ""          # upcoming: TMDB "YYYY-MM-DD" when known

def aired(episode_or_none, today) -> Optional[bool]     # True / False (air_date in the future) / None (no date)
def cached(media_type, tmdb_id, season, episode, directory=None) -> Optional[Availability]
    # saved data only: cached title + season (Library.cached_title, and the season from the Cache
    # without network), saved source list or failed marker; None when a search is needed
def cached_episodes(media_type, tmdb_id, season, numbers, directory=None) -> {episode: Availability}
def check(media_type, tmdb_id, season, episode, directory=None) -> Availability   # never raises
```

Movies use `season = episode = 0`.

- **Verdict:** sources found → `language.split` → `ranking.build` with the current filters (`sources._settings()`).
  - English releases shown → `AVAILABLE`.
  - None shown, but other-language releases pass → `NO_ENGLISH`.
  - Providers answered (`ok` / `empty`) and nothing failed → `UNAVAILABLE`.
  - Otherwise → `UNKNOWN`.
- **Aired:** use the TMDB episode's `air_date` (`Library.episodes` filters out unaired ones, so read the full season through a new `Library.season_episodes(title, season)` that returns all episodes, dated or not). A movie has aired when `title.date <= today` or has no date.

- [ ] **Step 1: Write the failing tests.** Use FakeNet with TMDB and Torrentio fixtures and `FakeTorBox` where needed:

```python
def test_english_release_is_available():                  # BB S2E3 stream "Breaking.Bad.S02..." -> AVAILABLE, and watch._cache_key saved
def test_only_other_language_releases_is_no_english():     # one PT-BR-only stream -> NO_ENGLISH
def test_nothing_found_is_unavailable():                   # streams [] -> UNAVAILABLE
def test_provider_failure_is_unknown_and_remembered():     # torrentio 500 -> UNKNOWN; second check within 10 min: no request
def test_future_episode_is_upcoming_with_its_date(monkeypatch):   # library._today before S2E1 -> UPCOMING, air_date == S2E1 date
def test_saved_sources_need_no_network():                  # cache filled by watch.presearch -> cached() returns AVAILABLE, FakeNet sees no call
def test_movie_released_is_checked_and_future_movie_upcoming():
def test_check_never_raises():                             # TMDB 500 for the title -> UNKNOWN
```

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement** `Library.season_episodes`, `watch.discover_and_save`, `availability.py` and the strings.
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`feat(sources): next-episode availability check`).

### Task 2: Checks for cards on screen

**Files:**
- Create: `plugin.video.novaflix/resources/lib/gui/checks.py` (port of AniVerse `gui/checks.py`)
- Modify: `gui/cards.py`:
  - `Card` gains `check: tuple = ()`, which is `(media_type, tmdb_id, season, episode)`.
  - Add `availability_text(result, season, episode, text, title_page=False) -> str`.
  - Add `apply_availability(card, result, text) -> Card` (label and action as in Global Constraints).
- Test: `tests/test_checks.py`, `tests/test_cards.py`

**Interfaces (produces):**

```python
class AvailabilityChecks:
    def __init__(self, app)                     # app.loader, app.window
    def reset(self)
    def watch(self, control_id, page_cards, start=0, count=MAX_CHECKS)
    def follow_grid(self, control_id, page_cards, position)
```

Each check runs as a loader job named `"m:id:s:e"`. The job calls `availability.check`; a delivered error becomes `UNKNOWN`. On delivery, every card with that `check` and `avail == "checking"` gets `apply_availability`, and its ListItem label2 and `avail` property are updated (AniVerse `_apply`).

- [ ] **Step 1: Write the failing tests:**

```python
def test_cards_update_in_place_and_actions_follow_the_state():   # available -> ("watch", ...); unknown -> ("search", ...); upcoming -> ("title", ...)
def test_one_failure_stays_on_its_card():                         # check raises for one card only
def test_each_episode_checked_once():                             # watch() twice with the same cards -> one job per episode
def test_result_after_reset_is_ignored():                         # deferred loader; reset(); deliver -> no error, no item change
def test_grid_checks_rows_around_the_selection():                 # 60 cards, position 30 -> starts at 30, 18 cards
def test_availability_text_and_title_page_wording():              # cards tests: each state's label; upcoming date "Sat 25 Oct"
```

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`feat(gui): availability checks for cards on screen`).

### Task 3: Continue Watching shows availability

**Files:**
- Modify: `gui/lists.py` (`_continue_cards`), `gui/cards.py` (`title_continue_card`), `gui/home.py`, `gui/app.py` (GridView and App call `checks`, plus the `search` action kind)
- Test: `tests/test_gui_lists.py`, `tests/test_gui_home.py`, `tests/test_gui_app.py`

**Behaviour:**
- **Watched episode with a next aired episode:** the card's `label2` is 30442 (Checking…), `avail="checking"`, `check=(…next…)`, and the action is `watch`. A saved result (`availability.cached`, read in the list job) is applied at once.
- **Watched episode whose next episode isn't aired:** use `title.next_air` when it is later than the watched one. Then `avail="upcoming"`, the label is 30445 with the date (30446 without one), and the action is `title`.
- **Ended or caught-up show:** dropped (unchanged).
- **Started episode:** `avail="available"` (it was playing), with the resume label unchanged.
- **Home:** `HomeView._fill_continue` calls `app.checks.watch(row_control, cards)`. `GridView` calls `checks.follow_grid` on load and on moves, and `checks.reset()` on every load.
- **`App.run`:** `("search", m, id, s, e)` → `actions.search_again(m, id, s, e)`.

- [ ] **Step 1: Write the failing tests:**

```python
# test_gui_lists.py
def test_continue_watched_next_aired_is_checking():
def test_continue_running_show_shows_next_air_date(monkeypatch):    # tv_456: last_aired watched, next_air in the future
def test_continue_uses_saved_availability():                        # cache holds a saved source list -> "Available" at once
# test_gui_home.py
def test_continue_cards_update_in_place_and_one_failure_stays_on_its_card(make_app, monkeypatch)
def test_upcoming_card_opens_the_title_page_instead_of_playing(make_app, monkeypatch)
# test_gui_app.py
def test_grid_checks_availability_of_the_cards_around_the_selection(app, monkeypatch)
def test_search_action_searches_again(app)
```

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`feat(gui): Continue Watching says whether the next episode is available`).

### Task 4: Title page status line and episode dots

**Files:**
- Modify: `gui/title.py`
- Test: `tests/test_title_page.py`

**Behaviour** (AniVerse `gui/show.py` `_show_availability`, `_deliver_availability`, `_reload_availability`):
- `_fetch` adds `"avail": availability.cached_episodes(...)` for the opening season (movie: `{0: …}`).
- `refresh()` sets each episode card's `avail` from saved results, and shows the Play episode's state:
  - `avail` / `avail_line` with the title-page wording (30449/30450 for unavailable/unknown);
  - while unknown it reads `checking` / 30442, and one background `availability.check` starts (never twice).
- **Season change:** the saved results for the new season are loaded with its episodes.
- **After playback** (`watch.ended()`): the saved results are read again in a loader job.

- [ ] **Step 1: Write the failing tests:**

```python
def test_play_episode_status_line_checks_once_then_shows_the_result(monkeypatch)   # availability.check patched; avail_line "S1 E1 · Available"
def test_unknown_reads_could_not_check(monkeypatch)
def test_saved_results_put_dots_on_episodes()
def test_movie_status_line()
```

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`feat(gui): title page shows whether the Play episode has streams`).

### Task 5: Release 0.2.1

- [ ] **Step 1:** Set version `0.2.1`. News: "0.2.1: Continue Watching and the title page show whether the next episode is available, not available, airs on a date, or has no English audio."
- [ ] **Step 2:** Run `tools\build.py release`. Expected: `plugin.video.novaflix 0.2.1: added`, and 0.2.0 / 0.1.0 kept in `dist\repo`.
- [ ] **Step 3: PC check (owner)** after `tools\dev_kodi.py install`:
  - the Continue Watching cards show "Checking...", then a state;
  - a running show whose next episode airs later shows its air date;
  - the title page line under Play;
  - a card marked "Not available" searches again when clicked.
- [ ] **Step 4:** Ask the owner for approval, then push and run `tools\build.py publish`. Stick check: the same as Step 3.
