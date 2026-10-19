# Otaku feature inventory

Source: Goldenfreddy0703/Otaku HEAD 420666d, plugin.video.otaku v5.3.3 (read-only, nothing executed).
Path shorthand: `L/` = `plugin.video.otaku/resources/lib/`, `R/` = `plugin.video.otaku/resources/`, `CTX/` = `context.otaku/`.
Line numbers are from this checkout. "Relevance" notes are suggestions for a personal RD-first, Android TV, remote-driven add-on, not decisions.

Architecture in one paragraph: `default.py` calls `ui/router.py` (`Route` / `multi_route` decorators, prefix match, `router_process` at `ui/router.py:30-39`). All routes live in `L/Main.py`. One "browser" class is chosen at runtime by setting `browser.api` (`otaku` | `anilist` | `mal`, default `otaku`; `R/settings.xml`, lazy proxy at `L/MetaBrowser.py:9-33`). Every browser exposes the same method set (`get_trending_*`, `get_search`, `get_genres`, ...), so Main.py is API-agnostic. Titles map to a MAL id; the MAL id is the primary key everywhere (`/animes/<mal_id>/`).

---

## 1. Home screen and menus

**Main menu builder** `L/Main.py:222-243` (`_main_menu`) returns 19 fixed entries, label ids 30001-30019:
Airing Calendar (`airing_calendar`), Airing Last/This/Next Season, Movies, TV Shows, TV Shorts, Specials, OVAs, ONAs, Music, Trending, Popular, Voted, Favourites, Top 100, Genres & Tags, Search, Tools.
Dynamic extras, prepended by `_collect_category_menu_items` (`Main.py:1672-1692`): watchlist entries (one per logged-in service, `WatchlistIntegration.py:206-211`), Last Watched (`add_last_watched`, `Main.py:314`), Watch History (`add_watch_history`, `Main.py:380`), Next Up (`add_next_up`, `Main.py:307`).

**How toggled:** each menu is a `list[string]` multi-select setting listing allowed ids (`menu.mainmenu.config`, default `last_watched,watch_history,next_up,airing_calendar,airing_last_season,airing_this_season,airing_next_season,trending,popular,voted,favourites,top_100,genres,search,tools`; `R/settings.xml:2630-2660`). Movies/TV/etc. are hidden by default. A menu item shows only if its id is in the list (`Main.py:1689-1692`). Same pattern per format: `movie.mainmenu.config`, `tv_show.mainmenu.config`, `tv_short…`, `special…`, `ova…`, `ona…`, `music…` (`settings.xml` category "Menu Customization", lines 2627-3455, 8 groups x 3 settings), plus `*.submenu.config` for Trending/Popular/Voted/Favourites time-window submenus and `*.genres.config` for genre lists.

**Route registration** is table-driven: `_CATEGORY_MAIN_MENU_ROUTES` and `_FILTERED_SUBMENU_ROUTES` (`Main.py:1750-1826`) generate handlers with closures (`_register_ui_menu_routes`, `Main.py:1801`).

**Submenu structure** (`Main.py:130-180`): Trending/Popular/Voted/Favourites each expand to Last Year / This Year / Last Season / This Season / All Time (label ids 30020-30039). Each of the 8 format filters (all, movie, tv, tv_short, special, ova, ona, music) repeats the full tree, which is why there are hundreds of routes.

**Tools menu** `Main.py:252-267`: Setup Wizard, Change Log, Settings, Clear Cache, Clear Search History, Clear Watch History, Rebuild Database, Wipe Addon Data, Completed Sync, Download Manager, Sort Select, Clear Selected Fanart.

Notable: `interface.content_type` switches the container content type to `addons` for menus (`Main.py:1700-1702`). `Main.py` is ~2.4k lines largely because of per-format duplication.
Relevance: a personal add-on needs ~6-8 entries (Continue Watching, Search, Trending, Popular, Seasonal/Airing, Genres, History, Settings). Do not copy the 8-format x 5-window route explosion; use one route with a `format` param.

## 2. Search (incl. history)

- Search menu `Main.py:246-249`: 8 entries (Anime, Movie, TV Show, TV Short, Special, OVA, ONA, Music) routing to `search_history_<kind>`.
- `SEARCH_HISTORY` `Main.py:1063-1078`: reads `database.getSearchHistory(format)`; if setting `searchhistory == 0` (Yes) draws "New Search" + "Clear Search History..." + saved items (`ui/utils.py:108-116`), else goes straight to keyboard.
- `SEARCH` `Main.py:1122-1153`: prompts `control.keyboard` if no payload, saves to history (`database.addSearchHistory`), calls `BROWSER.get_search(query, page, format, prefix)`, draws as `tvshows`, prefetches next page in a thread (`control.schedule_next_page_prefetch`, `ui/control.py:698-716`).
- History storage: separate `search.db`, one table per type with `value TEXT UNIQUE` (`ui/database.py:675-730`). Context actions per history row: "Remove from Item", "Edit Search Item..." (`ui/utils.py:109`; handlers `Main.py:1081-1119`).
- AniList search: GraphQL `search` arg, sort `SEARCH_MATCH`, `format_in` filter (`AniListBrowser.py:284-309`). Adult search is a second query with `isAdult:true` and results tagged red "Adult" (`search.adult`, `AniListBrowser.py:296-305`). MAL/Otaku browser uses `/anime?q=` on the Tenrai/Jikan-style API (`MalBrowser.py:432`, `OtakuBrowser.py:456`).
- Notable: no fuzzy or alt-title logic client-side; matching is whatever the server does.
Relevance: Core. Keep keyboard + history list. Remote note: Kodi's on-screen keyboard is slow on a TV remote, so history re-use and "edit" are valuable.

## 3. Trending / popular / seasonal / airing / upcoming / recent

- AniList implementation: generic `_ranked_media_list` + `_browse_season_airing` (`AniListBrowser.py:150-185`). Sorts: trending -> `TRENDING_DESC`, popular -> `POPULARITY_DESC`, voted -> `SCORE_DESC`, favourites -> `FAVOURITES_DESC`, top100 -> `SCORE_DESC` (`:275-282`). Windows built from `get_season_year(period)` (`:89-119`) which also honours user-forced year/season settings (`contentyear.*`, `contentseason.*`). `year` is sent as a string prefix `"2026%"`.
- Airing last/this/next season = season + year filter (`:206-214`). There is no separate "upcoming" or "recent episodes" feed; "next season" is the upcoming view, and `status`=NOT_YET_RELEASED is only available as a global content filter (`contentstatus.*`).
- Every list call is cached for 24 h through `database.get(fn, 24, vars)` (`:145-148`).
- Pagination: `handle_paging` appends a "Next Page (n)" folder item with `?page=n` (`ui/BrowserBase.py:31-49`); widgets can hide it (`widget.hide.nextpage`). Page size settings `interface.perpage.general.anilist|mal` default 20.
- Next-page prefetch thread warms cache (`ui/control.py:698`).
Relevance: Core: Trending, Popular, This Season; Maybe: Top 100, Voted, Favourites; Skip: year/season-forcing UI.

## 4. Genre filters and sorting

- Genre menu `Main.py:181-219`, 19 preset genres (Action ... Thriller; `_GENRE_ROWS`, `:158-179`) plus a "Multi" entry (`genres//`).
- Preset genre: sorted by `POPULARITY_DESC`, page size from settings (`AniListBrowser.py:187-204`). Per-genre route handlers are generated (`Main.py:925-1017`, `_install_anilist_genre_methods` `AniListBrowser.py:1633`).
- Multi-genre + tags: `GENRES` route `Main.py:874-903`, `update_genre_settings` dialog (multiselect) persisted to `genres.json` (`Main.py:906-922`, `AniListBrowser.py:1594`). Uses AniList `includedGenres` / `includedTags`.
- Global content filters (apply to all lists): year, season, format, status, country of origin, genre, rating (MAL) in "Content Customization" (25 settings). Loaded in browser `__init__` (`AniListBrowser.py:58-73`).
- Sorting of **sources** (not catalog) is a separate custom window: `windows/sort_select.py` (`SortSelect`, 627 lines) and source filters (`windows/filter_select.py`); settings category "Sort and Filter" (25 settings, `settings.xml:1438-1795`).
Relevance: Core: preset genre list; Maybe: multi-genre + tags; Skip: global content-filter matrix.

## 5. Info pages (series detail)

- There is no custom info window for series. `animes/<mal_id>/` (`Main.py:521-525`) draws the episode list; Kodi's own Information dialog shows plot/rating/cast from `ListItem` info built in `base_anilist_view` (`AniListBrowser.py:1213-1323`): title (romaji/english per `titlelanguage`), description with HTML->Kodi tags, genre, status, premiered/year, cast (top 10 characters + Japanese VAs), studio, rating (`averageScore/10`) + votes from score distribution, duration, trailer (`plugin://plugin.video.youtube/play/?video_id=` or dailymotion).
- Movie detection: `episodes == 1` -> URL `play_movie/<mal_id>/`, mediatype movie (`:1317-1320`). Shows without `idMal` are dropped silently (`:1219`).
- Extra info windows: Reviews (`Main.py:488-614`, text viewer `windows/textviewer.py`) and Statistics (`windows/stats_window.py`, `Main.py:511-518, 616-627`), both AniList or Jikan sourced.
Relevance: Core: rely on Kodi's native info dialog with good ListItem tags. Skip: reviews/statistics windows.

## 6. Posters, fanart, clearlogo, banner, landscape, clearart

- Poster = AniList `coverImage.extraLarge` (or MAL image). Merged artwork (fanart, thumb/landscape, clearart, clearlogo, banner) stored per show in `shows_meta.art`; fetched by `ui/get_meta.py` (`update_meta` `:62-205`, `merge_artwork` `:208-287`).
- Providers: Fanart.tv, TMDB, TVDB in parallel (`ThreadPoolExecutor`), selected by `artwork.preference` (0 Fanart, 1 TMDb, 2 TVDB, 3 all). Banner prefers AniList `bannerImage`. Title-search fallback if ID lookup returns nothing (`artwork.titlesearch`, `get_meta.py:129-190`). Details in `metadata_analysis.md`.
- Per-type toggles: `artwork.fanart|clearlogo|clearart|banner|landscape`, `artwork.fanart.count` (12 settings in "Artwork Customization").
- Fanart picker: context "Select Fanart" -> `Main.py:1635-1668`, stores choice in settings string lists `fanart.mal_ids` / `fanart.selections`.
- Missing art falls back to poster / addon fanart (`windows/base_window.py:61-70`, `Main.py:1243-1244` style fallbacks).
- Fetch happens during list draw (`collect_meta`, `get_meta.py:23-60`), up to `os.cpu_count()` threads, so first view of a new list is slow.
Relevance: Core: poster + fanart; Maybe: clearlogo (nice on TV skins); Skip: per-type toggles and fanart picker.

## 7. Episode lists

- `MetaBrowser.get_anime_init` (`L/MetaBrowser.py:35-90`) returns episodes for a MAL id. Fallback chain when `override.meta.api` is off: Simkl -> ani.zip -> Jikan -> AniDB -> Kitsu (`:62-83`). Setting `meta.api` can force one (including the merged `otaku` indexer which queries 5 providers in parallel, `indexers/otaku.py:376-440`).
- Each episode row: title, plot, thumb, aired date, rating, season, playcount from watchlist progress (`eps_watched`), "code" second label with filler/dub info (`indexers/__init__.py:9-17`, `update_database:76-98`).
- Stored in `episodes` table (pickled ListItem dict). Refresh for airing shows after `interface.check.updates` days (default 5; `indexers/__init__.py:get_diff`, `anizip.py:append_episodes`); finished shows are never refetched.
- Options: hide unaired (`interface.aired_episodes`, `indexers/__init__.py:should_hide_unaired_episode`), hide titles/plots as spoilers (`interface.cleantitles`), dub airing info (TeamUp or AnimeSchedule, `indexers/__init__.py:process_dub`), filler flags from animefillerlist.com scrape when >99 eps (`endpoints/anime_filler.py`).
- Smart scroll: after drawing, focuses the first unwatched episode via `Container.TotalWatched` / `Control.SetFocus` (`ui/control.py:742-775`, setting `general.smart.scroll.enable`). This is a TV-remote nicety.
Relevance: Core: episode list with thumb/title/plot/aired; Core-ish: smart-scroll to next unwatched; Skip: filler/dub badges.

## 8. Season navigation and ordering

- The add-on does NOT model "Show > Season N > Episodes". Every MAL entry (each season/cour/movie/OVA) is its own top-level show with episodes numbered 1..N (`indexers/anizip.py:72`, one `season` value per entry).
- To navigate between seasons users use "Find Relations" (`Main.py:539-543`, `AniListBrowser.py:320-325`, relations list excluding `ADAPTATION`, `:1188-1199`) or "Get Watch Order" (`Main.py:545-549`; AniList impl scrapes `chiaki.site/?/tools/watch_order/id/<mal_id>`, `AniListBrowser.py:327-357`).
- A season number is still computed for torrent queries: DB `thetvdb_season` else regexes on titles (`ui/utils.py:134-172`).
Relevance: central design choice for the user's add-on. Options: keep "one MAL/AniList entry = one folder" (simplest, matches AniList) or build a franchise tree on top. Needs a decision.

## 9. Context menus (context.otaku)

`CTX/addon.xml` declares 12 global items, each visible only if (a) a home-window property mirrors the setting and (b) `ListItem.Path` starts with `plugin://plugin.video.otaku/` and (c) DBTYPE matches:
Find Recommendations, Find Relations, Get Watch Order, View Reviews, View Statistics (tvshow/movie); Marked as Watched [WatchList] (episode/movie, not while playing); Rescrape; Source Select; Logout; Delete From Database; WatchList Manager; Select Fanart (`CTX/addon.xml:8-52`).
Dispatch in `CTX/default.py:main` (builds `Container.Update(...)` or `RunPlugin(...)`; Rescrape / Source Select copy the focused item's tags into URL params and call `PlayMedia(path?source_select=true|rescrape=true)`).
Settings toggles are cached into Window(home) properties by `ui/control.py:process_context` (`:381-404`), "Context Customization" category (12 settings).
Notable: this is a separate addon, so it adds install dependency; context menu key on Android TV remote is long-press OK.
Relevance: Core: Source Select / Rescrape via context (or an in-plugin item). Prefer building actions into the plugin using `ListItem.addContextMenuItems` to avoid a second addon.

## 10. Settings (summary of `R/settings.xml`)

Roughly 360 `<setting>` elements within 10 categories (371 raw `<setting ` tags; 4,000-line file). Counts per category:
General 65 (Setup Wizard 3, General Customization 17, Metadata 4, Content 25, Artwork 12, Widgets 2, Misc 2); Providers 16 (Torrents 8, Hosters 1, Embeds 7); Scraping 11; Playback 28 (incl. FFprobe, Skip Intro, Playing Next dialogs); Sort and Filter 25; Accounts 39 (Real-Debrid, Premiumize, AllDebrid, Debrid-Link, TorBox, EasyDebrid, Easynews); Watchlist 31 (AniList, Kitsu, MAL, Simkl, Trakt); Menu Customization 24; Context Customization 12; Maintenance 109 (cache, InputStream Adaptive, language invoker, Cloudflare solver, Megacloud solver, network IPv6/HTTP2, import/export).
Notable: Setup Wizard (`Main.py:2132-2296`) sets `browser.api` etc. Dialog theme `general.dialog` picks one of 7 skin-matched XML sets (`Default`, Arctic Horizon 2, AuraMod, Arctic Fuse, Arctic Fuse 2, Arctic Zephyr Reloaded, Titan Bingie Mod; values 5 and 6 use `_alt` XMLs, `Main.py:1188-1214`).
Relevance: a personal add-on needs about 15-25 settings (RD token, title language, per-page, quality prefs, autoplay vs select, cache clear).

## 11. Custom windows and skins

Python in `L/windows/`, XML in `R/skins/Default/1080i/` (~38 XML files; 7 dialog themes for playing_next/skip_intro/skip_outro).
| Window | File | Purpose |
|---|---|---|
| GetSources | `windows/get_sources_window.py`, `get_sources.xml`/`_alt` | Scrape progress: counts by quality (4K/1080/720/SD/EQ), provider list, % bar |
| SourceSelect | `windows/source_select.py`, `source_select.xml` | Manual source list: list id 1000, button 15 cycles views (both, cached, uncached, embeds); props: provider, quality, size, seeders, debrid |
| Resolver | `windows/resolver.py`, `resolver.xml` | Resolving progress; tries next source on failure (`general.autotrynext`) |
| Anichart | `windows/anichart.py`, `anichart.xml` | Weekly airing calendar grid |
| SortSelect / FilterSelect | `windows/sort_select.py`, `filter_select.py` | Source sort priority and filters |
| DownloadManager | `windows/download_manager.py` | Download queue UI + `Manager` class (threads, `downloads.json`) |
| PlayingNext, SkipIntro/Outro | `windows/playing_next.py`, `skip_intro.py` | Overlays during playback |
| WatchlistFlavorAuth | `windows/wlf_auth.py` | PIN/OAuth display (+QR) |
| StatsWindow, TextViewer, Progress_dialog | misc | Stats, reviews text, generic progress with cancel (ids 3002/3003/3005/4001) |
`BaseWindow` (`windows/base_window.py`) loads show meta and sets window properties `item.art.fanart|poster|clearlogo|thumb`, `item.info.title|plot|rating` for skins.
Relevance: Core: SourceSelect (manual selection is a hard requirement) and a scrape/resolve progress indicator. Consider native `xbmcgui.Dialog().select` first (remote-safe, no XML) and a custom window only if rich columns (quality/size/seeders/cached) are wanted.

## 12. Loading indicators, progress dialogs

- Busy dialog closed by `control.closeBusyDialog()` (`ui/control.py:124`); `closeAllDialogs` after directory draw (`:496`). Scrape progress is the GetSources window with properties updated per provider (`get_sources_window.py:update_properties`). Silent mode skips the window (`silent` actionArg).
- Generic `Progress_dialog` XML window with cancel button and optional QR image (`windows/progress_dialog.py:1-39`) used for debrid auth etc.
- `xbmcgui.DialogProgress` instance exists (`control.py:115`).
Relevance: Core: scrape progress + cancel; use `DialogProgressBG` or `DialogProgress` to avoid custom XML.

## 13. Error messages and notifications

- `control.notify(title, text, icon, time=5000)` toast (`ui/control.py:515`), `ok_dialog` (`:499`), `yesno_dialog` (`:507`), `multiselect_dialog` (`:523`), `context_menu` list popup (`:531`). Examples: "Failed to remove search item" (`Main.py:1090`), "Please Select A Debrid File" (`windows/source_select.py`), invalid year notice (`AniListBrowser.py:106`).
- Network failures are generally swallowed: AniList path returns None -> empty list; Otaku browser logs "MAL API request failed" and returns `[]` (`OtakuBrowser.py:73-80`). No user-visible "API down" message in most paths.
- Logging via `control.log` with levels.
Relevance: Core: a small set of toasts (no sources found, RD error, API unreachable). Improve on Otaku by surfacing "metadata service unreachable" instead of silent empty lists.

## 14. Caching and pagination

- Three-tier `database.get(fn, hours, ...)` cache (`ui/database.py:166-207`): Kodi window property (RAM, `_mem_get/_mem_set` `:105-123`) -> SQLite `cache.db` (key = md5 of function+args) -> live call. Listings cache 24 h; AniList enrichment 168 h (`database.py:638`); show/episode rows live in `malSync.db` (`shows`, `shows_meta`, `episodes`, `show_data`, `watchlist_cache`, `watchlist_activity`, `anilist_enrichment`, `activities`; `ui/database_sync.py:54-190`). Clear Cache tool and Rebuild Database (`database_sync.py:297-322`).
- Pagination: server pages of 20 (setting), "Next Page" item, background prefetch of next page.
- `cacheToDisc=True` on every directory (`control.py:728`).
Relevance: Core: SQLite cache + TTL; Maybe: RAM tier; the prefetch thread is a cheap win.

## 15. Remote-control behavior (custom windows)

Action ids used raw: 92 (ACTION_NAV_BACK) and 10 (PREVIOUS_MENU) close windows (`source_select.py:135`, `resolver.py:486`, `progress_dialog.py:30`, `sort_select.py:447`, etc.). 7 (SELECT_ITEM) and 100 (MOUSE_LEFT_CLICK) select the focused row when `getFocusId()==1000` (`source_select.py:141`). 117 (CONTEXT_MENU, long-press OK) opens a popup "Play / Download / File Select" (`source_select.py:145-176`, also download manager `:42`). Anichart handles NAV_BACK, SELECT, TOUCH_TAP, MOUSE_DOUBLE_CLICK, 117 (`windows/anichart.py:69-113`). Initial focus is forced with `setFocusId(1000)` in `onInit` (`source_select.py:61-72`, `anichart.py:56`, `sort_select.py:442`). Button 15 cycles list filter via `onClick`. Closing source select clears playlist (`control.playList.clear()`).
Notable: no dedicated left/right/page handling; navigation relies on skin XML `<onleft>/<onright>` wiring. TV-skin theme choice is a user setting because dialogs must visually match the skin.
Relevance: Core: BACK/SELECT/CONTEXT mapping and explicit initial focus are the minimum for TV remote.

## 16. Watchlist integrations (REMOTE TRACKING, flag)

`L/WatchlistFlavor/`: AniList (GraphQL `graphql.anilist.co`), MyAnimeList (`api.myanimelist.net/v2`, OAuth), Kitsu (`kitsu.io/api`), Simkl (`api.simkl.com`, PIN), plus Trakt via the separate `script.trakt` (property `script.trakt.ids` set during playback, `ui/player.py:224-228`). Features: login/logout (`WatchlistIntegration.py:23-37`), status lists, progress updates on playback, sync cache (24 h), Next Up from watchlist (`:43-60`), watchlist manager context. Requires accounts, tokens, and ID translation (mal -> kitsu/anilist/simkl via mapping DB, with fallbacks to `armkai.vercel.app` and `find-my-anime.dtimur.de`, `WatchlistFlavorBase.py:395-435`).
All of this is remote tracking and conflicts with the "local-only history" requirement.
Relevance: Skip entirely.

## 17. Watch order, relations, recommendations

- Recommendations: AniList `Media.recommendations` (`AniListBrowser.py:311-318, 819-917`), paged.
- Relations: AniList relations excluding ADAPTATION, relation type appended in green to the title (`:919-1008`, view `:1188`, title tag `:1226-1228`).
- Watch order: HTML scrape of chiaki.site (`:327-357`) -> MAL ids -> AniList lookups. Fragile (scraper) and slow (one query per id, cached 24 h).
Relevance: Maybe: Relations is cheap (one AniList query) and is the practical way to reach sequels; Skip: chiaki scrape.

## 18. Local history, Last Watched, Continue

- Local-only pieces (relevant to the user): `watch_history.json` (`Main.py:415-486`, route `watch_history/` `Main.py:629-722`; saved when playback starts, `ui/player.py:239`; last-10 shown in menu `:380`), `addon.last_watched` setting + Last Watched menu item with art (`Main.py:314-377`), `completed.json` (watched marks, `BrowserBase.open_completed`, plays set `playcount=1`), resume point prompt "Resume from HH:MM:SS / Play from beginning" (`Main.py:1195-1202`). Episode "watched" otherwise comes from remote watchlist `eps_watched` or Kodi's own playcount.
- Playback end handling `ui/player.py:116-143`, watched-percent threshold `:173-195`.
Relevance: Core: this is the local-only model to simplify (single JSON or SQLite table: mal_id, episode, position, updated).

## 19. Playback flow, auto-play, skip intro, next-up

- `PLAY` `Main.py:1156-1257`: load episode meta (fetch if missing), optional resume prompt, scrape (`MetaBrowser.get_sources`, `MetaBrowser.py:93-128`), then either SourceSelect window or Resolver auto-pick depending on `general.playstyle.episode` (1 = select), SmartPlay (`general.smartplay`: reuse last source for same series), or forced select/rescrape from context.
- Next-episode playlist (`ui/player.py:build_playlist`), Playing Next dialog, Skip Intro/Outro with AniSkip (`endpoints/aniskip.py`: `api.aniskip.com/v2/skip-times/<mal_id>/<ep>`), Anime-Skip GraphQL, and ffprobe chapter detection (`ui/ffprobe_chapters.py`).
Relevance: Core: select-or-autoplay, resume; Maybe: next-episode autoplay; Skip: skip-intro stack.

## 20. Download manager

`windows/download_manager.py:102-326` `Manager` (chunked download to `download.location`, status in `downloads.json`, speed/ETA display) + window (cancel, clear complete). Triggered from SourceSelect context popup "Download" (`source_select.py:154-171`) with a resolved debrid link (EasyDebrid unsupported; local files rejected).
Relevance: Skip for v1.

## 21. Schedule (airing calendar)

`L/AnimeSchedule.py` (1057 lines) + `endpoints/animeschedule.py` (`https://animeschedule.net/api/v3`, bearer token embedded in `context.otaku/info.db` client_secret) feeds the `Anichart` window (`Main.py:736-750`). Supports sub/dub/raw timetables, countdowns, stream links, MDBList ratings (`endpoints/mdblist.py`, `https://api.mdblist.com`), cache file `animeschedule_calendar.json`. Separate older calendar sources (Simkl `data.simkl.in/calendar/anime.json`, Jikan schedules) are commented out in `service.py:46-51`.
Relevance: Maybe: a simple "Airing This Season" list covers 80%; Skip the grid UI.

## 22. Background service and maintenance

`service.py`: on start `SyncDatabase()`, refresh API tokens, mappings DB refresh every 30 days (`service.py:316-324`, downloaded from `github.com/Goldenfreddy0703/Otaku-Mappings`), dub JSON (MAL-Dubs) + watchlist sync every 7 days, 1-day tasks; `onSettingsChanged` reloads settings. Maintenance settings include Cloudflare/DDoS-Guard solver and Megacloud solver (scraper evasion).
Relevance: Maybe: mappings refresh service; Skip: solvers.

---

## Summary table (suggested v1 relevance is a suggestion, not a decision)

| Feature | Complexity | External service | Suggested v1 relevance |
|---|---|---|---|
| Home menu (6-8 fixed entries) | Low | none | Core |
| Per-format x per-window menu matrix | High (hundreds of routes) | none | Skip |
| Menu show/hide via settings list | Medium | none | Maybe |
| Search + local history | Low-Med | AniList (or MAL proxy) | Core |
| Trending / Popular / Seasonal lists | Low | AniList | Core |
| Voted / Favourites / Top 100 | Low | AniList | Maybe |
| Airing calendar grid (Anichart) | High | AnimeSchedule (token), MDBList | Skip |
| Genre presets | Low | AniList | Core |
| Multi-genre + tags dialog | Medium | AniList | Maybe |
| Global content filters | Medium | AniList | Skip |
| Series info via native Kodi dialog | Low | AniList | Core |
| Reviews / Statistics windows | Medium | AniList/Jikan | Skip |
| Poster + fanart | Low | AniList cover; TMDB/Fanart.tv/TVDB for fanart | Core (poster), Maybe (fanart) |
| Clearlogo/clearart/banner/landscape | Medium | Fanart.tv, TMDB, TVDB | Maybe |
| Fanart picker | Low | none | Skip |
| Episode list w/ thumbs, plot, aired | High (5 providers) | Simkl, ani.zip, Jikan/Tenrai, AniDB, Kitsu | Core (1-2 providers) |
| Smart scroll to next unwatched | Low | none | Core |
| Hide unaired / spoiler-free titles | Low | none | Maybe |
| Filler / dub badges | Medium | animefillerlist.com scrape, TeamUp, AnimeSchedule | Skip |
| Season/relations navigation | Medium | AniList | Core (needs design decision) |
| Watch order | Medium | chiaki.site scrape | Skip |
| Recommendations | Low | AniList | Maybe |
| Context menu addon | Medium | none | Maybe (prefer in-plugin context items) |
| Source Select window | Medium-High | none | Core |
| Scrape progress window | Medium | none | Core |
| Resolver (auto-try-next) | Medium | Real-Debrid | Core |
| Sort/Filter sources windows | High | none | Maybe (simple quality sort in settings) |
| Multiple debrid providers | High | RD, AD, PM, TB, DL, EasyDebrid, Easynews | Skip (RD only) |
| Hosters/embeds scrapers + solvers | Very high | many sites | Skip |
| Torrent scrapers (Nyaa, AnimeTosho, nekoBT, Torrentio) | High | those sites | Core (1-2) |
| Local watch history / last watched / resume | Low-Med | none | Core |
| Watchlist sync (AniList/MAL/Kitsu/Simkl/Trakt) | Very high | all four + OAuth | Skip (remote tracking) |
| Next Up (watchlist based) | Medium | watchlist services | Skip |
| Skip intro/outro, Playing Next | High | AniSkip, Anime-Skip, ffprobe | Maybe (Playing Next only) |
| Download manager | High | RD links | Skip |
| 3-tier cache (RAM/SQLite) | Medium | none | Core |
| Next-page prefetch | Low | none | Maybe |
| Setup wizard | Medium | none | Skip |
| Background service (mappings refresh) | Medium | GitHub | Maybe |
| Import/Export settings | Low | none | Skip |
