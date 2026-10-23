# Decision Log

Status values: **Approved** (product owner decided), **Proposed** (recommendation, not approved), **Open**.

---

## DEC-001 — Platform priorities
- **Status:** Approved (project brief, 2026-10-10)
- **Question:** Which platforms matter?
- **Answer:** Primary: Android TV and Amazon Fire TV devices running compatible Kodi. Secondary: desktop Kodi.
- **Reasoning:** Personal TV use with a remote.
- **Alternatives considered:** Desktop-first.
- **Consequences:** Remote-first UX; pure-Python, portable Kodi APIs only; performance budget set by low-end sticks.
- **Related:** DEC-007 (exact devices/Kodi versions).
- **Open questions:** Exact devices and Kodi versions — see DEC-007. Research note: newer Fire TV models on Vega OS cannot run Kodi (`research/platform_compatibility.md`).

## DEC-002 — Primary playback integration
- **Status:** Approved
- **Answer:** Real-Debrid is the primary (only) playback integration for v1. Others need owner approval.
- **Consequences:** RD auth, token refresh, resolve pipeline are core. RD is not a catalog.
- **Related:** DEC-003, `research/real_debrid_analysis.md`.

## DEC-003 — Media-source discovery approach
- **Status:** Approved (Workshop 3, 2026-10-10)
- **Question:** How should the add-on find sources for an episode?
- **Answer:** (c) — three discovery paths, all feeding the same manual source list:
  1. Owner's existing Real-Debrid account content (torrents/downloads) matched to the episode by filename, plus an "add magnet" path.
  2. A Stremio-protocol source aggregator (Torrentio-compatible) queried by anime ID (Kitsu ID per Otaku `pages/torrentio.py:54`), torrent-only mode, **configurable base URL**.
  3. Nyaa RSS as a fallback text search; results labelled "best guess" match.
- **Reasoning:** Convenient per-episode discovery on TV, with a fallback when the aggregator has no results or is down.
- **Alternatives considered:** (a) own RD account only; (b) without Nyaa; (d) self-hosted Jackett/Prowlarr (ruled out by DEC-016); direct-stream website scrapers (excluded); AnimeTosho (shutting down); Easynews (not RD).
- **Consequences:**
  - The owner's RD token is **never** sent to the aggregator or Nyaa (unlike common Torrentio configurations). Aggregator/Nyaa see show/episode queries only.
  - RD cache status is unknown before selection (no instantAvailability) — candidates shown as "not checked"; readiness determined only after the owner selects one.
  - Discovery providers, the episode-file matcher and the RD resolver are separate components, so a dead provider can be replaced without touching playback.
  - Matching must cope with per-season AniList entries (DEC-013) vs absolute numbering in release names.
  - Implementation order is a milestone question: owner-account path first proves the RD pipeline, then aggregator, then Nyaa.
  - Owner acknowledged: torrent indexes list content of mixed copyright status; lawful use is the owner's responsibility.
- **Related:** DEC-002, DEC-004, DEC-013, DEC-016.
- **Open questions:** Aggregator public-instance health in 2026 (unverified); Kitsu ID source (AniList has no Kitsu ID — need a mapping, e.g. via the aggregator's own anime catalog or a mapping file); Nyaa RSS parameter stability (undocumented).

## DEC-004 — Manual source selection
- **Status:** Approved
- **Answer:** User always chooses the source. Show file name, resolution, size, language, release info, availability when known; never invent missing data. No automatic fallback to another source without user approval.
- **Consequences:** Otaku's default smartplay/autoplay is not adopted. Retry workflow must return to the source list.

## DEC-005 — Local watch history
- **Status:** Approved
- **Answer:** Stored locally per Kodi install. No remote sync in v1.
- **Consequences:** Own schema (identity, watched, resume position, completion, last-watched timestamp; favorites pending). Must not be wiped by cache rebuilds (contrast Otaku, `research/risks_and_unknowns.md` A7).

## DEC-006 — Private repository distribution
- **Status:** Approved (mechanism); details Open
- **Answer:** Install/update via a private Kodi add-on repository. Not to be created/published until packaging approved.
- **Open questions:** Kodi repos have no native auth; hosting choice; SHA-256 checksums (`research/platform_compatibility.md`).

---

## DEC-007 — Primary device
- **Status:** Approved (Workshop 1, model confirmed 2026-10-10)
- **Question:** Which exact devices will you use?
- **Answer:** Amazon **Fire TV Stick 4K (2nd generation, 2023)**.
- **Reasoning:** Owner's actual device.
- **Alternatives considered:** Android TV / Google TV boxes, Nvidia Shield.
- **Device facts:** Runs Android-based Fire OS (not Vega OS), so Kodi can be sideloaded — consistent with `research/platform_compatibility.md` §4. Commonly reported specs: Fire OS 8 (Android 11 base), 2 GB RAM, quad-core 1.7 GHz — ASSUMPTION from public spec listings, not verified from Amazon primary docs; Kodi build ABI (armeabi-v7a vs arm64-v8a) to confirm on the device (Kodi → System info).
- **Consequences:** Performance budget = 2 GB-RAM stick: fast menus, minimal background work, pure-Python dependencies only. Remote-first UI.
- **Related:** DEC-001, DEC-008.

## DEC-008 — Kodi version support
- **Status:** Approved (Workshop 1, 2026-10-10)
- **Question:** Which Kodi versions should v1 support?
- **Answer:** (a) Kodi 21 Omega only.
- **Reasoning:** Current stable release; smallest test matrix.
- **Alternatives considered:** (b) 21 + 22 Piers when final (recommended); (c) also Kodi 20 Nexus.
- **Consequences:** Target `xbmc.python` 3.0.1, Python 3.11 runtime. Use Kodi 20+ APIs (`InfoTagVideo`, not `setInfo`). Kodi 22 (Python 3.14, `xbmc.python` 3.1.0) is unsupported until a later decision; avoid deliberately version-fragile code so a later upgrade stays cheap.
- **Related:** DEC-009, platform matrix.
- **Open questions:** Revisit when Kodi 22 is final.

## DEC-009 — Desktop platform
- **Status:** Approved (Workshop 1, 2026-10-10)
- **Answer:** Windows only (secondary target).
- **Alternatives considered:** Linux, macOS.
- **Consequences:** Desktop testing on Windows Kodi 21. Note: Windows Kodi behaviour ≠ Fire OS behaviour (paths, performance, TLS stack) — Fire TV testing remains mandatory.

## DEC-010 — Input devices
- **Status:** Approved (Workshop 1, 2026-10-10)
- **Answer:** (b) TV remote plus phone.
- **Alternatives considered:** (a) remote only; (c) keyboard / air-mouse.
- **Consequences:** Real-Debrid authorization = device-code flow showing a QR code + short code on the TV; user approves on phone. All navigation must work with D-pad + Back + OK + menu. Text entry (search) uses Kodi's on-screen keyboard; Kodi's remote/phone keyboard apps may help but are not required.
- **Related:** F-RD-AUTH.

## DEC-011 — Metadata sources
- **Status:** Approved (Workshop 2, 2026-10-10)
- **Answer:** (b) AniList for catalog/search/seasonal + one free, keyless source for episode details (titles, thumbnails, air dates).
- **Alternatives considered:** (a) AniList only; (c) multi-provider incl. TMDB/Fanart.tv with user API keys.
- **Consequences:** No API keys required for metadata in v1. AniList entries carry `idMal`, so every show also has its MyAnimeList ID (useful for DEC-015). Episode-detail source to be chosen in architecture phase (candidates in `research/metadata_analysis.md`); AniList rate limit (90/min baseline, possibly 30/min) needs caching + backoff.
- **Open questions:** Which episode-detail source; its terms and stability.

## DEC-012 — Title language
- **Status:** Approved (Workshop 2)
- **Answer:** (a) English title first, fallback romaji. Search matches English, romaji, native and synonyms.

## DEC-013 — Season organisation
- **Status:** Approved (Workshop 2)
- **Answer:** (a) Each season is its own show, with Sequel/Prequel/Related links on the details page.
- **Alternatives considered:** (b) grouped seasons via mapping database.
- **Consequences:** No dependency on a cross-provider season mapping DB in v1. Episode numbers are per-entry (1..N). Source matching must handle releases that use absolute numbering or `S02E05` naming for a separate AniList entry — risk recorded for discovery design.

## DEC-014 — Specials, OVAs, movies
- **Status:** Approved (Workshop 2)
- **Answer:** (b) Catalog lists show TV series and movies; specials/OVAs/ONAs appear only under the related show's page.
- **Consequences:** Browse/search filter by AniList format; details page lists related entries grouped by type.
- **Open questions:** ONA-only series (some are main series, e.g. web releases) — treat ONA with ≥ N episodes as series? Decide in catalog follow-up.

## DEC-015 — MyAnimeList integration
- **Status:** Approved (Workshop 2, 2026-10-10)
- **Question:** "I use MyAnimeList to track my anime, can we use them?"
- **Answer:** (d) v1 = read-only MyAnimeList lists in Kodi; two-way sync = first post-v1 feature. Owner's MAL list is **public**.
- **Reasoning:** Lists on TV immediately without MAL's TV-unfriendly login; sync after playback basics are stable.
- **Alternatives considered:** (a) local only, store MAL IDs; (b) read-only only; (c) two-way sync in v1.
- **Consequences:**
  - v1 needs a MAL API client ID registered by the owner (free, myanimelist.net/apiconfig). It is the owner's app credential — stored in settings, never in source code or Git.
  - Owner's MAL username stored in settings (not secret).
  - Uses `GET /users/{user_name}/animelist` with `X-MAL-CLIENT-ID` — CONFIRMED in MAL API v2 reference (https://myanimelist.net/apiconfig/references/api/v2, fetched 2026-10-10). Live behaviour still to test.
  - Menus by status (Watching, Plan to Watch, Completed, On Hold, Dropped); each entry links by MAL ID → AniList entry (AniList `idMal`).
  - Local history (DEC-005) remains the source of truth for watched/resume in v1. MAL list status is displayed, not changed.
  - All local records keep the MAL ID so v2 sync needs no data migration.
- **Related:** DEC-005 (unchanged for v1; to be amended when sync is scheduled), DEC-011.
- **Open questions:** Login method for v2 write sync (paste-URL flow vs alternatives); conflict rules between local history and MAL episode counts.

## DEC-016 — Always-on LAN server
- **Status:** Approved (Workshop 3, 2026-10-10)
- **Answer:** No always-on PC/NAS available.
- **Consequences:** Everything runs on the Fire TV Stick or uses hosted services. Self-hosted Jackett/Prowlarr/Comet excluded for v1.

## DEC-017 — Real-Debrid authorization and disconnect
- **Status:** Approved (Workshop 3, 2026-10-10)
- **Answer:** (a) Device-code flow: TV shows QR code + short user code; owner approves on phone (or at real-debrid.com/device). Disconnect button revokes access (`GET /disable_access_token`) then deletes locally stored tokens.
- **Alternatives considered:** (b) pasting the private API token (rejected: remote typing; full-scope non-expiring token).
- **Consequences:** Uses RD's documented open-source client ID (`X245A4XAIBGVM`, public, not a secret; may carry stricter limits) unless the owner later registers an own app. Access token refreshed proactively before expiry and on HTTP 401 / error_code 8 (fixes Otaku gap, `risks_and_unknowns.md` A4). Tokens stored in Kodi add-on data in plain text — documented limitation (C3). Never logged.
- **Open questions:** Real `expires_in` and refresh-token rotation (need live test).

## DEC-018 — Account status display
- **Status:** Approved (Workshop 3)
- **Answer:** (b) Status in settings (username, account type, premium expiry) + warning notification when premium has < 7 days left.
- **Consequences:** `GET /user` on add-on start at most once per day (cached); warning shown at most once per day.

## DEC-019 — Cleanup of torrents added by the add-on
- **Status:** Approved (Workshop 3)
- **Answer:** (a) Remove a torrent the add-on added once its stream has started.
- **Alternatives considered:** (b) keep all; (c) keep, auto-remove after 14 days.
- **Consequences:** Next episode from the same batch pack is re-added (usually instant if cached). Only torrents **added by the add-on in this playback** are deleted — never torrents the owner added (F-SRC-RDCLOUD sources are never deleted). Removal failure is logged, not shown as a playback error.
- **Open questions:** Cancelled downloads (DEC-020 follow-up).

## DEC-020 — Selected source not ready on Real-Debrid
- **Status:** Approved in principle (Workshop 3); details pending follow-up questions
- **Owner's answer (verbatim intent):** If the source is not a bad link, ask whether to download it. If yes, download it, show the progress bar on screen, and play it once it's done.
- **Definitions (from RD API, `research/real_debrid_analysis.md`):**
  - *Bad link* → tell the owner and return to the source list: RD torrent status `magnet_error`, `error`, `virus`, `dead`; error_code 35 (infringing file), 16/unsupported; magnet never resolves to file list within a timeout.
  - *Not ready but downloadable* → ask: status `queued`, `downloading`, `compressing`, `uploading`, or `waiting_files_selection` after our file selection.
  - *Ready* → play immediately: status `downloaded`.
  - *Account problems* (own message, not "bad link"): 401/8 auth, 403 not premium, 21 too many active downloads, 23 traffic exhausted, 36 fair-usage limit.
- **Behaviour:** Ask → on Yes, progress dialog shows percent, speed, seeders and status from `GET /torrents/info/{id}`, polled at a bounded interval (respecting 250 req/min) → on `downloaded`, unrestrict and play automatically (it is the source the owner chose, so this does not violate DEC-004). On No → remove torrent, return to list.
- **Supersedes:** Option (b)/(c) wording of Q15.
- **Follow-ups (approved 2026-10-10):**
  - Q15a Cancel/Back during progress → (c) ask each time: "Keep downloading in Real-Debrid, or remove it?" (Exception to DEC-019: a kept torrent is not auto-removed.)
  - Q15b Stall (0 seeders or no progress) → (b) after 10 minutes without progress, stop and ask: keep waiting / keep in Real-Debrid for later / remove.
  - Q15c → (a) modal progress dialog stays until playback or cancel. Background download + notification = future feature.
- **Status update:** Approved.

## DEC-021 — Source list presentation
- **Status:** Approved (Workshop 4, 2026-10-10)
- **Answer:** (a) Kodi's built-in select dialog, two lines per source (line 1: release/file name; line 2: resolution · size · language · origin · status). Unknown fields shown as absent, never guessed (DEC-004).
- **Alternatives considered:** (b) custom full-screen window (Otaku-style).
- **Consequences:** No custom skin XML in v1; skin-consistent and remote-safe. Limits visual richness.

## DEC-022 — Source ordering
- **Status:** Approved (Workshop 4)
- **Answer:** (a) Groups in order: owner's Real-Debrid files (ready now) → aggregator results → Nyaa "best guess". Within group: resolution high→low, then size large→small. "Same as last episode" items (DEC-024) pinned to the top of their group.

## DEC-023 — Source filters
- **Status:** Approved (Workshop 4)
- **Answer:** (b) Optional filters in settings (minimum resolution, maximum size, excluded codecs); none active by default. List header shows "N hidden by your filters".
- **Consequences:** Filters apply only when the field is known; a source with unknown resolution is not hidden by a resolution filter (it is shown with resolution absent).

## DEC-024 — Remember last choice
- **Status:** Approved (Workshop 4)
- **Answer:** (b) Per show, remember release group + resolution of the last played source; matching sources are pinned and labelled "same as last episode". Never auto-selected.
- **Consequences:** Small per-show preference record in local DB (DEC-005).

## DEC-025 — Sub vs dub
- **Status:** Approved (Workshop 5, 2026-10-10); follow-ups pending
- **Answer:** (b) Dubbed only (English audio).
- **Consequences:**
  - Source list must label English-audio sources. Detection is heuristic: release-name tags (e.g. "Dual Audio", "Dub", "English Dub", "Multi-Audio"), aggregator language hints where provided. A source with no audio-language signal is shown as audio unknown — never labelled dub without evidence (DEC-004). True audio tracks only verifiable after playback starts.
  - Many anime have no English dub, or dubs released months after Japanese airing.
- **Follow-ups (approved 2026-10-10):**
  - Q20a → (a) Source list shows only dub-labelled sources. If none: "No English dub found" with an action "Show all sources anyway". Sources with unknown audio are hidden in dub-only view but appear in "show all".
  - Q20b → (b) Best-effort "DUB" badge in catalog lists.
    - Data source: **MAL-Dubs** dataset `https://raw.githubusercontent.com/MAL-Dubs/MAL-Dubs/main/data/dubInfo.json` — keys `dubbed` (5,764 MAL IDs) and `incomplete` (170) as fetched 2026-10-10; repo active (last push 2026-10-09). CONFIRMED. Otaku uses the same file (`service.py:173-176`, `ui/divide_flavors.py`).
    - License: file states AGPL-3.0. Downloading it at runtime for personal use is fine; do **not** bundle/redistribute it inside our add-on package without complying with AGPL.
    - Keyed by MAL ID → joins via AniList `idMal` (DEC-011). "incomplete" shown as "DUB (partial)". Badge may be wrong or missing — community-maintained.
    - Refresh: download at most weekly; keep last good copy if download fails.
- **Status update:** Approved.
- **Related:** DEC-023 (filters), DEC-022 (ordering), DEC-027.

## DEC-026 — Subtitle language and source
- **Status:** Approved (Workshop 5)
- **Answer:** English subtitles; embedded subtitles only (Q22 a). No external subtitle service in v1.
- **Consequences:** No OpenSubtitles account/key.
- **Follow-up Q21a (approved):** (b) With English audio, enable an English "Signs & Songs" / forced subtitle track if present (detected by track name/forced flag); otherwise subtitles off. Detection relies on track metadata; if ambiguous, subtitles off.

## DEC-027 — Audio track selection
- **Status:** Approved (Workshop 5)
- **Answer:** (b) Add-on setting "Preferred audio language" (default English per DEC-025) applied at playback start via the Kodi player API; falls back to Kodi's default if the language is absent.
- **Consequences:** Must not change Kodi's global audio setting. Audio-stream language tags inside files can be missing or wrong — fallback is Kodi default, no guessing.

## DEC-028 — Watched threshold
- **Status:** Approved (Workshop 6, 2026-10-10)
- **Answer:** (a) Episode marked watched at ≥ 90 % played.
- **Consequences:** Below 90 % → resume point stored. Add-on history is recorded by the add-on's own player monitor; Kodi's internal resume state for plugin URLs is separate and not relied on (DEC-005).

## DEC-029 — Continue Watching
- **Status:** Approved (Workshop 6)
- **Answer:** (a) Home-screen "Continue Watching": started shows, most recent first, each showing next episode or resume point.

## DEC-030 — End-of-episode behaviour
- **Status:** Approved (Workshop 6)
- **Answer:** (b) "Up next" prompt near the end ("Next: Episode N — choose source"); OK opens the source list. Source search starts during the credits so the list is ready; DEC-024 pin applies. Never auto-plays (DEC-004).
- **Consequences:** Prompt timing: start of end credits if known, otherwise last N seconds (N to fix in design). Background search must be cancellable and must not stall playback on a 2 GB stick.

## DEC-031 — Local favourites
- **Status:** Approved (Workshop 6)
- **Answer:** (b) Simple local Favourites list per device, managed with the remote; not synced.

## DEC-032 — Manual watched/unwatched
- **Status:** Approved (Workshop 6)
- **Answer:** Yes — mark episode (and whole show) watched/unwatched from the remote's context menu.

## DEC-033 — Home menu
- **Status:** Approved (Workshop 7, 2026-10-10)
- **Answer:** All 12 entries, in order: Continue Watching, Search, My MyAnimeList (by status), Favourites, Airing This Season, Recently Aired Episodes, Trending Now, Most Popular, Upcoming Next Season, Genres, My Real-Debrid, Settings.
- **Consequences:** Catalog sections come from AniList queries; no per-format/time-window menu explosion (contrast Otaku).

## DEC-034 — Cache policy
- **Status:** Approved (Workshop 7)
- **Answer:** (a) Favour speed: browse lists 1 day; episode lists 6 h for airing shows, 30 days for finished shows. "Clear cache" setting never touches watch history, favourites or preferences.
- **Consequences:** Cache and user data stored separately (separate DB files/tables) so clearing one cannot affect the other.

## DEC-035 — Error presentation
- **Status:** Approved (Workshop 7)
- **Answer:** (b) Transient issues → short notification. Actionable issues (RD login expired, premium ended, account limits, MAL user not found/private) → dialog with a clear next step.

## DEC-036 — Context menu
- **Status:** Approved (Workshop 7)
- **Answer:** In-add-on context items only (no global context add-on): Mark watched/unwatched, Add/remove Favourites, Choose a different source, Related & sequels, Show info.

## DEC-037 — Diagnostic logging
- **Status:** Approved (Workshop 7)
- **Answer:** "Debug logging" setting, off by default. Tokens, auth codes, RD download/unrestricted URLs and API client IDs/keys are always redacted, in all log levels and in exception messages.

## DEC-038 — Repository hosting
- **Status:** Approved (Workshop 8, 2026-10-10)
- **Answer:** (a) GitHub Pages (free). Source code in a **private** GitHub repo; built zips + `addons.xml` + checksum in a separate **public** Pages repo.
- **Consequences:** Packages are publicly downloadable by anyone who finds the URL (Kodi repos have no auth — `research/platform_compatibility.md`). Therefore the package must contain no credentials (already required). Use SHA-256 checksums in repository metadata (Kodi supports them; MD5 triggers a warning). Do not create/publish until packaging is approved (DEC-006).
- **Open questions:** GitHub account/repo names; repository add-on ID.

## DEC-039 — Update policy
- **Status:** Approved (Workshop 8)
- **Answer:** (b) Kodi notifies; owner chooses when to update. Repository keeps the previous 3 versions for rollback.
- **Consequences:** Kodi's auto-update mode is a Kodi-wide/per-add-on user setting, not something the add-on can enforce; installation guide will instruct setting this add-on to "notify". Local DB schema migrations must be forward-only and safe; rollback to an older version must not corrupt user data (older version must tolerate or refuse a newer schema clearly).

## DEC-040 — v1 test gate
- **Status:** Approved (Workshop 8)
- **Answer:** (a) Fire TV Stick 4K (2nd gen) on Kodi 21 **and** Windows Kodi 21; the Fire TV stick is the release gate.

## DEC-041 — Skip intro/ending
- **Status:** Approved (Workshop 8) — included in v1
- **Answer:** (a) Skip intro/ending button using AniSkip.
- **Research facts:** `GET https://api.aniskip.com/v2/skip-times/{malId}/{episode}?types[]=op&types[]=ed&episodeLength=<seconds>` returned 200 with `op`/`ed` intervals and the submitter's `episodeLength` (live probe 2026-10-10, MAL ID 52991 ep 1). CONFIRMED that the endpoint works; terms/rate limits not yet reviewed. Keyed by MAL ID (available via AniList `idMal`).
- **Consequences:** Dub files may differ in length/timing from the submission. Only offer the button when the submission's `episodeLength` is within a small tolerance of the actual playing duration; otherwise hide it. Button only (never auto-skip) unless decided otherwise. Failure of AniSkip must never affect playback.
- **Open questions:** Tolerance value; button vs auto-skip setting; AniSkip terms of use.

## DEC-042 — Backup/restore
- **Status:** Approved (Workshop 8)
- **Answer:** (a) Not in v1.
- **Consequences:** Watch history lives only on the device; a Fire TV reset loses it. Candidate future feature.

## DEC-043 — v1 scope
- **Status:** Approved (2026-10-10)
- **Answer:** (a) Approve the v1 feature scope as listed in `feature_backlog.md` (27 features).
- **Consequences:** Architecture proposal written (`architecture.md`), awaiting approval.

## DEC-044 — Architecture
- **Status:** Approved (2026-10-10)
- **Answer:** (a) Approve `architecture.md` as proposed.

## DEC-045 — Add-on name and IDs
- **Status:** Approved (2026-10-10)
- **Answer:** Display name **AniVerse**. IDs: `plugin.video.aniverse` (add-on), `repository.aniverse` (repository add-on).
- **Evidence:** No add-on ID or name containing "aniverse" in the official Kodi Omega repository index (`mirrors.kodi.tv/addons/omega/addons.xml`, checked 2026-10-10). Third-party repos not checked; irrelevant for a private install unless the owner also installs a same-ID add-on.

## DEC-046 — Episode-detail source
- **Status:** Approved (2026-10-10)
- **Answer:** (a) ani.zip for episode details and cross-IDs (incl. Kitsu ID for Torrentio); fallback to AniList-only episode numbers when ani.zip fails.
- **Consequences:** If ani.zip is down and no cached Kitsu ID exists, the Torrentio provider is skipped for that show (RD cloud + Nyaa still run) with a notice; never guess IDs.

## DEC-047 — Playback tracking
- **Status:** Approved (2026-10-10)
- **Answer:** (a) Always-running Kodi service (`service.py`) monitors playback.

## DEC-048 — Plan approval and dev setup
- **Status:** Approved (2026-10-10)
- **Answers:** Q44 (a) security requirements, test strategy and milestone plan approved. Q45 project Git repo approved; remote `https://github.com/chiefabs6-ops/Anime-Add-On.git`. Q46 Python 3.11 install approved.
- **Done:** `git init` in project folder (local commit `60be86c`, docs only); remote added, **not pushed**. Python 3.11.9 installed per-user via winget (`py -3.11`), alongside 3.12.
- **Open question:** The remote repository is **public** (GitHub API, 2026-10-10), while DEC-038 placed source code in a private repo. Owner to choose: make it private, or accept public source. No push until answered.

## DEC-049 — Source repository visibility; implementation start
- **Status:** Approved (2026-10-10)
- **Answer:** Q47 (a) Owner will make `chiefabs6-ops/Anime-Add-On` private (matches DEC-038). Owner answered "yes start implementing" to the Phase 9 gate question.
- **Consequences:** Before the first push, visibility is re-checked; if it is still public, no push happens and the owner is asked.

## DEC-050 — ONA in catalog lists
- **Status:** Approved (2026-10-11)
- **Answer:** (a) Include ONA in catalog lists (resolves DEC-014 open question). Catalog formats: TV, TV_SHORT, ONA, MOVIE.

## DEC-051 — Freshness of time-sensitive lists
- **Status:** Approved (2026-10-11) — amends DEC-034
- **Answer:** (b) "Recently Aired Episodes" and "Airing This Season" cached 1 hour; other lists stay 1 day.

## DEC-052 — Real-Debrid token storage location
- **Status:** Implementation decision (M5, 2026-10-11), reported to owner
- **Decision:** RD credentials stored in `addon_data/plugin.video.aniverse/realdebrid.json` instead of Kodi settings (architecture §5 said settings).
- **Reasoning:** Kodi's settings dialog keeps its own copy and saves it on OK, overwriting values written by a login started from that same dialog. Security is unchanged: plain text on the device (SEC-11); file written atomically, `chmod 600` where the OS supports it.

## DEC-053 — Pre-check sources with Real-Debrid
- **Status:** Approved (2026-10-11)
- **Question:** Should AniVerse test sources before listing them, given Real-Debrid's content filter (risks G)?
- **Answer:** Check in list order until **2 playable** sources are found; hide blocked ones.
- **Behaviour:** Each check = addMagnet → (wait ≤5 s for file list) → select episode file → info → delete (only torrents the check itself created). Outcomes: blocked (451/code 35), ready (cached), needs downloading, unknown (slow/timeout). Max 4 checks at a time; stop on Real-Debrid "slow down". Results cached: blocked 30 days, ready/needs-download 1 hour. Account files count as playable without checking.
- **List:** playable sources first; extra entries "Check more sources (N not checked)" and "Show blocked sources (N)".
- **Alternatives considered:** top-10 auto check; check everything; on-demand only.
- **Consequences:** first open of an episode slower (typically a few seconds, more when most are blocked); extra RD API calls; a check is a snapshot — play can still be refused (handled as BadSource → back to list).

## DEC-054 — TorBox replaces Real-Debrid for playback (for now)
- **Status:** Approved (2026-10-11) — amends DEC-002
- **Answer:** Owner: "for now replace Real-Debrid with TorBox so we can check if it will work". New setting "Playback service" (default TorBox; Real-Debrid still selectable); Real-Debrid code kept.
- **Evidence:** Real-Debrid refused all tested anime releases via API (risks G). TorBox free cache check on Frieren S2 ep 1: 67 of 76 sources cached, 20 of 20 English dub/dual cached (2026-10-11).
- **Consequences:** TorBox auth = owner API key in settings (stored by Kodi in plain text on the device; key redacted from logs). Source checking uses TorBox checkcached (free, adds nothing). Playback: createtorrent -> mylist -> requestdl -> cleanup via controltorrent delete. Free plan limits (TorBox support pages): ~10 downloads/month, 10 GB per torrent, 1 active slot — owner to confirm plan on torbox.app. mylist field names unverified until the first live torrent (debug log records them).

## DEC-055 — TorBox is the playback service going forward
- **Status:** Approved (2026-10-11) — supersedes the "for now" in DEC-054
- **Answer:** Owner: "we will move to TorBox as the anime videos are actually playing from there".
- **Evidence:** Live playback through TorBox on Windows Kodi 21.3 succeeded (cached source, stream started, add-on-added torrent removed after start). TorBox mylist fields confirmed live: download_finished, download_present, download_state (e.g. "cached"), progress, download_speed, seeds, files, hash, id, name, size.
- **Consequences:** Real-Debrid code stays selectable in settings but is no longer the default or the focus of testing. Known issue: default audio track was not English on the test file — addressed by DEC-027 preferred audio language in M8.

## DEC-056 — Dub release-date hint is the first M8 item
- **Status:** Approved (2026-10-11); built and verified on Windows and Fire TV 2026-10-11 (`metadata/animeschedule.py`, `Catalog.dub_estimates`)
- **Answer:** On a show's episode list, episodes aired in Japanese but not yet dubbed get a grey note "(Dub expected <weekday day month>)" (and in the description, "estimate from AnimeSchedule.net").
- **Data:** AnimeSchedule.net public `GET https://animeschedule.net/api/v3/anime?mal-ids=<id>` (no token; live 2026-10-11) returns dubPremier, dubTime, dubDelayedFrom, dubDelayedUntil, dubEpisodeOverride, dubDelayedTimetable, episodes. Timetables need an app token (401 without) — not used; Otaku's embedded token must not be reused. Estimate = dubPremier + 7 days x (n-1), shifted by known delays. Cache 1 day per show; failures = no hint.
- **Resolved (API v3 docs, 2026-10-11):** dubTime = release time, only hour/minute relevant. dubEpisodeOverride = on overrideDate, episodes overrideEpisode..overrideEpisode+episodesAired came out together; weekly after that. dubDelayedTimetable = display text only (not used). A delay with no end date = no estimate for episodes after its start.
- **When checked:** shows with a MAL ID, not movies, status Releasing/Hiatus or started within the last 365 days. Failures cached 1 hour.

## DEC-057 — M8 implementation choices (player monitor)
- **Status:** Built and verified by the owner on Windows and Fire TV (2026-10-11)
- **Resume (DEC-028):** Kodi already stores its own resume points under our `plugin://…/play?id=X&ep=N` URLs (seen in MyVideos131.db on the PC). So episode items carry our history as the Kodi resume point and play count, and Kodi's own "Resume from" dialog does the asking and seeking. No second AniVerse prompt. Our history is the record: an episode with no history row is shown unwatched.
- **History:** saved every 30 s and on stop/end; watched at >= 90 % (resume point cleared); positions under 60 s are not resume points; a rewatch never un-marks a watched episode. user.db schema v3 adds title/poster/MAL ID/episode total to show_prefs so Continue Watching needs no network.
- **Continue Watching (DEC-029):** one row per show, newest first. Started episode → plays directly (with resume point). Finished episode → "Next: Episode N" opens the show page (the next episode may not have aired). Shows whose last episode is watched drop off.
- **AniSkip (DEC-041 open questions):** tolerance ±5 s between the submission's episodeLength and the playing file (live: Frieren ep 1 file 1560.9 s vs submission 1559.9 s; AniSkip returned a 1420 s submission for a 1400 s request, which is rejected). Button only, never auto-skip. Button closes after 10 s.
- **Up next (DEC-030):** at the ending's start when AniSkip has a matching ending, otherwise 90 s before the end; not for movies, clips under 5 min, or after the last aired episode. Pre-search for the next episode starts when the prompt appears. OK = PlayMedia of the next episode's source list; never auto-plays. Prompt closes after 20 s. When Up next uses the ending's start it replaces the Skip ending button.
- **Audio/subtitles (DEC-026/027):** setting "Preferred audio language" English (default) / Japanese / Kodi default; switches only the current player's stream via JSON-RPC. With English audio: one clear English Signs & Songs/forced track → on, otherwise subtitles off. Non-English audio: Kodi's subtitle choice kept.
- **Playback error:** "Playback failed. Choose another source for this episode?" → opens the episode's source list again.
- **Prompts** take the remote's focus while shown: OK runs the action, any other key closes the prompt.

## DEC-058 — Keep the add-on loaded between menus (reuselanguageinvoker)
- **Status:** Approved (2026-10-11), on from 0.9.1; owner checked on Fire TV: runs fine
- **Answer:** Owner chose "Try it on": `reuselanguageinvoker` = true. Turn it off again if the stick closes Kodi for low memory or anything behaves oddly.
- **Evidence (Windows, Kodi debug log):** without it each menu spends ~350 ms starting Python and importing the add-on (add-on work 15–47 ms); with it, menus after the first take 3–12 ms. Fire TV not measured by automation (runs overloaded the stick); the stick's slower CPU should save more.
- **Consequences:** module state now lives across menu calls. Settings are read fresh each call (the cached debug-logging flag is reset in `router.setup()` and each service minute); the HTTP rate limiter now counts across calls, which is stricter, not looser. Extra memory for the kept interpreter on a 1.7 GB stick that already kills background apps (risk list H).

## DEC-059 — Repository published; updates install automatically
- **Status:** Approved (2026-10-11) — amends DEC-039 ("notify")
- **Answer:** Owner kept Kodi's "Install updates automatically" on the Fire TV stick (`general.addonupdates` = 0) instead of notify-only.
- **Evidence:** Repository live at `https://chiefabs6-ops.github.io/aniverse-repo/` (public Pages repo `chiefabs6-ops/aniverse-repo`, built zips only; source stays in private `chiefabs6-ops/Anime-Add-On`). On the stick: repository 1.0.0 installed, AniVerse installed from it, test update 0.9.2 installed, rollback to 0.9.1 worked, and Kodi then reinstalled 0.9.2 by itself (log: v0.9.1 installed → v0.9.2 installed).
- **Consequences:** every publish reaches the stick without action. A rollback only stays if Auto-update is turned off on AniVerse's add-on page. The repository keeps 3 versions, so rollback remains possible.

## DEC-060 — AniVerse look (UI redesign, M12)
- **Status:** Approved (2026-10-11); spec `docs/superpowers/specs/2026-10-11-aniverse-ui-redesign-design.md`, plan `docs/superpowers/plans/2026-10-11-aniverse-ui-redesign.md`
- **Answer:** AniVerse draws its own screens (app window with sidebar, Home, Grid; show page; source list; popups) in the owner's neon design. Only inside AniVerse; Kodi's skin untouched. Setting "AniVerse look" (default on) switches back to the classic lists.
- **Consequences:** resume is offered by AniVerse (button / Resume-or-start choice) and the player monitor seeks (`resume_s` in the hand-off). Fonts are Estuary's; glow/rounded corners are generated PNGs (`tools/make_assets.py`, Pillow dev-only; icons Material Symbols Rounded, Apache-2.0). Logo = owner's dragon image with its neon frame, background removed; icon file renamed `aniverse-icon.png` so Kodi's icon cache shows it at once. Kodi widgets keep using the plugin lists. Owner checked every screen on the PC (2026-10-11).

## DEC-061 — MyAnimeList two-way tracking (M13)
- **Status:** Approved (2026-10-11); spec `docs/superpowers/specs/2026-10-11-mal-two-way-tracking-design.md`, plan `docs/superpowers/plans/2026-10-12-mal-two-way-tracking.md`. Amends DEC-015.
- **Answer:** Optional MyAnimeList login (Settings → MyAnimeList → MyAnimeList account): QR code on the TV, login on the phone, the code reaches the TV through the static relay page `mal-login.html` on the repository site and a one-shot listener on the TV's LAN address. AniVerse then shows MAL progress (show page, next episode, Continue Watching) and updates MAL automatically (episode watched ≥ 90 %, marks), queued in `user.db` and sent by the service.
- **Consequences:** Owner's MAL app needs App Redirect URL `https://chiefabs6-ops.github.io/aniverse-repo/mal-login.html` and no client secret (not "web" type). Tokens in `mal_auth.json` (plain text like `realdebrid.json`, SEC-11), only sent to MAL. Plain PKCE (MAL's only method). The listener also redirects `GET /` to the MAL login so the TV can show a short address (spec amendment). Without a login AniVerse behaves as 1.1.0. Owner check on PC and Fire TV: pending.

## DEC-062 — Related & sequels as franchise rows (M14)
- **Status:** Approved (2026-10-12); spec `docs/superpowers/specs/2026-10-12-related-franchise-rows-design.md`, plan `docs/superpowers/plans/2026-10-12-related-franchise-rows.md`. Amends DEC-013, DEC-014.
- **Answer:** The Related & sequels button shows the whole franchise in six rows: Sequels, Prequels, Side stories, OVAs & Specials, Movies, Other, each oldest first. Sequel/prequel links are followed through every format, one batched AniList query (`id_in`, 50 per call) per step; extras of every chain member are fetched once and not walked. Rows by format first (movie → Movies, OVA/Special → OVAs & Specials), then by relation.
- **Consequences:** Nodes cached `relnode:<id>` and results `franchise:v1:<id>` for 1 day; partial results (AniList failure mid-walk) shown with a notice and not cached. Cap 60 chain entries and 60 extras, counted separately. The plugin-list route shows the same rows as labelled entries. Owner checked on PC and Fire TV (2026-10-12, 1.3.1).

## DEC-063 — Launcher add-on for the Video add-ons tile (1.3.1)
- **Status:** Approved (2026-10-12), owner-tested on the PC.
- **Answer:** A plugin tile in Video add-ons always opens Kodi's folder screen before the plugin runs (Kodi gives any add-on with a plugin extension a `plugin://` path). AniVerse's tile is now the small script add-on `script.aniverse` (`<provides>video</provides>`), which calls `RunPlugin(plugin://plugin.video.aniverse/launch)`; the `launch` route opens the AniVerse window, or the classic lists when "AniVerse look" is off.
- **Consequences:** `plugin.video.aniverse` has no `<provides>` (no second tile) and imports `script.aniverse`, so repository installs and updates pull the launcher in. `tools/build.py` publishes three add-ons; `tools/dev_kodi.py install` installs both. Owner checked on PC and Fire TV (2026-10-12). First update on the stick failed with "dependency on script.aniverse could not be satisfied" until the repository data refreshed (GitHub Pages caches up to 10 min); installing the launcher from the repository first, then updating, worked.


## DEC-064 — Simplified sidebar; My TorBox moves into Settings
- **Status:** Implemented (2026-10-13); owner check on PC and Fire TV pending.
- **Answer:** The AniVerse sidebar shows Home, Search, Continue Watching, My Anime List, Favourites, then a collapsible Explore entry (Trending Now, Most Popular, Airing This Season, Upcoming, Genres, Recently Aired) with a purple-to-cyan accent beside the open group. Explore starts closed each time AniVerse opens and toggles in place (OK on Explore). Settings is a separate button anchored at the bottom; it opens a small menu: AniVerse settings (Kodi's add-on settings, unchanged, incl. the TorBox API key / Real-Debrid account) and My TorBox / My Real-Debrid (the same cloud-library grid as before).
- **Consequences:** No setting ids changed, so saved keys and logins stay. The sidebar list must fit without scrolling (test) because the accent bar is drawn at a fixed position. Continue Watching progress moved under the card text (cyan). The classic lists ("AniVerse look" off) keep their old menu.

## DEC-065 — Continue Watching: started shows only, next-episode availability
- **Status:** Implemented (2026-10-13); owner check on PC and Fire TV pending.
- **Answer:** A show is in Continue Watching only when started: an episode part-watched in AniVerse, or at least 2 episodes done (MAL count 1 = not started). Shows whose saved MAL entry is Completed, Dropped or On Hold are left out; one card per show; never an episode past the end of a finished series. The next episode's state is checked before it is offered as playable: AniList airing data first (not aired → Upcoming, with AniList's airing time when known; no search), then the configured providers through the source list's own search, filters and 1 h cache (`sources/availability.py`). Available → plays; Not available (all providers answered, nothing passes the filters) and Availability unknown (a provider failed, or airing cannot be told) → search again (`play?refresh=1`); Upcoming → show page.
- **Consequences:** Checks run in the background per card (at most 20 per screen, 2 searches at once); one failing check only marks its own card unknown. All-failed searches are remembered 10 minutes. Results warm the source cache, so pressing Play afterwards opens the list at once. With "Dub only" on, Available means a dub / dual-audio source passes the filters; sources only without a dub mark show "Sub only" (blue dot, OK opens the source list, which offers them). Classic lists ("AniVerse look" off) are unchanged.
- **Amendment (2026-10-13):** The MyAnimeList status grids (all but Completed) show the same next-episode state for each show (episode = MAL count + 1; kept as "watched/total" once caught up with the last episode). There the card still opens the show page. Grids check the rows around the selection as the owner scrolls (18 cards), not the whole list.

## DEC-066 — Add to / remove from MyAnimeList in the long-press menu
- **Status:** Implemented (2026-10-13); owner check pending.
- **Answer:** The long-press menu of a show card (also Continue Watching cards now) offers "Add to MyAnimeList" (choose Plan to Watch, Watching, Completed, On Hold, Dropped) when the show is not on the owner's list, or "Remove from MyAnimeList" (confirm first) when it is. Sent at once with the MAL login (`myanimelist/listedit.py`; DELETE `/anime/{id}/my_list_status`), not through the sync queue. Completed sends every episode as watched; other statuses send the episodes watched in AniVerse. Removing also drops a queued watch change for the show (it would re-add it).
- **Consequences:** Saved MAL entry, Watching list and status-list pages are dropped, so lists and the My Anime List counts show the change. Not logged in: Add explains where to log in. MAL unreachable: no MAL option in the menu. Failures show a notification; nothing is retried.

## DEC-067 — Cinematic UI (NovaFlix 0.4.0)
- **Status:** Implemented (2026-10-23); owner check on PC and Fire TV pending.
- **Answer:** Every NovaFlix screen and popup takes the "Cinematic Premium" look the owner chose from concept previews (`docs/superpowers/specs/2026-10-23-cinematic-ui/`). Near-black ground `#05070A`, cyan `#00A6D6` the one accent, no purple or blue; 10 px cards, pill buttons, white focus rings on cards and cyan on buttons, no glow or gradient buttons. An add-on cannot ship fonts, so the big titles are TMDB title logos (English, else language-less; text in the skin's font when a title has none). The sidebar is an icon rail that opens into the Netflix-style menu while it has focus. Grids and More like this show the focused title above them. Genres has Films / Shows tabs. Kodi's own OK box and pick lists are replaced by NovaFlix dialogs; the on-screen keyboard, toasts and Settings stay Kodi's.
- **Consequences:** The layouts' repeating parts are written by `tools/gen_layouts.py` between `<!-- gen:NAME -->` markers (`test_generated_sections_are_current`); edit the generator, not the XML. Only the colours listed in `tools/gen_layouts.py` may appear in layouts (`test_layouts_use_only_the_cinematic_palette`). Title details now ask TMDB for `images` (one request, cached as before; old cache entries load without a logo). The MyAnimeList status-card view and its IDs are gone.
