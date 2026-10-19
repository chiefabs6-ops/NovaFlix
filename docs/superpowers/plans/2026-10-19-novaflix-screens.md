# NovaFlix Screens (Plan 4 of 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** NovaFlix's own screens show real TV shows and movies:
- Home, Explore and Search;
- a title page with a season picker;
- Continue Watching and My List;
- More like this, and movie collections.

Everything plays through Plan 3's `watch` route. Then every anime, MyAnimeList and Real-Debrid part is removed and NovaFlix 0.2.0 is released to the stick.

**Architecture:** Same window design and skins (AniVerse M12 look, Plan 1 colours). The GUI data layer (`gui/lists.py`, `gui/cards.py`) reads Plan 2's `Library` and Plan 3's `WatchHistory`. Cards carry title actions: `("title", media_type, tmdb_id)` and `("watch", media_type, tmdb_id, season, episode, resume_s)`. The show page becomes a title page. The MyAnimeList button slot (id 503) becomes the season picker. The anime code paths are deleted last, once nothing uses them.

**Tech Stack:** Python 3 stdlib, Kodi WindowXML, pytest with the `tests/fakes` Kodi fakes and recorded TMDB/Torrentio fixtures.

**Spec:**
- Owner decisions in chat, 2026-10-19:
  - Keep the AniVerse design.
  - TorBox only; English releases.
  - Non-English titles still appear everywhere. When a title has no English release, its releases are listed anyway, and the screen says clearly that they have no English audio track.
- Roadmap: `docs/superpowers/plans/2026-10-19-novaflix-foundation.md`.
- Interfaces: `2026-10-19-novaflix-tmdb-catalog.md` (Library) and `2026-10-19-novaflix-sources-playback.md` (watch, WatchHistory).

## Global Constraints

- **Layouts:** keep the existing XML (`novaflix-app.xml`, `novaflix-show.xml`, …) and control IDs (`gui/ids.py`). Only the button 503 property names change: `mal_label` → `season_label`.
- **Sidebar main:** Home, Search, Continue Watching, My List.
- **Sidebar Explore:** Trending, Popular movies, Popular shows, Top rated movies, Top rated shows, Airing today, Genres.
- **Home rows** (four existing row controls): Continue Watching, Trending, Popular shows, Popular movies. The hero rotates the first 5 Trending titles.
- **Card actions:**
  - `("title", media_type, tmdb_id)` opens the title page;
  - `("watch", media_type, tmdb_id, season, episode, resume_s)` starts `watch_url(...)` through `PlayMedia`;
  - `("t_episode", tmdb_id, season, episode)` is an episode on a title page (resume prompt, then watch).
- **Grid keys:**
  - lists: `trending`, `popular_movies`, `popular_tv`, `top_movies`, `top_tv`, `airing_today`;
  - personal: `continue`, `mylist`;
  - genres: `genres` (tiles) and `genre:<movie|tv>:<id>`;
  - search: `search` (tiles) and `search:<text>`;
  - `more:<media_type>:<tmdb_id>` (More like this / collection rows in the related view);
  - `torbox` and `torbox:<id>` (unchanged).
- **The GUI is the only interface:** the `novaflix_look` setting and the classic directory listings go. The plugin root and `launch` open the window.
- **Deferred to a later plan** (not in 0.2.0):
  - availability labels ("next episode available") on Continue Watching and the title page;
  - Polish releases;
  - skip intro.
- **Test command:** `.venv\Scripts\python -m pytest -p no:cacheprovider -o addopts=""`. Known flaky: `tests/test_phone_keyboard.py` socket tests (rerun once).

## Review Focus

1. **Non-English title without English releases:**
   - the source list opens with all its releases;
   - the heading says "No English audio track — Korean releases";
   - nothing is hidden silently.
   - Pinned by `test_watch.py::test_non_english_title_lists_original_language_releases` (Task 2).
2. **TMDB key missing on first open:** the window opens and the rows show the "add your TMDB key" text with a button to Settings, instead of a crash loop or empty silence. Pinned by `test_gui_app.py::test_missing_tmdb_key_asks_for_settings` (Task 4).
3. **Show with only a specials season, or season numbers with gaps** (S1, S3): the season picker lists what exists, specials last. Pinned by `test_title_page.py::test_season_choices_skip_missing_and_put_specials_last` (Task 5).
4. **End episode** returns to the right title page, also for a different title than the one that was open. Pinned by `test_title_monitor.py::test_end_episode_returns_to_title_page` (Task 5).
5. **Old 0.1.0 profile** (anime favourites, history, MAL rows in user.db) opens without errors after the update. Old tables stay, unused. Pinned by `test_watching.py::test_v4_database_upgrades_in_place`, extended to v6 (Task 1).

---

### Task 1: My List, search history store, original language

**Files:**
- Modify: `resources/lib/storage/migrations.py` (append v6), `resources/lib/media.py`
- Create: `resources/lib/storage/mylist.py`, `resources/lib/storage/searches.py`
- Test: `tests/test_mylist.py`, `tests/test_media_parse.py`, `tests/test_watching.py`

**v6 SQL:**

```sql
CREATE TABLE my_list (media_type TEXT NOT NULL, tmdb_id INTEGER NOT NULL, title TEXT NOT NULL, poster TEXT,
                      year INTEGER, added_at REAL NOT NULL, PRIMARY KEY (media_type, tmdb_id));
```

**Interfaces (produces):**
- `MyList(directory)` with:
  - `add(title)`, `remove(media_type, tmdb_id)`
  - `contains(media_type, tmdb_id) -> bool`
  - `all() -> [Title]`, newest first, built from the stored fields.
- `searches.recent(directory, limit=10) -> [str]`, `searches.remember(directory, text)`. These use the existing `search_history` table (same rules as `views/browse._recent_queries/_remember`; read them before deleting).
- `Title.original_language: Optional[str]` (TMDB `original_language`, e.g. `"ko"`).
- `media.language_name(code) -> str`: English name for the common codes:
  - en, ko, ja, zh, hi, fr, es, de, it, pt, pl, ru, tr, sv, da, no, nl, th, ar;
  - any other code → the code in capitals;
  - `None` → `""`.

- [ ] **Step 1: Write the failing tests:**
  - add, contains, remove and order of My List
  - search history keeps the 10 newest, without duplicates
  - `title_from` for `tv_1396` → `original_language == "en"`
  - `language_name("ko") == "Korean"`, `language_name("xx") == "XX"`
  - the v4-upgrade test now expects `user_version == 6`
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`feat(storage): My List, search history, original language`).

### Task 2: Non-English titles in the source list

**Files:**
- Modify: `resources/lib/views/watch.py`
- Modify: `strings.po`: 30408 `"No English audio track — %s releases"`. 30406 is no longer used here.
- Test: `tests/test_watch.py`

**Behaviour.** When `candidates` exist but `language.split` keeps none:
- Do not stop. List all candidates.
- The note is 30408, with `language_name(title.original_language)`, or `language_name` of the most common release language when the original language is English or unknown.
- The row details line gains "No English audio" (30409) for every row. Add an optional `extra` text argument to `sources.details_line(c, check, extra=None)`, passed through `pick_source(..., row_note=None)`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_non_english_title_lists_original_language_releases():   # TMDB title with original_language "ko", one 🇰🇷-only stream
    # -> select heading contains "No English audio track — Korean releases"; the row is listed and ends with "No English audio"
def test_english_releases_still_hide_others():                    # existing behaviour kept when some English release exists
```

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.** Remove `test_all_other_language_says_so` (behaviour replaced) in the same commit.
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`feat(watch): non-English titles list their releases and say there is no English audio`).

### Task 3: Screen data for titles (`gui/lists.py`, `gui/cards.py`)

**Files:**
- Modify: `resources/lib/gui/lists.py`, `resources/lib/gui/cards.py`
- Modify: `strings.po`:
  - 30410 "Popular movies", 30411 "Popular shows", 30412 "Top rated movies", 30413 "Top rated shows", 30414 "Airing today"
  - 30415 "My List", 30416 "Movies", 30417 "TV shows", 30418 "More like this", 30419 "%s collection"
  - 30420 "Resume S%d E%d · %s left", 30421 "Next: S%d E%d", 30422 "Resume · %s left"
  - 30423 "Add your TMDB key in Settings to browse."
- Test: rewrite `tests/test_cards.py` and `tests/test_gui_lists.py` for titles. Delete their anime cases.

**Interfaces (produces):**

```python
# cards.py (pure)
def title_card(title) -> Card                    # label title, label2 year, poster, wide backdrop, action ("title", type, id)
def continue_card(row, next_ref, text) -> Card   # row from WatchHistory.continue_watching(); next_ref (s, e) | None
    # watched episode + next_ref -> label2 30421, action ("watch", "tv", id, s, e, 0)
    # watched episode, no next_ref -> None (caller drops it: caught up)
    # watched movie -> None
    # started -> label2 30420 / 30422 (movie), action ("watch", ..., int(position))
def title_episode_card(title, episode, state, text) -> Card   # kind "episode", action ("t_episode", id, season, number)
def title_meta(title, text) -> str               # "2008 · TV · 5 seasons · ★ 8.9 · Korean" (language only when not en)
def title_hero(title, text) -> dict              # same keys as hero(): title, alt (original title if different), plot, art, dark, meta
def next_up(numbers, states) -> (season, episode, resume_s)   # like next_episode() over (s, e) keys within one season

# lists.py
def load(key, page=1) -> Page                    # grid keys from Global Constraints; Page.shows renamed Page.titles
def home_row(key) -> Page                        # unchanged contract
def more_like_this(media_type, tmdb_id) -> RelatedPage   # rows: [collection row (movies in a collection)], "More like this"
class TmdbKeyMissing(Exception)                  # raised by load() when Library has no token (Review Focus 2)
```

**Continue Watching:** the rows come from `WatchHistory.continue_watching()`. For a watched last episode, `next_ref = Library().next_episode(Library().title(...), s, e)` runs in the loader thread. `home_row("continue:local")` uses saved data only: `cached_title`, and no Up next lookup when nothing is saved, so the card reads "Next: …" only once known.

- [ ] **Step 1: Write the failing tests.** Use FakeNet with the TMDB fixtures:
  - every grid key returns cards of the right action
  - genres tiles list the movie genres, then the TV genres (label2 "Movies" / "TV shows")
  - search remembers the text
  - continue cards for started / watched-with-next / caught-up / movie
  - `more_like_this` for Dune → a collection row first, then More like this; for Breaking Bad → only More like this
  - missing token → `TmdbKeyMissing`
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: all pass, except the tests Task 4/5 rewrite. List those failing files in the ledger and make them pass by the end of Task 5.
- [ ] **Step 5: Commit** (`feat(gui): screen data for TV shows and movies`).

### Task 4: App window: sidebar, Home, grid, More like this, long-press menu

**Files:**
- Modify: `resources/lib/gui/app.py`, `gui/home.py`, `gui/related.py` (now "More like this" rows), `gui/actions.py`
- Delete: `gui/malhub.py`, `gui/checks.py` (availability labels deferred)
- Test: rewrite `tests/test_gui_app.py`, `tests/test_gui_home.py`

**Behaviour:**
- **Sidebar and Home** as in Global Constraints.
- **`run()` kinds:** `title` → title page (Task 5). `watch` → `actions.watch(...)`. `more` → `open_grid("more:…")`. The `home`, `grid`, `settings`, `search_*`, `phone_unpair`, `magnet` and `plugin_play` kinds are unchanged. The `play`, `episode`, `search`, `related` and MAL kinds are removed.
- **Grid de-duplication** uses `("title", …)` actions.
- **Long-press on a title card:**
  - My List add/remove;
  - Mark watched: movie (0, 0), or for a show every aired episode of the seasons TMDB lists;
  - Mark unwatched (confirm);
  - More like this.
- **`report()`:** `TmdbKeyMissing` → confirm 30423, then open Settings. `lists.ServiceMissing` → TorBox setup. Anything else → as before.
- **Settings menu:** unchanged (Settings, My TorBox).

- [ ] **Step 1: Write the failing tests:**
  - sidebar labels and targets
  - Home loads 4 rows and the hero from Trending
  - a grid click on a title card opens the title page with `(type, id)`
  - a watch card plays the `watch` URL with the resume value
  - long-press adds to My List and marks a movie watched
  - `test_missing_tmdb_key_asks_for_settings`
  - phone search still opens `search:<text>`
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: all pass, except title-page tests until Task 5.
- [ ] **Step 5: Commit** (`feat(gui): NovaFlix window for TV shows and movies`).

### Task 5: Title page with season picker; End episode returns here

**Files:**
- Rename: `gui/show.py` → `gui/title.py` (`TitlePage`, `open_title(media_type, tmdb_id, loader=None, start_ticker=True)`)
- Modify: `skins/Default/1080i/novaflix-show.xml` (button 503: `season_label`, visible when not empty), `gui/ids.py` (`SHOW_SEASON = 503`, replaces `SHOW_MAL`), `gui/actions.py`, `playback/monitor.py`, `views/home.py` (`launch`), `gui/app.py`
- Modify: `strings.po`: 30424 "Season %d", 30425 "Specials", 30426 "Play S%d E%d", 30427 "Not in English (%s)"
- Test: `tests/test_title_page.py` (replaces `tests/test_gui_show.py`), `tests/test_title_monitor.py`

**Behaviour:**
- **Header:** `cards.title_hero`. Genres. For a non-English original language, the `dub` property shows 30427 (the existing badge slot).
- **Buttons:**
  - Play/Resume: `next_up` within the current season, label 30426 or 30420.
  - My List toggle (501).
  - More like this (502; visible when recommendations or a collection exist).
  - Season (503, TV only): `dialogs.menu` of seasons 1..N, then specials last. Choosing one reloads the episode row in the background.
- **Opening season:** the season of the last watched episode (`WatchHistory.states`), else the first season with an aired episode, else 1.
- **Episode row:** `Library.episodes(title, season)` → `title_episode_card` with watched marks and resume progress. A click → resume prompt (`dialogs.resume_choice`), then `watch`. Long-press: mark watched/unwatched, or search again (`refresh=1`).
- **Movie:** one card (the film) with runtime. Play: 30235 "Play", or "Resume · 12:30 left".
- **End episode** (`monitor.py`): for a title, set `OPEN_SHOW_PROPERTY` to `"tv:1396"` / `"movie:438631"` before stopping. `actions.take_open_show()` returns `(media_type, tmdb_id)`. The app and title page open that page, as AniVerse did. Without the window open: `RunPlugin(launch?title=tv:1396)`.

- [ ] **Step 1: Write the failing tests:**
  - header and buttons for Breaking Bad and Dune
  - `test_season_choices_skip_missing_and_put_specials_last` (seasons 3, 1, 0 → "Season 1", "Season 3", "Specials")
  - the season switch reloads the episodes
  - the opening season follows history
  - an episode click with a resume point asks, then plays `watch?…&resume=…`
  - My List toggle
  - `test_end_episode_returns_to_title_page` (monitor sets "tv:1396"; the app opens title page tv 1396)
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`feat(gui): title page with season picker; End episode returns to it`).

### Task 6: Remove anime, MyAnimeList, Real-Debrid and the classic lists

**Delete:**
- `metadata/{anilist,anizip,animeschedule,aniskip,catalog,dubs,franchise,mal}.py`
- `myanimelist/` (move `relay.lan_address` and `relay.is_private` to a new `net/lan.py` first; the phone keyboard uses them)
- `sources/{nyaa,availability}.py`
- `storage/{history,favourites}.py` (move `WATCHED_AT` and `MIN_RESUME_S` into `storage/watching.py`)
- `views/{browse,show,history,listing,mylists,mal_account}.py`
- `debrid/{realdebrid,auth}.py`
- `pages/mal-login.html`
- the anime fixtures (`tests/fixtures/{anilist_*,anizip_*,animeschedule_*,mal_dubs,nyaa_*,torrentio_46474_3}.*`)
- every test file that only tests deleted code

**Modify:**
- `models.py`: keep `Candidate` only.
- `views/sources.py`: drop `choose`/`_choose`/`_find`/`_wanted`/`_cache_key`/`presearch`/`_last_choice` for anime. Keep `pick_source`, `details_line`, `_settings` (without `dub_only`/`nyaa_enabled`), `_report`, and the My TorBox views.
- `views/play.py`: drop `play_candidate`/`remember_choice`.
- `views/home.py`: `root` and `launch` open the window.
- `discovery.py`: drop the Nyaa and kitsu paths.
- `torrentio.py`: drop `url()` (kitsu).
- `playback/monitor.py` and `session.py`: titles only. `TitleSession` becomes `Session`. Drop AniSkip, MAL and the anime hand-off.
- `service_main.py`: drop MAL sync and dubs.
- `router.py`: routes `""`, `settings`, `launch`, `clear_cache`, `watch`, `rd/cloud`, `rd/torrent`, `rd/play`, `rd/add_magnet`.
- `settings.xml`: drop `novaflix_look`, `dub_only`, `nyaa_enabled` and the MAL category. The audio language options become English / Kodi default.
- `strings.po`: drop strings no code uses. A test checks that every string ID used in code and settings exists.
- `kodi/ui.py`: drop `styled()` and its branches.

- [ ] **Step 1: Write the failing tests first** in `tests/test_identity.py`:

```python
def test_no_anime_or_mal_code_left():
    # no file under plugin.video.novaflix contains: anilist, anizip, myanimelist, aniskip, nyaa, kitsu, real-debrid, realdebrid
def test_every_string_id_in_code_exists():          # ui.string(N) / label="N" ids all in strings.po
def test_only_title_routes():                       # router.ROUTES keys == the list above
```

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Delete and modify** as listed. Run the suite after each group of deletions.
- [ ] **Step 4: Run the full suite.** Expected: all pass.
- [ ] **Step 5: Commit** (`refactor: remove anime, MyAnimeList, Real-Debrid and classic lists`).

### Task 7: Release 0.2.0 and stick check

- [ ] **Step 1: Update `plugin.video.novaflix/addon.xml`:** version `0.2.0`. News: "0.2.0: TV shows and movies from TMDB. Seasons, Continue Watching, My List and More like this. Plays English releases through TorBox." `INSTALL.md`: the TMDB key step.
- [ ] **Step 2: Build.** Run `.venv\Scripts\python tools\build.py release`. Expected: `plugin.video.novaflix 0.2.0: added`. `script.novaflix` and `repository.novaflix` are unchanged.
- [ ] **Step 3: PC check (owner).**
  - Install with `tools\dev_kodi.py install`.
  - Home shows four rows and the hero.
  - Explore → Popular shows → Breaking Bad: Season picker → Season 2 → episode 3 plays.
  - Up next → S2 E4.
  - A movie from Trending plays.
  - My List add/remove.
  - Search "severance".
  - *Parasite* lists Korean releases, with the "No English audio track" heading.
- [ ] **Step 4: Ask the owner** in chat for approval. Then run `git push` and `.venv\Scripts\python tools\build.py publish`.
- [ ] **Step 5: Stick check (owner).**
  - Wait about 10 minutes after publishing; Kodi auto-updates NovaFlix.
  - Repeat the Step 3 checks on the stick.
  - Check that AniVerse still works.
