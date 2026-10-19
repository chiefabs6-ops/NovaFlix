# Otaku metadata analysis

Source: Goldenfreddy0703/Otaku HEAD 420666d, plugin.video.otaku v5.3.3 (read-only; no code executed). `L/` = `plugin.video.otaku/resources/lib/`, `R/` = `plugin.video.otaku/resources/`.
Labels: CONFIRMED = read in code or fetched from official docs; ASSUMPTION = inferred or unverified.
Two separate systems are described: (A) METADATA providers (what a show/episode is, art, IDs) and (B) MEDIA-SOURCE discovery (scrapers/debrid that find a playable file). Section 9 shows where B consumes A's output.

---

# PART A: METADATA

## 1. Provider map (base URLs from code)

| Provider | Base URL (code) | Role | Required? |
|---|---|---|---|
| AniList GraphQL | `https://graphql.anilist.co` (`L/endpoints/anilist.py:6`, `L/AniListBrowser.py:56`, `L/OtakuBrowser.py:564`) | Catalog, search, relations, recommendations, cover/banner, characters; enrichment | Required if `browser.api` = anilist or otaku (default otaku) |
| "MAL API" = Tenrai (Jikan v4-schema compatible) | `https://api.tenrai.org/v1` (`L/ui/control.py:78`; comment at `:73-77` says Jikan was swapped for Tenrai) | Catalog/search/seasons/top, per-anime info, episodes list (`/anime/<id>/episodes`) | Required for `browser.api` = mal or otaku |
| Jikan (legacy name) | indexer `L/indexers/jikanmoe.py:17` now points at the same Tenrai URL; has client-side throttle (3 req / 1 s, `:19-31`) | Episode meta fallback | Optional |
| Simkl | `https://api.simkl.com` (`L/indexers/simkl.py:14`), images `https://wsrv.nl/?url=https://simkl.in/episodes/%s_w.webp` (`:15`) | Episode titles/plots/thumbs, `alt_titles`, ID lookup `/search/id` | Optional; FIRST in default episode chain |
| ani.zip | `https://api.ani.zip` `GET /mappings?mal_id=` (`L/indexers/anizip.py:13-21`) | Episode meta incl. `anidbEid`, `seasonNumber`, EN titles, images; also a mapping source | Optional; 2nd in chain |
| AniDB HTTP API | `http://api.anidb.net:9001/httpapi` (`L/endpoints/anidb.py:6`, `L/indexers/anidb.py:15`) | Episode list/titles; episode ids (`anidb_ep_id`) used for AnimeTosho | Optional (client name embedded) |
| Kitsu | `https://kitsu.io/api/edge` (`L/indexers/kitsu.py:14`) | Episode meta fallback | Optional; last in chain |
| TMDB | `https://api.themoviedb.org/3/`, images `image.tmdb.org/t/p/w500` & `/original` (`L/endpoints/tmdb.py:5-7`) | Artwork (backdrops, posters, logos); title search for ID discovery | Optional |
| TVDB v4 | `https://api4.thetvdb.com/v4` (`L/endpoints/tvdb.py:5`), art host `artworks.thetvdb.com` | Artwork (types 2/3/22/23 series; 14/15/24/25 movie, `:75-80` comments); title search | Optional |
| Fanart.tv | `https://webservice.fanart.tv/v3` (`L/endpoints/fanart.py:5`) | Artwork: TV via TVDB id, movies via TMDB id (`:13`) | Optional |
| MDBList | `https://api.mdblist.com` `/mal/any?apikey=` (`L/endpoints/mdblist.py:17,64`) | Ratings for calendar only (`L/AnimeSchedule.py:621`) | Optional (calendar) |
| MAL Sync | `https://api.malsync.moe/mal/anime/<id>` (`L/endpoints/malsync.py:3-14`) | Site slugs/titles for streaming-site scrapers (gogoanime, zoro, animepahe) | Scraper support, not metadata |
| AnimeSchedule | `https://animeschedule.net/api/v3` (`L/endpoints/animeschedule.py:8`) | Calendar, dub times (also HTML scrape) | Optional |
| Chiaki | `https://chiaki.site/?/tools/watch_order/id/<id>` (HTML scrape, `L/AniListBrowser.py:328`) | Watch order | Optional |
| animefillerlist.com | `L/endpoints/anime_filler.py:6` (scrape) | Filler flags | Optional |
| TeamUp / MAL-Dubs | `api.teamup.com` (`endpoints/teamup.py:11`); `raw.githubusercontent.com/MAL-Dubs/MAL-Dubs/main/data/dubInfo.json` (`service.py:176`) | Dub info | Optional |
| Mapping DB (GitHub) | `https://github.com/Goldenfreddy0703/Otaku-Mappings/raw/refs/heads/main/anime_mappings.db` (`plugin.video.otaku/service.py:56`) | Cross-ID mapping (see section 5) | Effectively REQUIRED: art, season, scrapers all read it |
| Legacy ID fallbacks | `https://armkai.vercel.app/api/search`, `https://find-my-anime.dtimur.de/api` (`L/WatchlistFlavor/WatchlistFlavorBase.py:403, 423`) | Per-flavor ID lookup for watchlist sync | Remote-tracking only |
| AniSkip / Anime-Skip | `api.aniskip.com/v2/skip-times/<mal>/<ep>` (`endpoints/aniskip.py:6`), `api.anime-skip.com/graphql` | Skip times | Optional, not metadata |

MAL itself (`api.myanimelist.net/v2`, `L/WatchlistFlavor/MyAnimeList.py:12`) is used only for watchlist OAuth, not for catalog.

### Which catalog backend is active
`browser.api` setting (`otaku` default, `anilist`, `mal`; `R/settings.xml`, selected in `L/MetaBrowser.py:9-23`). Three browsers share one method surface:
- `AniListBrowser`: AniList GraphQL only; hits with no `idMal` are dropped (`AniListBrowser.py:1219`).
- `MalBrowser`: Tenrai/Jikan-shaped REST (`MalBrowser.py`).
- `OtakuBrowser` (default): list/search from Tenrai, then batch-enrich from AniList by `idMal_in` (`OtakuBrowser.py:563-680`), cached via `anilist_enrichment` (7 days, `ui/database.py:638`, `endpoints/anilist.py:get_enrichment_for_mal_ids`).
MAL id is the universal primary key in every table and URL (`animes/<mal_id>/`).

## 2. API keys and secrets (values not printed)

Not in .py source. All keys/client ids live in a SQLite file shipped with the context addon: `context.otaku/info.db`, table `info(api_name, api_key, client_id, client_secret, description)`, read via `database.get_info(name)` (`L/ui/database.py:462-465`, path `L/ui/control.py:72`). Present in that file (CONFIRMED by inspecting column presence only):
- api_key present: Fanart-TV, TMDB, Teamup, MDBList, TVDB.
- client_id present: MyAnimeList, Debrid-Link, Anime-Skip, AniDB, AnimeSchedule, Simkl, Real-Debrid, Premiumize, Trakt.
- client_secret present: AnimeSchedule (used as bearer token, `L/AnimeSchedule.py:29`), Trakt.
- AniList GraphQL and Tenrai/Jikan need NO key for these calls (no auth header in `endpoints/anilist.py` or `MalBrowser.get_base_res`). AniList/Kitsu/MAL/Simkl user tokens are user-supplied via OAuth/PIN (watchlist only).
- Real-Debrid client id is embedded (`L/debrid/real_debrid.py:10-11`), i.e. RD uses the open-source/device-code client flow. Not metadata but relevant: user RD token is still per user.
Implications for the user's add-on: they must register their OWN TMDB, Fanart.tv (personal key), TVDB, and Simkl client id; do not reuse Otaku's embedded keys (shared, rate-limited, and not licensed for reuse). AniList and Tenrai/Jikan need none.

## 3. Catalog / search operations

AniList queries (all `POST` GraphQL, `Page(page, perPage)` pagination):
- Lists: `get_base_res` (`AniListBrowser.py:601`) vars `type, format_in, countryOfOrigin, season, year (string "2026%"), includedGenres, includedTags, status, sort`.
- Search: `get_search_res` (`:715`) `search`, `sort: SEARCH_MATCH` (`:284-291`), optional second adult query (`:296`).
- Single: `Media(idMal:, type:ANIME)` (`:1010`, cached 24h `:593-599`).
- Relations (`:919`), recommendations (`:819`), reviews (`:395`), stats (`:431`).
- Batch enrichment by `idMal_in` (`endpoints/anilist.py:9-100`) and banners (`endpoints/anilist.py:240`).
Fields requested: `id, idMal, title{romaji,english}, coverImage.extraLarge, bannerImage, startDate, description, synonyms, format, episodes, status, genres, duration, countryOfOrigin, averageScore, characters(10)+JP voice actors, studios, nextAiringEpisode, trailer, stats.scoreDistribution` (`endpoints/anilist.py:16-77`). NOTE: `native` title and `season`/`seasonYear` are not requested; `synonyms` is requested but not stored in `kodi_meta`.
Tenrai/Jikan-shaped REST: `/anime` (filters `type, status, rating, genres, order_by, sort, start_date, end_date, sfw`), `/seasons/{year}/{season}`, `/top/anime`, `/anime/{id}`, `/anime/{id}/episodes`, `/anime/{id}/relations`, `/anime/{id}/recommendations`, `/anime/{id}/reviews`, `/anime/{id}/statistics` (`MalBrowser.py:186-282`, `jikanmoe.py:34-60`, `OtakuBrowser.py:553`).
Caching of all list/search calls: `database.get(fn, 24 hours)` (`AniListBrowser.py:147`, `MalBrowser.py:196`).

## 4. Titles and alt-title matching

- Display: `title_userPreferred = res['title'][lang] or romaji`, language chosen by `titlelanguage` (0 romaji, 1 english; default 1) (`AniListBrowser.py:58-59, 1331`). MAL variant uses `title` / `title_english`.
- Stored `kodi_meta` (pickled) keys: `name` (romaji), `ename` (english), `title_userPreferred`, `start_date`, `query`, `episodes`, `status`, `format`, `plot`, `duration`, genre/cast/studio/rating/trailer (`AniListBrowser.py:1344-1368`).
- `query` is a ready-made scraper search string: `"(<romaji>)|(<english>)"` (`:1337-1346`). Torrent scrapers use this OR pattern; there is no synonym or native-title list. Colons are stripped as a retry when no results (`L/pages/nyaa.py:30-37`).
- No fuzzy alt-title matching in the add-on. Alt titles used in only two places: Simkl `alt_titles` and Otaku `titles` to infer a season number from text (`indexers/simkl.py:60`, `indexers/otaku.py:382-383` -> `ui/utils.py:134-172`).
- Title-based ID discovery only for artwork: TMDB `search/tv|movie` first hit and TVDB search first hit (`endpoints/tmdb.py:55-72`, `endpoints/tvdb.py:23-40`), triggered when ID art returned nothing (`ui/get_meta.py:129-190`). First-hit matching is unverified for correctness (risk of wrong art).
- NekoBT scraper resolves its media id by title search then matches TVDB id (`L/pages/nekobt.py:35-70`).

## 5. Cross-provider ID mapping and what replaced script.otaku.mappings

**Old:** addon `script.otaku.mappings` (bundled `resources/data/anime_mappings.db`, schema keyed by `anilist_id`; I extracted the last committed copy to inspect: 7,656 rows). **Deleted in commit `f550be6` dated 2025-09-11** ("Updated Version v5.0.1 to v5.2.45", CONFIRMED via `git log --diff-filter=D -- script.otaku.mappings`). Earlier history: local DB first, fallback to armkai (commit `c6d958a` "Use local mapping database first, fallback to armkai if needed"; `2c50526` "add local anime_id mapping database").
**Now:** a SQLite DB downloaded by the service from the separate GitHub repo `Goldenfreddy0703/Otaku-Mappings`, file `anime_mappings.db` (`service.py:54-63`), saved to the add-on profile as `mappings.db` (`L/ui/control.py:84`). Refresh: first run and every 30 days (`service.py:315-324`) and on "Rebuild Database" (`ui/database_sync.py:306`). Failure is logged only (`service.py:62-63`); there is no bundled fallback copy, so a first-run offline start has no mappings (CONFIRMED by reading code; consequence is inference).
I downloaded the current file to inspect schema (public, not executed): **31,182 rows**, table `anime`:
`mal_id PK, mal_dub_id, anilist_id, kitsu_id, anidb_id, simkl_id, thetvdb_id, themoviedb_id, imdb_id, trakt_id, mal_title, mal_picture, thetvdb_season, thetvdb_part, duration, score, status, anime_media_type, global_media_type, anime_media_episodes, global_media_episodes`, unique indexes on mal, anilist, kitsu, anidb, simkl. Sample rows (verified): Naruto Shippuuden mal 1735 -> tvdb 79824, tmdb 31910, `thetvdb_season='a'`, episodes '1 - 500'; Attack on Titan mal 16498 -> tvdb 267440, season 1, part 1; Frieren mal 52991 -> anilist 154587, tvdb 424536, season 1.
Lookups: `database.get_mappings(id, column)` (`ui/database.py:424-429`, any of the indexed columns), `get_unique_ids` returns `mal_id, mal_dub_id, anilist_id, kitsu_id, anidb, simkl, tvdb, tmdb, imdb, trakt` for `UniqueIDs` on ListItems (`:432-452`). `meta_ids` stored in `shows_meta.meta_ids` is the whole mapping row (`get_meta.py:update_meta`, `database.py:324`).
Gap handling: `shows` table also has `anilist_id, simkl_id, kitsu_id` columns filled lazily (`database.add_mapping_id`, `:342`); Simkl `/search/id?mal=` fills simkl_id on demand (`indexers/simkl.py:165-175`); watchlist code can fall back to armkai/find-my-anime (`WatchlistFlavorBase.py:395-435`). ASSUMPTION: unmapped new shows (very recent releases) have no tvdb/tmdb id until the monthly DB update, so no Fanart.tv art unless title search succeeds.
Other mapping-capable APIs (not used as primary): ani.zip `/mappings`, Simkl ids, AniDB.

## 6. Season / episode identification, specials, movies, cours

- Model: one MAL id = one "season-like" entry with episodes 1..N (CONFIRMED: `indexers/anizip.py:72-77` builds numbered episodes for the single MAL id; `episodes` unique index is `(mal_id, season, number)`, `database_sync.py:121-124`).
- Season number (for display and torrent queries): `ui/utils.py:134-172`: (1) `thetvdb_season` from mapping DB; value `'0'` or `'a'` (absolute) returns 1; (2) regex on titles `season N`, `Nth season`; (3) trailing number unless title contains "part"/"cour"; (4) default 1, and values > 10 become 1. Show-wide default for the episode row `season` is thus the TVDB season of that MAL entry.
- Part / split-cour: `thetvdb_part` from mapping DB is passed to scrapers (`MetaBrowser.py:57-62`) and to the torrent filter, which also parses `part N` / `cour N` out of release names (`ui/source_utils.py:481`).
- Absolute numbering: `thetvdb_season == 'a'` marks long-running shows indexed absolutely on TVDB (e.g. Naruto Shippuuden). For those, `filter_sources` sets `season=None` so only the episode number is compared (`source_utils.py:458-464`). Not fully general (ASSUMPTION: shows with 'a' but where MAL splits entries may mis-number).
- Movies/OVAs/specials: each is its own MAL entry. Detection: `episodes == 1` and format in MOVIE/ONA/OVA/SPECIAL -> `play_movie/<mal_id>/` (`AniListBrowser.py:1317-1320`), artwork type 'movies' (`get_meta.py:35-38`), scraper movie path uses a different search category (Nyaa `c=1_2`, `pages/nyaa.py:142-150`). Multi-episode OVAs/ONAs treated like TV.
- Specials inside a show's episode list are DROPPED by two providers: Simkl filter `type == 'episode'` (`indexers/simkl.py:67`), ani.zip `isdigit()` keys only (`anizip.py:72`), AniDB episode ids `isdigit()` (`pages/animetosho.py:57`). Special entries (S1, C1...) are therefore not shown; users reach them via Relations/Watch Order as separate MAL entries.
- Unaired/airing: `nextAiringEpisode` requested but status string and `get_diff` age (default 5 days, `interface.check.updates`) decide refresh; unaired episodes optionally hidden by `aired` date (`indexers/__init__.py:should_hide_unaired_episode`). When the requested episode exceeds the provider's max for an ongoing show, Next Up marks `not_yet_aired` (`MetaBrowser.py:get_next_up_meta` end).
- Episode source of truth precedence: default chain Simkl > ani.zip > Jikan > AniDB > Kitsu; the first non-empty wins (`MetaBrowser.py:62-83`). With `meta.api=otaku`, AniDB base list, else Simkl, else Jikan, with fields merged from all five (`indexers/otaku.py:376-460`).

## 7. How episode number maps to torrent queries (system B consuming A)

Inputs gathered in `MetaBrowser.get_sources` (`MetaBrowser.py:93-128`): `query` (`"(romaji)|(english)"`), `mal_id`, per-entry `episode` (1-based within the MAL entry), `episodes` total, `status`, `duration`, `season` (from `episodes.season`), `part` (mapping DB). Nyaa builds (`pages/nyaa.py:41-85`):
- primary: `<query> "- 07"|"S01E07"` (zero-padded), sorted by downloads;
- batch (only if status FINISHED): `<query> "Batch"|"Complete Series"|"01-07"|...|"S01"|"Season 01"|"S01E07"|"- 07"`, sorted by seeders;
- fallback same as primary unsorted; plus a base-title-without-"season" search.
All run in parallel. Results then pass `source_utils.filter_sources` (`:452-756`), which regex-extracts season/part/episode (including ranges like `01-12` and `sXXeYY`) from each torrent name, keeps ones that contain the requested episode, then debrid cache check. AnimeTosho uses AniDB ids (`aids=<anidb_id>`) and episode id lookups (`pages/animetosho.py:41-105`); Torrentio uses `kitsu:<kitsu_id>:<ep>` (`pages/torrentio.py:51-55`); NekoBT uses TVDB-derived media id (`nekobt.py:35`).
So: relative episode numbering per MAL entry is what scrapers receive; release groups commonly name by absolute or per-season numbers, so the batch queries and regex filter are the compensation. ASSUMPTION: split-cour releases numbered absolutely (e.g. ep 13 for cour 2 ep 1) will be missed unless `thetvdb_season='a'` handling applies.

## 8. Artwork retrieval and fallback

`ui/get_meta.py` (`collect_meta` 23-60, `update_meta` 62-205, `merge_artwork` 208-287):
1. Skip shows already in `shows_meta`. `movies` type vs `tv` type chosen at `:35-38`.
2. Batch AniList banners (`artwork.banner`) (`endpoints/anilist.py:240`).
3. Fetch per `artwork.preference` (Fanart.tv / TMDb / TVDB / all in parallel). Fanart.tv: TV needs `thetvdb_id`, movies need `themoviedb_id`; languages `['en','ja','']`; clearlogo prefers the title-language logo (`fanart.py:6-9,44-75`). TMDB: uses `themoviedb_id`, or `find/{tvdb_id}?external_source=tvdb_id` (`tmdb.py:11-27`); `include_image_language=en,ja,null`; backdrops -> fanart, posters -> thumb, logos -> clearlogo. TVDB v4 login + `/series/{id}/artworks`.
4. Merge: fanart lists concatenated and truncated to `artwork.fanart.count`; thumb = first; clearart & clearlogo = random pick; banner = AniList banner else provider banner.
5. If no fanart and no thumb: title-search TMDB and TVDB, then re-fetch (`:129-190`, setting `artwork.titlesearch` default true).
6. Display fallbacks: poster = AniList `extraLarge`; `fanart` = merged fanart else the poster (`AniListBrowser.py:1304`); window skins fall back to the add-on fanart/logo (`windows/base_window.py:61-95`).
Stored in `shows_meta.art` (pickle) permanently (no TTL; cleared by Rebuild Database or Delete From Database).
Episode thumbs come from the episode provider (Simkl `img` via wsrv.nl, ani.zip `image`, etc.) else the poster (`anizip.py:parse_episode_view`).

## 9. Caching and refresh (tables and TTLs)

| Store | Location | TTL / refresh | Ref |
|---|---|---|---|
| Listing/search/single-show API cache | `cache.db` table `cache(key,value,date)` + RAM (Window(10000) properties) | 24 h per call (hardcoded `database.get(..., 24, ...)`) | `ui/database.py:105-207` |
| `shows` (kodi_meta blob, ids, anime_schedule_route) | `malSync.db` | no TTL; created on first view | `database_sync.py:77-92` |
| `shows_meta` (meta_ids = mapping row, art blob) | `malSync.db` | no TTL | `:94-106` |
| `episodes` (kodi_meta blob, season, number, filler, anidb_ep_id, last_updated) | `malSync.db` | airing shows re-fetched when older than `interface.check.updates` days (default 5); FINISHED shows never | `:108-125`, `anizip.py:append_episodes` |
| `show_data` (dub info) | `malSync.db` | daily (compared with `date.today()`) | `indexers/__init__.py:process_dub` |
| `anilist_enrichment` | `malSync.db` | 168 h | `database.py:621-660` |
| `watchlist_cache`, `watchlist_activity` | `malSync.db` | 24 h | remote tracking |
| `mappings.db` | profile dir | replaced every 30 days | `service.py:316-324` |
| `mal_dub.json` | profile dir | every 7 days | `service.py:173-183` |
| `search.db` | profile dir | permanent history | `ui/database.py:675-730` |
| JSON: `genres.json, sort_options.json, watch_history.json, completed.json, downloads.json, embeds.json, animeschedule_calendar.json` | profile dir | n/a | `ui/control.py:86-93` |
Schema version check: `activities.otaku_version` vs add-on constant triggers menu/embed defaults update (`database_sync.py:205-272`).

## 10. Missing / conflicting metadata handling

- No MAL id on AniList entry: entry silently skipped (`AniListBrowser.py:1219`). Hence AniList-only shows never appear.
- Provider returns nothing: fall through the chain; if all fail episode list is `[]` and `get_anime_init` returns an empty list (no message) (`MetaBrowser.py:83-86`).
- Missing episode title: `Episode N` (`anizip.py:parse_episode_view`).
- Conflicts between providers are not reconciled except in the `otaku` indexer which merges fields by precedence (AniDB/Simkl/Jikan/ani.zip/Kitsu, `indexers/otaku.py:239-374`). ASSUMPTION: episode counts may differ across providers (a commented-out length check at `anizip.py:67-70` shows the author considered and disabled it).
- Failed API call: caller returns None; Otaku browser logs and returns empty list (`OtakuBrowser.py:73-80`). No retry/backoff except fixed sleeps: MAL fetch retries 3x with 100/200/300 ms (`MalBrowser.py:268-276`), burst sleep 1 s every 3 requests (`:278`), calendar retry loop with 1 s sleeps (`endpoints/mal.py:27-41`).
- HTTP layer: 20 s default timeout, Cloudflare/DDG challenge solving, TLS retry (`ui/client.py:165-181, 424-491`).

## 11. Rate limits

From code (CONFIRMED): Jikan indexer limits itself to 3 requests per rolling second (`indexers/jikanmoe.py:19-31`); MalBrowser sleeps 1 s every 3 requests in loops (`MalBrowser.py:278`); calendar fetch sleeps 1 s every 3 pages (`endpoints/mal.py:39-41`). There is NO AniList rate-limit handling and no 429/Retry-After logic in browsers or `endpoints/anilist.py` (grep of those files for 429/rate/Retry-After found none). Parallelism is `os.cpu_count()` threads (`ui/control.py:43`) which can burst many AniList/artwork calls.

External, official:
- AniList: official docs at https://docs.anilist.co/guide/rate-limiting (WebFetch returned 403; content obtained through web search snippet of that page). Statement: normal limit 90 requests/minute; exceeding gives a 1-minute timeout with `Retry-After` and `X-RateLimit-Reset`; a separate burst limiter exists; **the page currently says the API is in a degraded state limited to 30 requests/minute**, not reflected in headers. Status: 90/min = CONFIRMED as documented baseline; 30/min degraded = CONFIRMED as currently stated by docs via search result, but could not verify by direct fetch or on what date (ASSUMPTION that it is still in force today; check `X-RateLimit-Limit` header live).
- Jikan (3 req/s, 60 req/min): ASSUMPTION. Direct fetch of https://docs.api.jikan.moe/ returned only the title (JS app), the jikan-rest GitHub page has no numbers, and the search returned no Jikan page. The 3/s value is only confirmed as what Otaku's own code assumes (`jikanmoe.py:19`). Note Otaku no longer calls jikan.moe but the Tenrai host (https://api.tenrai.org/ doc page loads only a title, "Tenrai API v1 Docs"); Tenrai limits are UNKNOWN.
- Simkl, ani.zip, Kitsu, AniDB, TMDB, TVDB, Fanart.tv limits: not checked (ASSUMPTION: AniDB's HTTP API is strict, bans on bursts; Otaku caches AniDB episode data in DB so it is fetched once per show).

## 12. Notes for the user's add-on design (suggestions, not decisions)

- Minimum viable metadata stack: AniList (catalog/search/relations/art/title variants; no key; 90/min baseline) + the Otaku-Mappings DB (or another mapping source such as ani.zip) for MAL/AniList/Kitsu/AniDB/TVDB/TMDB ids + one episode provider (ani.zip needs no key and returns `anidbEid`, `seasonNumber`, EN titles, images) + optional TMDB/Fanart.tv for fanart/logos.
- Decide the franchise model early: Otaku's "one MAL entry = one folder, episodes 1..N" avoids absolute/season conflicts and matches how AniList/MAL split cours, but pushes sequel navigation into Relations.
- Keep AniList-without-MAL-id shows (Otaku drops them); store `anilist_id` as primary if MAL ids are not needed.
- Store alt titles (`romaji`, `english`, `native`, `synonyms`) in the DB and build torrent queries from them; Otaku uses only romaji+english.
- Bundle a snapshot mapping DB so first run works offline; add 429 handling with Retry-After for AniList.
- Unresolved: Tenrai terms/limits and permanence; whether the 30/min AniList degradation persists; whether Otaku-Mappings license permits reuse of its DB (not checked).
