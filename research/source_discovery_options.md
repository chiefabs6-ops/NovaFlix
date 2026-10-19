# Media-Source Discovery Options for a Personal Kodi Anime Add-On (Real-Debrid)

Date of research: 2026-10-10. Scope: how the add-on finds *candidate sources* (magnets, hashes, links). Out of scope: anime metadata (AniList etc.) and playback resolution, except where they interact.

Labels: **CONFIRMED** = read in code or fetched from a primary page this session. **ASSUMPTION** = inferred, from secondary sources, or not verifiable here.

Otaku paths below are relative to `plugin.video.otaku/resources/lib/` in the read-only clone.

---

## 0. Key facts that shape every option

1. **Real-Debrid is not a catalog.** It accepts a magnet/torrent/hoster link and returns files. CONFIRMED by API doc: `POST /torrents/addMagnet`, `PUT /torrents/addTorrent`, `POST /torrents/selectFiles/{id}`, `GET /torrents/info/{id}`, `GET /torrents`, `POST /unrestrict/link`, `GET /downloads` (https://api.real-debrid.com/). Otaku wraps exactly these in `debrid/real_debrid.py:174-208`.
2. **No cheap cache check.** The official API page lists no `instantAvailability` endpoint (CONFIRMED absence, https://api.real-debrid.com/). Its removal in late 2024 is reported by TorrentFreak and ElfHosted (https://torrentfreak.com/real-debrid-implements-extreme-anti-piracy-filters-to-appease-film-companies-241122/ , https://store.elfhosted.com/blog/2024/11/22/stremio-after-realdebrid/) - secondary sources, treat as CONFIRMED-by-reports. I could not confirm whether it was ever restored; the API page does not list it (so assume still absent).
   - **Impact:** you cannot ask "is hash X instantly available?" before adding. The only reliable test is to `addMagnet` + `selectFiles` + `GET /torrents/info` and look at `status` (`downloaded` = was cached; `downloading`/`magnet_conversion`/`waiting_files_selection` = not). That consumes a slot in the user's torrent list and counts against the active-download cap (error code 21 "Too many active downloads"; API doc). Rate limit 250 req/min, 429 on excess (API doc).
   - Otaku works around it with third-party signals, not RD: `debrid/debrid_cache.py:76-87` (Torrentio probe + Debrid Media Manager availability), cached 24 h in SQLite (`debrid_cache.py:21,49-60`). **Do not copy as-is:** it embeds a third-party RD token in a Torrentio URL (`debrid_cache.py:112`), a reverse-engineered DMM anti-bot "solution" (`debrid_cache.py:216-254`), and a demo API key/config blob for a third-party AIOStreams instance (`debrid_cache.py:127-165`). These are fragile, arguably ToS-violating toward those services, and a privacy/security smell.
3. **RD content filtering, May 2026.** ElfHosted reports RD began rejecting playback of many cached torrents by filename/release-tag keywords around 2026-05-10 (errors like `File was removed from debrid service due to copyright infringement`); RD has not commented publicly; ElfHosted is a commercial vendor so treat as ASSUMPTION-grade (https://store.elfhosted.com/blog/2026/05/12/real-debrid-filtering-may-2026/). **Impact:** even a "found + cached" source may fail at unrestrict time. Design for per-source failure and easy fall-through to the next source.
4. **RD ToS (https://real-debrid.com/terms):** accounts are personal; no account/link sharing; users acknowledge not using the service to download copyright-infringing files; RD disclaims responsibility for user downloads; no use of dedicated server/VPS/cloud beyond remote traffic. The fetched text does not address third-party API apps. Consequence: a design that runs on the user's own device with their own token is on safest ground; a shared/hosted helper that uses one person's RD token for others is not.
5. **AnimeTosho is effectively dead for new content.** CONFIRMED from its own pages: ingestion of new torrents halted ~2026-05-09; feed/storage server expires in October 2026 ("all feeds and API requests will stop working"); the website is planned to close May 2027 and runs as an archive in the meantime (https://animetosho.org/about/shutdown2 and notice on https://animetosho.org/). Today is 2026-10-10, so treat AnimeTosho as unavailable. Otaku still ships `pages/animetosho.py` (scrapes HTML: `animetosho.py:191-217`), which will break.
6. Otaku scrapes HTML for both Nyaa and AnimeTosho (BeautifulSoup selectors, `nyaa.py:162-171`, `animetosho.py:191-200`), not RSS/JSON. That is the fragile way; Nyaa has a documented-by-practice RSS feed (see option 3).

---

## 1. Option 1 - User's own Real-Debrid account only

**What it discovers:** only what the user already has in RD: `GET /torrents` and `GET /downloads` (hoster links). No discovery of anything new.

**How Otaku does it (`pages/debrid_cloudfiles.py`):** `rd_cloud_inspection` lists torrents (`:36-37`), filters (`:38`, `source_utils.filter_sources` at `ui/source_utils.py:452`), fuzzy-matches the title against torrent filenames (`:39-40`, `get_fuzzy_match` `source_utils.py:325`), then per candidate calls `torrentInfo` (`:44`), keeps selected files (`:45`), skips multi-file torrents with only one link (`:47-48`), requires a valid video extension (`:50`). At play time `resolve_cloud` (`real_debrid.py:210-218`) picks the file via `get_best_match` (`source_utils.py:422-445`) and maps file index to `torrent_info['links'][idx]` (a known RD gotcha: `links` only covers *selected* files, so index must be over selected files; Otaku does this at `real_debrid.py:216-218`).

**Episode matching:** by filename regex. `get_cache_check_reg` (`source_utils.py:277-293`) accepts episode zero-padded to 2/3/4 digits after `e|x|ep|_|-|(`. If several files match, the user is prompted (`source_utils.py:442-443`); if none match, returns `{}`. Batch packs work (match inside pack's file list). Weak on absolute numbering (a "Season 2" pack numbered 25-48), specials, and titles with numbers.

**Extra service:** none beyond RD.

**Manual source selection:** yes, trivially (list of matching cloud items; user-selected file inside packs).

**RD interaction:** read-only list + `torrents/info` + `unrestrict/link`. No add. Cheapest and fastest. Performance caveat: Otaku's `list_torrents` (`real_debrid.py:181-185`) sends no `limit`/`page`; the API doc says list endpoints are paginated (limit max 5000) - ASSUMPTION that default page is 100 (doc shows 100 default for `/downloads`), so large libraries need paging.

**Unavailable/uncached:** n/a - everything listed is already in the account. Items with status != `downloaded` must be hidden or shown as "downloading".

**Dependencies/maintenance:** minimal, only RD REST (stable, documented). Low burden.

**Legal/privacy:** neutral; user supplies content. Only RD token stays on device. RD can still reject files (point 3 above).

**Failure modes:** nothing found for unseen shows; RD auto-expiry/deletion of old torrents; filename fuzzy-match false positives; library paging.

**Complexity: S.**

## 2. Option 2 - User-curated input (paste magnet / hoster link, or add on RD website, then list)

**What it discovers:** exactly what the user provides. Variants: (a) user adds on real-debrid.com/torrents then falls to Option 1; (b) add-on offers "Add magnet" (Kodi keyboard/clipboard dialog; on Android TV, typing a 40-char hash is painful) or accepts a magnet/link via a small helper (phone web page, Kodi's JSON-RPC/`script` call, or a share-intent target). (c) Paste a hoster URL then `unrestrict/link` directly.

**Episode matching:** after `addMagnet` -> `selectFiles` (`all` or just video files) -> `torrents/info`, the same filename-regex matching as Option 1 (Otaku `resolve_single_magnet`, `real_debrid.py:220-255`; it also deletes the torrent afterwards, `:254`). Reliability same as Option 1, but the user chose the pack on purpose, so it is higher in practice.

**Extra service:** none (optional phone-side helper UI; this adds a tiny local HTTP server or a hosted page - the latter would be an extra service, keep it local).

**Manual source selection:** inherent.

**RD interaction:** full flow `addMagnet` -> `selectFiles` -> `info` -> poll status until `downloaded` -> `unrestrict/link` (Otaku `resolve_uncached_source`, `real_debrid.py:279-354`, polls every 5 s in a progress dialog, `:312-328`). Magnet from the user means the user decides to take the cache-miss risk, so no cache-check problem arises. Note Otaku's loop at `:312` has no overall timeout beyond user cancel.

**Unavailable/uncached:** shows progress or lets the user "download in background" (`:307-309`). Dead torrents sit at `magnet_conversion`/`downloading` at 0 seeders; clean up via `DELETE /torrents/delete/{id}`.

**Dependencies/maintenance:** very low. Needs a mapping store (which magnet belongs to which anime/episode) if you want it to appear under the show; otherwise it is just a "my links" list.

**Legal/privacy:** neutral; user fully responsible for what they paste. No third party sees queries.

**Failure modes:** user effort; remote-input friction on TV; RD blocking filenames; duplicates in RD list.

**Complexity: S** (add-magnet dialog + file picker) to **M** (phone helper + show-to-link mapping).

## 3. Option 3 - Public torrent indexers with feeds/APIs (Nyaa RSS, AnimeTosho, nekoBT)

### 3a. Nyaa (nyaa.si)
- **Discovers:** broadest anime torrent index: individual episodes, season/batch packs, raws, dubs, many fansub groups.
- **API:** RSS 2.0 at `https://nyaa.si/?page=rss&q=<query>&c=<cat>&f=<filter>` - CONFIRMED live this session; items carry `title`, `link` (`/download/<id>.torrent`), and `nyaa:infoHash`, `nyaa:seeders`, `nyaa:size`, `nyaa:categoryId` in namespace `https://nyaa.si/xmlns/nyaa`. The help page only shows an "RSS" nav link; no formal API, params, or rate-limit docs (https://nyaa.si/help) - so params are de facto, not documented (ASSUMPTION they are stable). Otaku does *not* use RSS; it scrapes HTML (`nyaa.py:158-175`, base URL `nyaa.py:12`, with a Google-Translate proxy-mirror variant for blocked regions).
- **Episode matching:** text search only. Otaku issues 4 parallel queries per episode (`nyaa.py:45-114`): `show "- 05"|"S01E05"`, a batch query (`:57-73`), fallback, season variant; then `filter_sources` regex-filters season/episode/part/range (`source_utils.py:452-680`). Reliability: good for weekly-release groups using " - 05"; poor for absolute vs seasonal numbering, title aliases (romaji/English/Japanese), `Part 2`/cour splits, batch ranges. This is the hardest part of the whole add-on, and it is entirely heuristic. Torrent-level only, so inside a batch you still need Option 1's file matching.
- **Extra service:** none (public site). A mapping layer for titles/aliases and per-season episode offsets (from the metadata side: AniDB/TVDB/AniList) improves hit rate; Otaku leans on AniDB IDs for AnimeTosho (`animetosho.py:42-59`).
- **Manual selection:** yes, list with title/size/seeders.
- **RD interaction:** you get an infoHash -> must `addMagnet` (build `magnet:?xt=urn:btih:<hash>`) to test availability. No pre-check (point 2). Strategy: sort by seeders/size, show all, label "cache unknown", add only on user pick. Otaku shows "uncached" only if seeders > 0 (`nyaa.py:182`).
- **Uncached:** user waits or cancels; RD downloads at its own speed if seeded.
- **Maintenance:** moderate. HTML scraping is brittle; RSS is steadier. Nyaa has had outages/DDoS periods and regional blocks (ASSUMPTION; Otaku's proxy-mirror setting at `nyaa.py:12` suggests blocks occur).
- **Legal/privacy:** Nyaa lists content of varying copyright status, including unlicensed fansubs and rips of licensed anime. User is responsible for lawful use. Queries go to Nyaa from the user's IP (consider RD does not hide that).
- **Failure modes:** query returns nothing for alt titles; wrong season/pack picked; RD filename filter (note many Nyaa releases carry tags such as `WEB-DL`, `CR`, `WEBRip` that May-2026 reports say are rejected - ASSUMPTION); site down.
- **Complexity: M** (search + heavy episode matching).

### 3b. AnimeTosho
- **Discovers:** same ecosystem (mirrors Nyaa plus own ingest), with AniDB IDs (`aids` param, `animetosho.py:75`) which gave good per-episode matching.
- **Status: shut down for new content (CONFIRMED, see 0.5).** Ingestion halted 2026-05-09; feed server expiring October 2026; site closing May 2027. A 1.01 TB data dump exists (https://animetosho.org/about/data) but is not a live feed. The site named successor/alternative indexers ("Anime Tosho NEW", NextTosho, TsukiHime, Otakuness) on the shutdown page; I did not evaluate them (ASSUMPTION they have usable APIs).
- I could not locate any documented JSON API page (https://animetosho.org/api returned 404; `feed.animetosho.org` was unreachable from here, though the homepage lists `https://feed.animetosho.org/atom` and `/rss2`). The earlier "JSON API" the task mentions is therefore UNVERIFIED. **Recommend: do not build on AnimeTosho.**
- Complexity if included anyway: S-M, but pointless.

### 3c. nekoBT
- Otaku has a JSON client (`pages/nekobt.py:10`: `https://nekobt.to/api/v1`; `/media/search`, `/media/{id}`, `/torrents/search`, `nekobt.py:48,73,104`). Matches by TVDB ID to a media ID then episode IDs (`:35-100`), a structured approach better than text search. Not authenticated in the code I saw (grep for api key/Authorization found none - CONFIRMED absence in that file). Newer, smaller index; the site's long-term stability and ToS were not verified (ASSUMPTION). Complexity M.

## 4. Option 4 - Stremio-addon-protocol aggregators (Torrentio, Comet, MediaFusion, Jackettio, AIOStreams)

**How it works:** `GET <base>/[config/]stream/<type>/<id>.json` returns `{streams: [...]}`. Stream ids are IMDb (`tt0898266:9:17`) per Stremio SDK docs (https://raw.githubusercontent.com/Stremio/stremio-addon-sdk/master/docs/api/requests/defineStreamHandler.md; the page does not define stream-object fields, so `infoHash`, `fileIdx`, `behaviorHints` details are from Otaku's use, not from that page).

**Kitsu support for anime (CONFIRMED in Otaku):** Torrentio is called with `/stream/series/kitsu:<kitsu_id>:<episode>.json` and movies `/stream/movie/kitsu:<id>.json` (`pages/torrentio.py:54,90`), where the Kitsu id comes from a MAL->Kitsu mapping (`torrentio.py:28-34`). So the episode is a *Kitsu-relative episode number*, which means the aggregator, not you, does absolute/seasonal reconciliation, with whatever quality that has. Comet lists Kitsu/anime support (https://github.com/g0ldyy/comet; page states "Kitsu support is listed as an anime feature").

**What it discovers:** whatever the addon's scrapers index; Comet lists Jackett, Prowlarr, Zilean, Torrentio, MediaFusion, **Nyaa**, BitMagnet, AIOStreams scrapers, DMM hashlist ingester, and "debrid account scraper" (searches your debrid library) (same Comet page). Torrentio's configure page lists NyaaSi among providers (https://torrentio.strem.fun/configure).

**Episode matching:** per-episode streams returned directly; each stream has `infoHash`, optional `fileIdx` (which file in a pack) and `behaviorHints.filename` (Otaku reads this at `torrentio.py:146`). That is the most reliable episode-level mapping of any option, because `fileIdx` + filename let you pick the right file in a batch without guessing. Otaku still post-filters (`torrentio.py:71`). Quality depends on the aggregator's Kitsu mapping.

**Extra service:** a third-party hosted endpoint (Torrentio public instance, hosted Comet/MediaFusion instances) or your own self-hosted instance (Comet runs from source with `uv` or Docker; Docker setups use a database and reverse proxy per one secondary source - ASSUMPTION on resource needs, the Comet page gave no requirements).

**Manual selection:** yes - you get a list of streams and present them. Mandatory manual selection is easy because you control the UI (unlike Stremio's auto-pick).

**RD interaction:** two modes. (i) *Torrent-only mode:* configure the addon with no debrid, take `infoHash`(+`fileIdx`), then do your own `addMagnet` -> `selectFiles` -> `info` -> `unrestrict`. This is what Otaku does (`torrentio.py:20-23,145`; no RD key sent in the main request). Cache status unknown (point 2). (ii) *Debrid-configured addon:* user's RD key is put in the addon's config URL; the addon returns `url` for streams it considers cached. That sends the user's RD key to the addon operator (privacy risk for third-party hosts; fine for self-hosted). Hosted-IP vs your-IP concurrency also matters: RD terms disallow simultaneous multi-IP use, which is why hosted addons offer proxying (https://store.elfhosted.com/blog/2024/11/22/stremio-after-realdebrid/ ; secondary).

**Unavailable/uncached:** Torrentio returns many uncached hashes; Otaku hides those with 0 seeders and optionally shows them (`torrentio.py:77-84`).

**Torrentio ToS/status:** I found **no ToS or rate-limit text** on https://torrentio.strem.fun/configure (CONFIRMED absence) and could not confirm the public instance's 2026 health or any blocking policy (ASSUMPTION: it can change or rate-limit without notice; it is a community-run free service). The GitHub repo (`TheBeastLT/torrentio-scraper`) is Apache-2.0 per its page; the README excerpt I got did not cover usage terms. Stremio Docs: no formal protection for non-Stremio clients either way.

**Maintenance burden:** low code (one JSON GET) but **high dependency risk**: a hosted instance can vanish, throttle, or drop providers; Otaku code at `torrentio.py:10` hardcodes the base URL. Mitigate: make base URL configurable; allow multiple aggregator URLs (Torrentio, Comet) and merge by infoHash (Otaku dedups by hash+debrid, `torrentio.py:188-210`).

**Legal/privacy:** Torrentio/Comet index public torrent sites incl. content of mixed copyright status; user responsible. Your Kitsu id + IP go to the operator; a debrid key goes too in mode (ii).

**Failure modes:** instance down/429; Kitsu mapping missing (Otaku skips: `torrentio.py:32-34`); wrong season offset; RD filtering; hosted-addon policy changes.

**Complexity: S** (client) to **M** (config, dedup, multiple instances, Kitsu mapping). Self-hosting adds **L** ops work.

## 5. Option 5 - Self-hosted Jackett / Prowlarr (user-configured)

**What it discovers:** whatever indexers the user enables (Nyaa.si is on Jackett's public list per https://github.com/Jackett/Jackett, but no Nyaa-specific steps on that page; Prowlarr docs mention "over 500 trackers" and Generic Torznab; https://github.com/Prowlarr/Prowlarr).

**API:** Torznab. Jackett pattern, CONFIRMED from its README: `http://127.0.0.1:9117/api/v2.0/indexers/<name|all>/results/torznab/api?apikey=<key>&t=search&q=...`, `t=caps` lists supported modes. Torznab also defines `tvsearch` with `season`/`ep`/ids; whether anime trackers honor them is indexer-dependent (ASSUMPTION - the Jackett page did not specify this).

**Episode matching:** same as Option 3 (text) unless the indexer supports ids. Same heuristics needed.

**Extra service:** a Jackett/Prowlarr instance: Windows installer/service, Docker (recommended), Jackett README says nothing about Android (CONFIRMED), so on Android TV/Fire TV it must run on another machine (PC, NAS) on the LAN. That is a real extra moving part for a personal TV add-on.

**Manual selection:** yes.

**RD interaction:** identical to Option 3 (hash -> addMagnet; no pre-check).

**Unavailable:** same.

**Dependencies/maintenance:** high compared with Option 3: indexer definitions break, Cloudflare challenges (Prowlarr lists Flaresolverr per-indexer proxy support), "too many requests can result in being banned by tracker sites" (Jackett README). Upside: one stable local API for the add-on, indexer breakage handled upstream, privacy (queries leave the user's own server).

**Legal/privacy:** user's own indexer selection; same copyright caveat; public vs private trackers (private trackers have their own rules and ratio requirements, and sending those to RD is usually against their rules - ASSUMPTION).

**Failure modes:** server offline when TV is on; LAN address/API key setup on TV remote; indexer breaks.

**Complexity: M** (client) plus **L** user setup.

## 6. Option 6 - Usenet (Easynews)

Out of scope for Real-Debrid: it needs an Easynews subscription, not RD. Otaku has `pages/easynews.py` and `debrid/easynews.py` (members.easynews.com, `debrid/easynews.py:24`; merged as hoster 'cached_only' in `pages/__init__.py:21-23,202-203`). Matching is title-token based with broadened queries (`easynews.py:13-100`). Pros: direct HTTP streaming, no cache problem. Cons: separate paid service and credentials, less anime coverage, Usenet legal/copyright considerations same as torrents. Not recommended for this add-on unless the user already has it. Complexity M.

## 7. Option 7 - Direct-stream website scrapers (hianime, animepahe, etc.)

Otaku embed modules: `pages/__init__.py:30-37` (animepahe, animix, hianime, anikoto, watchnixtoons2; aniwave and animekai commented out at `:33,35`). Example: hianime base `https://hianime.ms/` (`hianime.py:15`), with an embed extractor (`hianime.py:358`). **No RD involvement.** Discovers whatever the site hosts; per-episode matching by the site's own episode lists (high reliability when the site maps correctly); multi-sub/dub toggles; skip-intro metadata (`__init__.py:235-247`). Cons: scrapers break whenever the site changes markup, domains rotate (note the hardcoded `.ms` mirror), embed extractors rot, ad/tracker exposure, and these sites commonly host content without a license (ToS/legality questionable - the user is responsible; this is likely a worse legal footing than torrent search because the site itself serves the stream). Also contrary to the stated product design (RD playback, manual selection among RD sources). **Recommend excluding.** Complexity L (high maintenance).

---

## Comparison table

| # | Option | Finds new content | Episode match | Pre-cache knowledge | Extra service | Manual select | Maintenance | Legal/privacy exposure | Complexity |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Own RD account | No (only owned) | Filename regex; ok | n/a (already cached) | None | Yes | Low | Lowest | S |
| 2 | User-pasted magnet/link | No (user brings) | Filename regex after add | User accepts risk | None (opt. phone helper) | Yes | Low | Lowest | S-M |
| 3a | Nyaa RSS | Yes, broad | Heuristic text; weak on absolute/part | No | None | Yes | Medium | Index of mixed-status content | M |
| 3b | AnimeTosho | Frozen archive only (dead 2026) | AniDB ids were good | No | None | Yes | Dead | n/a | not advised |
| 3c | nekoBT API | Yes, smaller | TVDB-id media, better | No | None | Yes | Medium (new site) | Mixed | M |
| 4 | Torrentio/Comet/MediaFusion | Yes, broad (multi-indexer) | Per-episode streams, `fileIdx`/filename; best | No (unless debrid-configured) | Hosted instance or self-host | Yes | Low code, high dependency risk | Mixed content; RD key leak if configured | S-M (L if self-host) |
| 5 | Jackett/Prowlarr | Yes, user-chosen | Heuristic text | No | Own server (LAN) | Yes | High setup, low upstream | Mixed; user-controlled | M + user L |
| 6 | Easynews | Yes (Usenet) | Heuristic | n/a | Paid Easynews | Yes | Medium | Mixed | M |
| 7 | Website scrapers | Yes | Site lists; good | n/a (no RD) | None | Yes | Very high | Weakest (unlicensed hosts, ads) | L |

---

## Cross-cutting design notes (no code)

- **Separate three layers in the add-on:** (a) discovery providers return a normalized candidate `{info_hash, title, size, seeders, source_name, file_hint?}`; (b) a matcher decides which *file* in a torrent is the target episode; (c) the RD resolver does addMagnet/selectFiles/info/unrestrict. Otaku mixes cache-check into providers (`nyaa.py:179`, `torrentio.py:74`); keeping them separate lets you swap providers when one dies (AnimeTosho just did).
- **Matching:** keep an episode-number map per show (relative, absolute, TVDB/AniDB season offsets) from the metadata layer; accept multiple candidate numbers per request. Otaku's single regex (`source_utils.py:277-293`) matches `-05`, `E05`, `_05`, and `(05` but would also hit resolution/bit-depth tokens, so strip bracket tags first (Otaku does: `source_utils.py:427`). For packs, prefer `fileIdx`/`behaviorHints.filename` when an aggregator provides it.
- **Cache unknown:** present all candidates; mark "unverified"; on pick, run add flow with a progress dialog, a timeout (Otaku has none, `real_debrid.py:312`), and cleanup (`deleteTorrent`) on failure/cancel. Keep a small local record of hashes that previously resolved or failed (like Otaku's 24 h SQLite, `debrid_cache.py:21`) to reorder future lists.
- **Don't replicate** hard-coded third-party tokens, anti-bot solutions, or demo keys (`debrid_cache.py:112,127-165,216-254`).
- **Own token only, on-device:** consistent with RD ToS (personal use, no sharing).

---

## Recommendation - awaiting user approval (non-binding)

**Default: a phased hybrid, all selectable by the user manually.**

- **Phase 1 (smallest useful):** Option 1 + Option 2. "My RD cloud" matching by filename and an "Add magnet" path. Zero third-party dependency, lowest legal/privacy surface, proves the RD flow and matcher.
- **Phase 2 (discovery):** Option 4 in *torrent-only mode* with a **configurable base URL** (default Torrentio-compatible, user may point to a self-hosted Comet), using Kitsu ids as Otaku does. Reasons: best per-episode mapping, `fileIdx`/filename for packs, tiny client, no scraping. Add Option 3a (Nyaa RSS, not HTML) as a second provider/fallback for when the aggregator has no hit or is down.
- **Phase 3 (optional/power user):** Option 5 Jackett/Prowlarr for users who already run it.
- **Skip:** AnimeTosho (shut down), Option 7 (fragile, RD-less, legally weakest), Easynews (not RD).

Open questions for the user: (1) Is a third-party hosted aggregator acceptable, or must discovery stay on the device/LAN? (2) Is a PC/NAS available on the LAN (for Option 5 or a self-hosted Comet)? (3) Is lawful-use responsibility acknowledged for whichever indexers are enabled? (4) Is the user fine with "unverified cache" status and wait-times when adding magnets?

Caveats: Torrentio/Comet public-instance health in 2026, successor AnimeTosho-type indexers, and Nyaa RSS parameter stability were not verified (ASSUMPTION). RD's May-2026 filename filtering is reported by a vendor blog only (https://store.elfhosted.com/blog/2026/05/12/real-debrid-filtering-may-2026/); verify before designing around it.

## Sources
- https://api.real-debrid.com/ (endpoints, 250 req/min, error codes; no instantAvailability listed)
- https://real-debrid.com/terms
- https://torrentfreak.com/real-debrid-implements-extreme-anti-piracy-filters-to-appease-film-companies-241122/
- https://store.elfhosted.com/blog/2024/11/22/stremio-after-realdebrid/
- https://store.elfhosted.com/blog/2026/05/12/real-debrid-filtering-may-2026/
- https://animetosho.org/ , https://animetosho.org/about/shutdown2 , https://animetosho.org/about/data
- https://nyaa.si/help , https://nyaa.si/?page=rss (live sample)
- https://torrentio.strem.fun/configure , https://github.com/TheBeastLT/torrentio-scraper
- https://github.com/g0ldyy/comet
- https://github.com/Jackett/Jackett , https://github.com/Prowlarr/Prowlarr
- https://raw.githubusercontent.com/Stremio/stremio-addon-sdk/master/docs/api/requests/defineStreamHandler.md
