# Implementation Plan — AniVerse v1

Status: **Approved (DEC-048, 2026-10-10).** Implements the approved scope (DEC-043) on the approved architecture (DEC-044). Security requirements: `security_requirements.md`. Platform gate: `platform_matrix.md` (DEC-040).

Working rules during implementation:
- One milestone at a time. After each: report changes, test results, remaining risks, next step — then wait for "continue".
- Automated tests use mocked APIs and Kodi fakes; no live credentials needed.
- No scope expansion or architecture change without owner approval.
- Nothing is published (GitHub repos, Pages) without explicit approval at Milestone 10.

Legend for automated tests: U = unit, I = integration with mocked HTTP.

---

## M0 — Project setup — ✅ Done 2026-10-10
- **Deliverables:** own Git repository in `Desktop/Kodi Add-On` (this folder currently sits inside a Git repo rooted at the user's home folder); `.gitignore`; Python 3.11 virtual environment for tests (matches Kodi 21's Python); `pytest`.
- **Owner actions/approvals:** OK to `git init` here; OK to install Python 3.11 (via the official python.org installer or `winget`) — only Python 3.12 is installed now.
- **Acceptance:** `pytest` runs (0 tests) under Python 3.11.

## M1 — Skeleton add-on — ✅ Done 2026-10-10 (Windows Kodi 21.3 + Fire TV Kodi 21.2 verified)
- **Deliverables:** `plugin.video.aniverse` with `addon.xml` (pluginsource + service), `default.py`, `service.py` (idle loop), `router.py`, `kodi/` adapters, `settings.xml`, `strings.po`, icon; `tests/fakes`; `tools/build.py` (zip only).
- **Files:** `plugin.video.aniverse/**`, `tests/fakes/**`, `tools/build.py`.
- **Tests:** U: router dispatch, unknown route handled. Build produces a zip with correct structure.
- **Manual:** install zip on Windows Kodi 21 and on the Fire TV stick (Downloader / file manager); home menu shows 12 placeholder entries; service starts without errors in `kodi.log`.
- **Acceptance:** installs and opens on both platforms; no errors in log.
- **Limitations:** entries do nothing yet.

## M2 — Core infrastructure — ✅ Done 2026-10-10 (71 tests; Windows + Fire TV verified)
- **Deliverables:** `net/http.py` (timeouts, retries, per-host rate limiter, `Retry-After`, HTTPS-only, TLS context), `errors.py`, `redact.py`, `kodi/log.py` (debug toggle), `storage/db.py` + `migrations.py` (user.db, cache.db, WAL), `storage/cache.py`, "Clear cache" setting action.
- **Tests:** U/I: timeout, retry limits, no POST retry, 429 + `Retry-After`, 5xx, redaction (SEC-03/04/05/08/09), migrations up + newer-schema refusal, cache TTL expiry, Clear cache leaves `user.db` intact.
- **Manual:** toggle debug logging on Fire TV, confirm log lines; Clear cache works.
- **Acceptance:** all tests pass; SEC-03/04/05/08/09 tests green.

## M3 — Catalog and browsing — ✅ Done 2026-10-11 (117 tests; Windows + Fire TV verified)
- **Deliverables:** `metadata/anilist.py`, `anizip.py`, `dubs.py`, `catalog.py`; views: Airing This Season, Recently Aired, Trending, Popular, Upcoming, Genres, Search (+ recent searches), Show page (info, art, related, specials/OVAs grouped), episode list; DUB badge; English-first titles.
- **Tests:** U/I with fixtures: title selection (DEC-012), format filtering (DEC-014), relations, ani.zip episode-key filtering (the 53-vs-28 caveat), ani.zip failure fallback, MAL-Dubs parse + failure keeps last copy, AniList 429 handling, pagination.
- **Manual:** browse every section with the remote on the stick; measure first-load and cached-load times; search by English/romaji/Japanese title.
- **Acceptance:** every home entry except MAL/Favourites/Continue/My RD works; cached menus open in ~1 s on the stick (measured and reported, not assumed).
- **Limitations:** no playback yet.

## M4 — MyAnimeList lists and Favourites — ✅ Done 2026-10-11 (131 tests; Windows + Fire TV verified)
- **Deliverables:** `metadata/mal.py`; MAL settings (client ID, username); My MyAnimeList menus by status; Favourites (add/remove via context menu) and menu.
- **Owner action:** register a free MAL API client at myanimelist.net and enter the client ID in settings on the device (never shared with me in chat).
- **Tests:** I: list parsing, paging, private/unknown user → clear message, MAL→AniList join via `idMal`, missing mapping shown, favourites persistence.
- **Manual:** owner's public list appears with correct shows.
- **Acceptance:** lists load with client ID + username only.

## M5 — Real-Debrid connection — ✅ Done 2026-10-11 (164 tests; Windows + Fire TV connected to owner account)
- **Deliverables:** `debrid/realdebrid.py`, `debrid/auth.py`; QR + code login dialog; account status in settings; < 7-day warning; Disconnect.
- **Tests:** I: device-code happy path, user cancels, code expires, refresh proactive/reactive, refresh failure → `AuthError`, disconnect with revoke failure, every RD error code → correct error type (SEC-06/07/10/13).
- **Manual (owner's account):** connect via phone, status shows username/expiry, disconnect, reconnect. Record actual `expires_in` and refresh behaviour (closes unknown D1).
- **Acceptance:** "Connected" shown only after `/user` succeeds.
- **Limitations:** QR PNG rendering via `script.module.pyqrcode` verified here; fallback is code + URL only.

## M6 — Source discovery and source list — ✅ Done 2026-10-11 (Windows + Fire TV)
- **Deliverables:** `sources/matcher.py`, `ranking.py`, `discovery.py`, `rdcloud.py`, `torrentio.py`, `nyaa.py`; source select dialog (two lines, groups, filters, dub-only view + "Show all sources anyway", "same as last episode" pin, hidden-count header); "Add magnet" action.
- **Tests:** U: matcher table (≥ 100 real-world style names: batches, absolute numbering, `S02E05`, OVA packs, bracket tags, version tags `v2`, dub tags, resolutions, codecs); ranking/filter/pin rules; RD token never in provider requests (SEC-12). I: provider down while others succeed; all providers empty; Kitsu ID missing → Torrentio skipped with notice.
- **Manual:** source lists for an airing show, a finished show, a dubbed show, a show with no dub; compare against what's expected.
- **Acceptance:** no source auto-selected; unknown fields absent; labels truthful.

## M7 — Resolution and playback — ✅ Done 2026-10-11 via TorBox (DEC-054/055), Windows + Fire TV verified
- **Deliverables:** `debrid/resolver.py` state machine; play view; `setResolvedUrl` with `InfoTagVideo`; not-ready → ask → modal progress (percent/speed/seeders/status) → auto-play when downloaded; cancel → keep/remove; 10-min stall prompt; bad link → back to list; cleanup of add-on-added torrents (DEC-019).
- **Tests:** I: cached play, not-ready accepted/declined, stall, cancel keep/remove, each bad status, account errors (21/23/36/403), expired auth mid-flow, unrestrict failure, file selection via `fileIdx`/filename/ambiguity prompt, poll rate within limit, owner-added torrents never deleted.
- **Manual (owner's account, Fire TV):** play a ready source; play a not-ready source end-to-end; cancel paths; confirm RD account torrent list afterwards.
- **Acceptance:** "Playing" only after Kodi reports start; no auto-switching of sources.
- **Limitations:** RD behaviours D2 (single-file select on cached torrents) verified here.

## M8 — Playback service features (first item: dub-date hint, DEC-056) — ✅ Done 2026-10-11 (DEC-057), Windows + Fire TV verified
- **Deliverables:** `service.py` player monitor: position save (30 s), watched at ≥ 90 %, resume offer, Continue Watching, manual watched/unwatched (episode + show), preferred audio language, Signs & Songs subtitle, AniSkip button (duration tolerance), Up next prompt with pre-search, playback-error → "Choose another source".
- **Tests:** U/I with fake player events: thresholds, resume, history survives Clear cache, audio/sub stream choice from fake stream lists, AniSkip tolerance accept/reject, AniSkip failure ignored, up-next timing, hand-off properties contain IDs only (SEC-15).
- **Manual (Fire TV):** watch through an episode; stop mid-way and resume; up-next flow; skip button; dubbed file audio/subs choice; memory use of service observed.
- **Acceptance:** history correct after stop, finish, crash/kill of Kodi (last saved position within 30 s).

## M9 — Hardening and performance — ✅ Done 2026-10-11 (DEC-058; findings in research/risks_and_unknowns.md §H), Windows + Fire TV verified
- **Deliverables:** error-message review against DEC-035 for every error type; performance pass on the stick (startup, menus, discovery time); `reuselanguageinvoker` evaluated (measure, then owner decides); remaining risk list updated.
- **Tests:** full suite; failure-path matrix from the brief (invalid auth, network failure, rate limits, unavailable media, expired links, Kodi playback errors) confirmed covered.
- **Acceptance:** owner reviews messages and speed on the stick.

## M10 — Packaging and private repository (publishing needs explicit approval) — ✅ Done 2026-10-11 (DEC-059), Fire TV: install, update, rollback verified
- **Deliverables:** `tools/build.py` full: version check, tests, zip, `repository.aniverse` add-on, `addons.xml` + SHA-256, last-3-versions retention, secret scan (SEC-01/02/14); install guide (Fire TV: Downloader → repository zip → install; set updates to "notify"; rollback steps).
- **Owner approvals:** create private source repo + public Pages repo on owner's GitHub; enable Pages.
- **Manual:** install repository on the stick from HTTPS; install add-on; publish a test bump; update notification appears; roll back to previous version.
- **Acceptance:** DEC-038/039 behaviours confirmed on device.

## M11 — Cross-platform release test (v1 gate) — ✅ Done 2026-10-11, released as 1.0.1 (tag v1.0.1); checklist in planning/v1_release_checklist.md
- **Deliverables:** completed manual checklist on Fire TV Stick 4K 2nd gen (gate) and Windows Kodi 21; known-limitations list; v1.0.0 tag.
- **Acceptance:** all v1 backlog acceptance criteria met or explicitly waived by the owner.

---

## M12 — UI redesign ("AniVerse look") — ✅ Done 2026-10-11 (DEC-060), released 1.1.0, Windows + Fire TV verified
- Spec: `docs/superpowers/specs/2026-10-11-aniverse-ui-redesign-design.md`; plan: `docs/superpowers/plans/2026-10-11-aniverse-ui-redesign.md`.

## M13 — MyAnimeList two-way tracking — 🔄 In progress (DEC-061)
- Spec `docs/superpowers/specs/2026-10-11-mal-two-way-tracking-design.md`, plan `docs/superpowers/plans/2026-10-12-mal-two-way-tracking.md`.

## M14 — Related & sequels franchise rows — ✅ Done 2026-10-12 (DEC-062, DEC-063), released 1.3.1, Windows + Fire TV verified
- Spec `docs/superpowers/specs/2026-10-12-related-franchise-rows-design.md`, plan `docs/superpowers/plans/2026-10-12-related-franchise-rows.md`.

---

## M15 — Sidebar, My Anime List page, Continue Watching availability, MAL add/remove — ✅ Done 2026-10-13 (DEC-064, DEC-065, DEC-066), released 1.4.0; Windows verified by owner, Fire TV pending

## Known limitations carried into v1 (stated up front)
- RD cache status is unknown until a source is chosen (no `instantAvailability`).
- Tokens stored in plain text in Kodi data on the device.
- Dub detection is heuristic; DUB badges are community data.
- ani.zip, Torrentio, Nyaa, AniSkip, MAL-Dubs are third-party services without SLAs; each fails independently with a message.
- History is per device; no backup in v1.
