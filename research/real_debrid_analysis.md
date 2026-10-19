# Real-Debrid: Otaku integration (Part A), official API (Part B), recommendation (Part C)

Reference: Goldenfreddy0703/Otaku HEAD 420666d (v5.3.3). Paths relative to `plugin.video.otaku/resources/lib/` unless noted.
Docs fetched 2026-10-10 from https://api.real-debrid.com/ (the `/rest/1.0/` URL returns HTTP 404; the docs live at the site root).
Tags: CONFIRMED = read in source or in cited doc. ASSUMPTION / UNVERIFIED = inferred or not found in an authoritative source.
No real tokens were read or printed. Two third-party credentials embedded in Otaku source are referred to by location only.

---

# PART A - Otaku's Real-Debrid integration

Single class `RealDebrid` in `debrid/real_debrid.py` (354 lines). Cache classification lives in `debrid/__init__.py` and `debrid/debrid_cache.py`. HTTP is done by Otaku's own urllib wrapper `ui/client.py`.

## A1. Account authorization

- Flow: **OAuth2 "device flow for open source apps"** (CONFIRMED, `real_debrid.py:49-102`). Matches the official sequence in Part B.
  1. `GET https://api.real-debrid.com/oauth/v2/device/code?client_id=<id>&new_credentials=yes` (`real_debrid.py:57-61`, base URL `:20`).
  2. Shows `https://real-debrid.com/device` plus the `user_code` (and copies it to clipboard), and a QR code of the plain device URL (`:72-86`). The QR encodes only the URL, not the user code (CONFIRMED `:79`). Uses `script.module.pyqrcode` (`addon.xml:7`) and a custom progress window (`windows/progress_dialog.py`).
  3. Polls `GET /oauth/v2/device/credentials?client_id=..&code=<device_code>` every `interval` s until `expires_in` runs out or the user cancels (`:90-99`, `auth_loop` `:27-47`). Success returns a **per-user `client_id` + `client_secret`**, which are saved (`:39-42`).
  4. `POST /oauth/v2/token` with `client_id`, `client_secret`, `code=<device_code>`, `grant_type=http://oauth.net/grant_type/device/1.0` (`token_request`, `:104-128`). Saves `access_token`, `refresh_token`, and `expiry = now + expires_in`.
  5. `status()` (`:130-144`) calls `GET /rest/1.0/user`, stores username and account type, warns if not `premium`.
- **client_id handling** (CONFIRMED): the add-on ships a bootstrap id in `context.otaku/info.db` table `info`, row `Real-Debrid`, column `client_id` = `X245A4XAIBGVM`. This is the **public shared open-source client id** that RD documents for open-source apps (https://api.real-debrid.com/ ; "Open source apps may use the shared client ID `X245A4XAIBGVM`..."). It is not a secret. It is loaded via `database.get_info('Real-Debrid')` (`real_debrid.py:8-11, 54-55`; `ui/database.py:462-465`; db path `ui/control.py:72`). After step 3 the settings hold the per-user client id/secret which overrides the bootstrap id (`real_debrid.py:8-9`). `client_secret` column in info.db is empty for RD (verified by reading the sqlite row read-only).
- Entry points: plugin route `auth/realdebrid` (`Main.py:1599-1603`), exposed as a button `realdebrid.auth_start` (`settings.xml` ~1830, `RunPlugin(plugin://plugin.video.otaku/auth/realdebrid)`).
- Not supported: private API token entry (no code path to type in a token for RD; compare EasyDebrid which asks for an API key, `debrid/easydebrid.py:19`).

## A2. Token management / refresh

- Stored settings: `realdebrid.client_id`, `realdebrid.secret`, `realdebrid.token`, `realdebrid.refresh`, `realdebrid.expiry` (int epoch), plus `realdebrid.username`, `realdebrid.auth.status` (`real_debrid.py:8-14, 122-124`; declared `settings.xml:4145-4175`, all `<level>4</level>` hidden internal settings).
- Header: `Authorization: Bearer <token>` (`real_debrid.py:24-25`).
- Refresh: `refreshToken()` (`real_debrid.py:146-172`) does `POST /oauth/v2/token` with `grant_type=http://oauth.net/grant_type/device/1.0`, `code=<refresh_token>`, `client_id`, `client_secret` - exactly the documented refresh call. Updates token, refresh token, expiry, username.
- **Gap (CORRECTED by lead reviewer 2026-10-10):** `refreshToken` is invoked (a) manually via route `refresh/realdebrid` (`Main.py:1625-1628`) / settings button, and (b) **once at Kodi startup** by `service.py:12-24` (`refresh_apis()`, called at `service.py:314`), which reads `realdebrid.expiry` and refreshes if within 600 s of expiry. There is **no periodic refresh** while Kodi stays running (the service then only waits in `Monitor().waitForAbort()`, `service.py:340`) and **no 401-triggered refresh/retry** in `real_debrid.py`. So on a long-running device (TV boxes are rarely restarted) an expired access token makes RD calls return `None`/`[]`, surfacing as "BAD LINK" or empty results until restart or manual refresh. The new add-on must refresh proactively (before `expiry`, checked at call time, not only at startup) and reactively (on HTTP 401 / error_code 8).
- `enabled_debrid()` treats RD as usable when `realdebrid.token != ''` and `realdebrid.enabled` (`ui/control.py:153-155`) - an expired token still counts as enabled.

## A3. Account status

- `GET /rest/1.0/user` (`real_debrid.py:130-144`, again after refresh `:163-167`): reads `username` and `type`; warns if `type != 'premium'`. Does not read `premium` seconds/`expiration`, does not check traffic or active torrent limits.
- Not used: `/torrents/activeCount`, `/traffic`.

## A4. Link processing (magnets / hashes / unrestrict)

All via `ui/client.py` `get/post/delete` (urllib with sessions, Cloudflare handling; `real_debrid.py:3`).

| Method | Endpoint | Code |
|---|---|---|
| `addMagnet(magnet)` | `POST /torrents/addMagnet` form `magnet=` | `real_debrid.py:174-179` |
| `torrentSelect(id, 'all')` | `POST /torrents/selectFiles/{id}` form `files=all` | `:193-196` |
| `torrentInfo(id)` | `GET /torrents/info/{id}` | `:187-191` |
| `list_torrents()` | `GET /torrents` | `:181-185` (no paging params; default page of 100 per docs) |
| `resolve_hoster(link)` | `POST /unrestrict/link` form `link=` -> returns `download` field | `:198-204` |
| `deleteTorrent(id)` | `DELETE /torrents/delete/{id}` (timeout 10) | `:206-208` |

- Identifier given to RD is a magnet, never a `.torrent` upload: cached path rebuilds `magnet:?xt=urn:btih:<hash>` from the infohash (`windows/resolver.py:338`); uncached path uses the stored magnet with `dn=` (`real_debrid.py:284`, torrentio magnet `pages/torrentio.py:145`).
- `torrentSelect` returns `response is not None` (`:196`) - i.e. true even for an HTTP error response object (the Response object is returned for failures too, `client._build_response` `ui/client.py:680-702`, `status_code 0` only on total failure). Treat selectFiles success as unchecked. CONFIRMED by reading.
- Not used: `/torrents/addTorrent`, `/downloads`, `/streaming/*`, `/unrestrict/check`, `/hosts`.

## A5. Availability / cache check (RD removed instantAvailability)

- Old code called `GET /torrents/instantAvailability/{hash}` (`resolve_single_magnet`); it was removed in commit **fbc473b "Updated Version v5.2.85 - v5.2.86"** (2026-04-05) which replaced it with the comment "DMM handles cache checking - just add the magnet directly" (CONFIRMED via `git show fbc473b`; current code `real_debrid.py:220-255`). `grep -rn instantAvailability` on HEAD returns nothing.
- Current approach (CONFIRMED, `debrid/__init__.py:123-154`, `debrid/debrid_cache.py:76-207`):
  1. Local sqlite table `debrid_cache(hash, debrid, cached, expires)` with 24 h TTL (`debrid_cache.py:24-60`).
  2. Unknown hashes need an IMDb id (from Otaku's id mapping). If none, no external check -> hash is classed **uncached** (`__init__.py:137-139, 148-154`).
  3. External oracles run in parallel with 7 s timeouts:
     - **Torrentio with a hard-coded RD token** embedded in the URL (`debrid_cache.py:112`); streams whose `name` contains `+` (Torrentio's "cached on RD" marker) and have a `url` have their 40-char hash regexed out of the URL (`debrid_cache.py:113-123`). The embedded value is a third-party credential belonging to someone else's RD account/Torrentio profile (unclear whose; do NOT reuse). Request goes through Otaku's client, which logs failing URLs (see A9).
     - **Debrid Media Manager** `POST https://debridmediamanager.com/api/availability/check` with body `{dmmProblemKey, solution, imdbId, hashes<=100}`; the `solution` is computed locally by a reverse-engineered anti-bot hash ported from POV (`debrid_cache.py:176-207, 216-254`). Fragile and against the grain of any official API (ASSUMPTION that DMM can change it at any time; the code itself comments "ported from POV").
  4. Results (True/False) cached in sqlite for 24 h.
- Consequence: "cached" in Otaku means "reported cached by Torrentio-RD or DMM". It is a heuristic, not an RD guarantee. Truth is only learned at addMagnet -> info (`status == 'downloaded'` immediately).
- Official docs do not list instantAvailability (Part B).

## A6. Playback URL resolution (cached source)

`RealDebrid.resolve_single_magnet` (`real_debrid.py:220-255`), called from `windows/resolver.py:342`:
1. `addMagnet(magnet)` -> `{id, uri}`.
2. `torrentSelect(id)` -> selects **all** files (no per-episode select; wasteful for big packs and can hit torrent size/active limits).
3. `torrentInfo(id)` -> `files[]`, `links[]`, `status`. Note: if the torrent is not actually cached, `status` is not `downloaded` and `links` is empty. Code does NOT check `status` here; `files['links'][...]` then raises IndexError which is caught (`:241, 252`) -> returns None.
4. Pick file (A7), index into `links[]`.
5. `resolve_hoster(link)` -> `POST /unrestrict/link` -> `download` (direct CDN URL).
6. `deleteTorrent(id)` always (`:254`). (Cached path ignores the `realdebrid.autodelete` setting; only the uncached path honors it, `:348`.)
- Resolver then HEADs the URL (`resolver.py:360-399`) and passes it to Kodi (`playback_trace.md` steps 7-9).
- Uncached/background flow: `resolve_uncached_source` (`:279-354`) adds the magnet, selects all, polls `torrentInfo` in a loop while status not in `[downloaded, error]`, using `control.wait_for_abort(5)` for spacing, with a progress dialog; no overall timeout (loop ends on user cancel/abort). Statuses displayed: status, progress, seeders, speed. "Run in Background" just notifies and returns (`:307-309`). Cloud inspection later shows finished items (`pages/debrid_cloudfiles.py`).

## A7. File selection inside packs

- `source_utils.get_best_match('path', files, episode, pack_select, filename)` (`ui/source_utils.py:422-445`):
  - drops non-video extensions (uses Kodi's `getSupportedMedia('video')`, `:735-742`);
  - if `filename` hint (Torrentio `behaviorHints.filename`) is a substring of a path, returns it immediately (`:430-431`);
  - else regex `get_cache_check_reg(episode)` (`:277-293`) matches `S?E?|x|episode|ep|_|-|(` followed by zero-padded ep num (2/3/4 digits) not adjacent to another digit; keeps matches, sorts by match length, and if more than one remains asks the user via `select_dialog('Select File', ...)` (`:442-443`, `user_select :745-751`).
  - `pack_select=True` (the "File Select" context action) skips matching and always shows the picker (`:434-435`).
  - If no regex match: returns `{}` -> resolution fails (`:437-440`).
- Single-file torrents skip matching (`real_debrid.py:243-244`). The index mapping `selected_files[i] <-> links[i]` relies on RD returning `links` in order of the *selected* files (ASSUMPTION about RD API contract; docs only say `links` is an array of host URLs, `files[].selected` is 0/1).
- Known weaknesses: season-agnostic regex (absolute numbering vs S01E05 vs batch with multiple seasons can mismatch), no OVA/special handling, `episode_re` is a zero-padded string passed as `episode` (`resolver.py:342`).

## A8. Error handling

- No HTTP status inspection and no RD `error_code` parsing anywhere in `real_debrid.py` (grep: none). Failures degrade to `None`/`[]`; the user-facing signals are a few ok-dialogs: "Failed to connect to Real-Debrid", "Failed to get Real-Debrid token", "Failed to get Real-Debrid user info", "BAD LINK" (`real_debrid.py:63, 117, 133, 265, 269, 287, 293`).
- No retry/backoff, no 429 handling, no handling for error codes 21 (too many active downloads), 23 (traffic exhausted), 35 (infringing file), 36 (fair-usage limit) which are documented (Part B). These all just look like "no stream".
- Resolver wraps `resolve_source` in try/except, logs `Error resolving source with <provider>: <exc>` at error level and continues (`windows/resolver.py:356-358`).
- HTTP client: custom urllib wrapper, default timeout 20 s (`ui/client.py:705`), logs `Request-HTTPError (code): url` at debug level for non-extended output (`ui/client.py:497`). For `output='extended'` (which `get/post` use, `client.py:707-722`) errors are returned as tuples; behaviour on 4xx not verified in detail.

## A9. Logging and secret redaction

- Logging goes through `control.log` -> `xbmc.log` with default level DEBUG (`ui/control.py:131-142`). No central redaction helper exists (grep for `redact|mask` in debrid/ui: none).
- Tokens are NOT logged by RD code: only `'refreshed realdebrid.token'` (`real_debrid.py:168`) and exception strings of KeyError/ValueError (`:45, 128, 144, 170`) which contain key names, not values. The Authorization header is never logged (CONFIRMED by grep of `log(` with token/header terms).
- Leak risks (CONFIRMED by reading):
  - `ui/client.py:497, 502` log the full request URL on errors. For `_tio_check_cache` the URL contains the embedded third-party RD credential (`debrid_cache.py:112`).
  - `windows/resolver.py:386` raises `Exception('could not resolve %s ...' % link)` containing the unrestricted RD download URL (semi-sensitive: usable by anyone with the link until it expires/IP-bound; ASSUMPTION on expiry rules). That text can end up in logs (`resolver.py:357`).
  - `control.getSetting` caches values in a **Kodi Home-window property** (`ui/control.py:200-208`), readable by any other add-on/skin via `Window(Home).getProperty`. The RD token read through `getSetting` is therefore held in a window property for the session (ASSUMPTION about cache population path in `_settings_cache`/`homeWindow`: the read path is confirmed, the write-back path not examined).
- Recommendation for new add-on: wrapper that never passes headers/URLs with query tokens to logs; mask `Bearer`, `auth_token=`, `refresh`, and unrestricted download hosts; log only error_code + endpoint path.

## A10. Settings and persistence

- Kodi add-on settings (plain text XML in the add-on's `userdata/addon_data/plugin.video.otaku/settings.xml`, ASSUMPTION about location - standard Kodi behaviour, not Otaku-specific): `realdebrid.client_id`, `.secret`, `.token`, `.refresh`, `.expiry`, `.username`, `.auth.status`, `.enabled`, `.autodelete` (`settings.xml:1800, 1849, 4145-4175`). Stored unencrypted. Kodi has no keychain API.
- Local sqlite `cache` (provider results, 8 h) and `debrid_cache` (RD hash states, 24 h) in `control.cacheFile` (`debrid/debrid_cache.py:24-60`; `ui/database.py:166-206`).
- Bootstrap client id: read-only `context.otaku/info.db` shipped with the context add-on.
- User-facing options relevant to RD: `realdebrid.enabled` (default false), `realdebrid.autodelete` (default true), `provider.*`, `show.uncached` (default true).

## A11. Bottom line on Otaku RD

Good: correct device-flow-for-open-source-apps implementation including refresh grant; clean small class; per-user credentials obtained.
Bad: no automatic refresh or 401 handling; no status checks; select-all-files; cache check depends on two third-party hacks (hard-coded foreign credential, reverse-engineered DMM solver); heuristics when IMDb id is missing; deletes cached torrent after unrestrict (fine); can leave stray torrents if the process dies mid-flow (deleteTorrent not in finally).

---

# PART B - Official Real-Debrid API

Primary source: https://api.real-debrid.com/ (single-page docs). Fetched 2026-10-10. Everything under "CONFIRMED" is from that page unless another URL is given. The WebFetch tool summarizes pages; wording below is paraphrased except where in quotes.

## B1. Basics (CONFIRMED, https://api.real-debrid.com/)
- REST base `https://api.real-debrid.com/rest/1.0/`; OAuth2 base `https://api.real-debrid.com/oauth/v2/`. The URL `https://api.real-debrid.com/rest/1.0/` itself returns HTTP 404 (fetched).
- Verbs GET/POST/PUT/DELETE; `X-HTTP-Verb` override header; successful JSON 200; errors: 4xx/5xx with JSON `{error, error_code?}`; UTF-8 strings; ETag/If-None-Match supported; dates in JS `toJSON` format; all methods need auth unless stated.
- **Rate limit: "The API is limited to 250 requests per minute."** Refused requests return 429 and still count; brute-forcing can lead to an indefinite block. CONFIRMED.

## B2. Authentication options (CONFIRMED)
| Option | Use | Notes |
|---|---|---|
| Private API token | Personal scripts | Sent as `Authorization: Bearer <token>` or `?auth_token=`. Docs: "Do not use your private API token in public applications... grants access to all methods." Obtainable from the user's account page (page location not on the API doc - UNVERIFIED; commonly https://real-debrid.com/apitoken). |
| OAuth2 device flow (mobile apps) | Registered app with own client_id/secret | `/device/code?client_id=` -> `device_code, user_code, interval (5), expires_in (1800), verification_url`; poll `/token` with client_id, client_secret, code, `grant_type=http://oauth.net/grant_type/device/1.0` every 5 s. |
| **OAuth2 device flow for open-source apps** | Apps without own registration | `/device/code` with `client_id` + `new_credentials=yes`; poll `/device/credentials?client_id&code` every 5 s until it returns a user-bound `client_id`+`client_secret`; then POST `/token` with those + device code + device grant type. "Do not redistribute these credentials. Usage with another account displays the owner's UID alongside the app name." |
| Shared open-source client id | `X245A4XAIBGVM` | Allowed scopes: unrestrict, torrents, downloads, user. "This client ID can have stricter limits than service limits due to poorly designed apps using it." |
| Three-legged OAuth2 (websites) | `/auth`, `/token` | needs redirect URI; not suitable for TV. |
| Legacy password grant | Old apps | needs special approval; includes 2FA grant types. Not recommended. |
- Registering an app: "Create an app in your control panel to receive a client_id and client_secret." (CONFIRMED statement; where exactly in the panel and any approval step are UNVERIFIED.)

## B3. Token lifetime and refresh
- Access token response: `access_token, expires_in (seconds), token_type "Bearer", refresh_token`. CONFIRMED.
- Docs do not state a fixed lifetime: "expires_in: token validity period, in seconds". Concrete value (e.g. 1 hour) = **UNVERIFIED**; always compute from `expires_in`.
- Refresh tokens "only expire when your application rights are revoked by user". CONFIRMED.
- Refresh: `POST /oauth/v2/token` with `client_id`, `client_secret`, `code=<refresh_token>`, `grant_type=http://oauth.net/grant_type/device/1.0`. CONFIRMED. Response contains a new access token (and a `refresh_token`; Otaku stores the returned one, `real_debrid.py:157-158`; whether RD rotates it per refresh is UNVERIFIED -> always store the new value).
- Revoke: `GET /disable_access_token` -> 204 (401 if already invalid). CONFIRMED.

## B4. Error codes (CONFIRMED, docs error table)
| error_code | Meaning | | error_code | Meaning |
|---|---|---|---|---|
| -1 | Internal server error | | 20 | Hoster unavailable to free users |
| 1 | Missing parameter | | 21 | Too many active downloads |
| 2 | Invalid parameter value | | 22 | IP address not permitted |
| 3 | Unknown method | | 23 | Traffic quota exhausted |
| 4 | Method not allowed | | 24 | File unavailable |
| 5 | Slow down (rate limited) | | 25 | Service unavailable |
| 6 | Resource unreachable | | 26 | Upload too large |
| 7 | Resource not found | | 27 | Upload error |
| 8 | Invalid token | | 28 | File type not allowed |
| 9 | Permission denied | | 29 | Torrent too large |
| 10 | 2FA required | | 30 | Invalid torrent file |
| 11 | 2FA pending | | 31 | Action already done |
| 12 | Wrong login | | 32 | Image resolution error |
| 13 | Wrong password | | 33 | Torrent already active |
| 14 | Account locked | | 34 | Too many requests |
| 15 | Account not activated | | 35 | Infringing file |
| 16 | Unsupported hoster | | 36 | Fair usage limit reached |
| 17 | Hoster under maintenance | | 37 | Endpoint disabled |
| 18 | Hoster quota reached | | | |
| 19 | Hoster temporarily unavailable | | | |

HTTP codes: 200 JSON, 201 created (addTorrent/addMagnet), 202 action already done (selectFiles), 204 no body, 400 bad request, 401 bad/expired/invalid token, 403 permission denied / account locked / not premium, 404 unknown resource, 429 rate limit, 503 service/file unavailable. CONFIRMED.
Relevant for this project: 8/401 -> refresh then retry once; 34/429/5 -> backoff; 21/23/36 -> tell user (not "BAD LINK"); 35 -> content blocked; 37 -> endpoint disabled (watch for this on removed endpoints); 22 -> IP/VPN issue.

## B5. Endpoints relevant to the add-on (CONFIRMED, listed in docs)
| Endpoint | Purpose / key facts |
|---|---|
| `GET /user` | id, username, email, points, locale, avatar, `type` (free/premium), premium seconds left, expiration. 401 bad token, 403 account locked. |
| `POST /unrestrict/link` | params `link` (req), `password`, `remote` (0/1). Returns generated link; fields (per docs block, mapping partly inferred by the fetch tool): `id`, `filename`, `host`, `filesize`, `download` ("Generated link"), `streamable`. 401/403. |
| `POST /unrestrict/check` | No auth. Checks host-file downloadability. |
| `POST /unrestrict/folder`, `PUT /unrestrict/containerFile`, `POST /unrestrict/containerLink` | folder/container decryption; not needed. |
| `GET /torrents` | list; `offset`, `page` (priority over offset), `limit` 0-5000 default 100, `filter=active`. |
| `GET /torrents/info/{id}` | fields: id, filename, original_filename, hash, bytes, original_bytes, host, split, progress, status, added, files[{id,path,bytes,selected 0/1}], links[] (host URLs), ended, speed, seeders. |
| Torrent `status` values | magnet_error, magnet_conversion, waiting_files_selection, queued, downloading, downloaded, error, virus, compressing, uploading, dead. |
| `GET /torrents/activeCount` | active count and limit. |
| `GET /torrents/availableHosts` | upload hosts + max sizes. |
| `PUT /torrents/addTorrent?host=` | upload .torrent; 201 `{id, uri}`; 403 if not premium. |
| `POST /torrents/addMagnet` | params `magnet` (req), `host`; 201; errors 400/401/403/503. |
| `POST /torrents/selectFiles/{id}` | `files` = comma-separated file ids or `all`; 204; 202 already done; 400/401/403/404. Starts the torrent (instant if cached). |
| `DELETE /torrents/delete/{id}` | 204. |
| `GET /downloads`, `DELETE /downloads/delete/{id}` | list/delete generated-download history. |
| `GET /hosts`, `/hosts/status`, `/hosts/regex`, `/hosts/regexFolder`, `/hosts/domains` | hoster info (most no auth). |
| `GET /time`, `/time/iso` | server time, no auth. |
| `/traffic`, `/streaming` (transcode, media info), `/settings` | documented; not examined further. |
- Not UNVERIFIED but "not found in docs": any endpoint to test cache state of a hash. See B6.

## B6. `/torrents/instantAvailability` status
- **Not present in the current official docs** (fetched 2026-10-10): the page lists no such endpoint (CONFIRMED by absence; the fetch tool reported none). Error code 37 "Endpoint disabled" exists in the table (CONFIRMED) - consistent with disabled endpoints, though the doc does not say which.
- External reporting (secondary sources, not RD's own notice):
  - TorrentFreak, 2024-11-22: RD "will also deactivate" its API ("could be used by third-party services and applications"), and "the instantAvailability feature"; Kodi named as a media center that could use the API. https://torrentfreak.com/real-debrid-implements-extreme-anti-piracy-filters-to-appease-film-companies-241122/ (CONFIRMED that the article says this; planned action, not a record of execution).
  - ElfHosted, 2024-11-22: Stremio add-ons configured for RealDebrid errored/returned no results after the change. https://store.elfhosted.com/blog/2024/11/22/stremio-after-realdebrid/
  - Heise, same period, anti-piracy filters (filename filtering, private-tracker hash blocking). https://heise.de/-10180564
- The RD *API itself* was not shut down: Otaku's addMagnet/selectFiles/info/unrestrict flow works against it in 2026 (Otaku HEAD still ships it; ASSUMPTION - I did not execute anything, only read that the code and docs agree).
- Net: no official way to ask "is this hash cached?" without adding the magnet. Workarounds in the wild: (a) addMagnet + selectFiles + info and check `status == "downloaded"` (what Otaku effectively does at resolve time); (b) third-party oracles (DMM, Torrentio-with-RD, AIOStreams, Comet etc.); (c) user's own cloud list `GET /torrents`.

## B7. Terms-of-service constraints relevant to third-party apps
- RD Terms, https://real-debrid.com/terms (fetched 2026-10-10, CONFIRMED quotes): "The User's account is for personal use only."; "Connections to the User's account are recorded so that we can detect account sharing."; "Any account sharing or generated links sharing will lead to a suspension of the User account."; "...nor managing it for somebody else without our explicit permission"; "The User certifies that he will not use a dedicated server, VPS or any cloud service on our service"; "...not to use our service to download copyright infringement digital files". The terms page does not mention the API or multiple-IP rules.
- Multi-IP rule (account usable from any single IP but not more than one concurrently) appears only in forum quotes of the RD help pages; UNVERIFIED against an official page.
- API docs rule: don't use the private token in public apps; don't redistribute per-user credentials; shared client id may be rate-limited harder (B2).
- Implications for a personal add-on: your own account on your own devices behind one IP is the intended use; no sharing of tokens/links/add-on config; don't host the add-on as a proxy service; avoid cloud/VPS execution; no publishing of unrestricted links.
- Legal posture of the *content* is on the user. This research doc does not assess it.

---

# PART C - Recommended design for the personal Kodi add-on (Android TV / Fire TV primary)

## C1. Auth flow: OAuth2 device flow, QR + user code
- **Primary: device flow for open-source apps** (B2) using the shared client id `X245A4XAIBGVM` as bootstrap (it is explicitly provided for open-source apps; a *personal, unpublished* add-on is outside the strict wording but is the same use case - UNVERIFIED whether RD cares; no restriction found). Sequence as in A1, but improved:
  1. `GET /oauth/v2/device/code?client_id=X245A4XAIBGVM&new_credentials=yes`.
  2. Show a Kodi dialog with `verification_url`, the **user code in large text**, and a QR of the verification URL with the code appended if RD accepts it (UNVERIFIED; RD's `verification_url` field from the response should be used verbatim instead of hard-coding `real-debrid.com/device` as Otaku does). Fire TV/Android TV users will usually scan the QR with a phone.
  3. Poll `/device/credentials` every `interval` seconds (docs: 5) until `expires_in` (docs: 1800); handle cancel and expiry; on success persist the returned per-user `client_id`/`client_secret`.
  4. `POST /token` -> save `access_token`, `refresh_token`, `expires_at = now + expires_in`.
  5. `GET /user` -> show username, premium state and expiry date; refuse to continue when `type != premium` (addMagnet requires premium, 403).
- **Optional second path:** paste a private API token (docs allow `Bearer <private token>`) for a personal install only - simple fallback when QR/polling is awkward on a TV. Mark it non-default; never display it back; never log it.
- **Own app registration** (alternative to the shared id): create an app in the RD control panel to get a dedicated client_id/secret (B2). Benefit: not subject to the shared id's stricter limits and misuse throttling; no UID shown as "another account". Requirement/process details UNVERIFIED (docs only say "create an app in your control panel"). If used, flow = the standard mobile device flow (no `new_credentials`, secret is yours and must be kept in the add-on configuration, not in a repo).
- Refresh strategy (fixing Otaku's gap): refresh when `now > expires_at - 60 s` and on any 401/error_code 8 (retry once); single-flight lock; store new refresh token if returned.
- Storage: Kodi `Addon.setSettingString` is plaintext in userdata; acceptable for personal device; set file permissions where possible; don't mirror tokens in window properties; keep tokens out of logs (A9).

## C2. Resolution algorithm for the new add-on (cache-agnostic, quota-friendly)
1. For each candidate (infohash + optional trackers), `POST /torrents/addMagnet` -> `id`.
2. `GET /torrents/info/{id}` once; if `status == waiting_files_selection`, choose the episode file ids from `files[]` (path + bytes), then `POST /torrents/selectFiles/{id}` with **just that file id** instead of `all` (cuts size/limit problems; UNVERIFIED that every cached torrent honors single-file select instantly - standard behaviour in other clients).
3. `GET /torrents/info/{id}` again: `status == downloaded` -> `links[]` are available (map the selected files to links in order); else it is not instantly available.
4. `POST /unrestrict/link` for the chosen link -> `download`.
5. `DELETE /torrents/delete/{id}` in a `finally`.
- Wrap each call with error_code mapping (B4). Respect 250 req/min: a resolve is ~5-6 calls; polling uncached progress at >=5 s is OK.

## C3. Content authorized but uncached / unavailable
- Authorization does not change availability. With no instantAvailability, "cached" is only knowable after addMagnet+selectFiles+info (A5, B6).
- Cases:
  - **Cached:** info returns `downloaded` almost immediately with `links[]` -> unrestrict -> play (typical total a few seconds).
  - **Not cached:** statuses `magnet_conversion` -> `waiting_files_selection` -> `queued`/`downloading` (seeders/speed visible in `/torrents/info`) -> `downloaded` when RD finishes. Dead swarm -> `dead` / `magnet_error`, or stuck at 0 seeders. Offer the user: wait with progress (Otaku-style foreground), run in background (it appears in the cloud list `GET /torrents`), or cancel; always delete abandoned jobs.
  - **Blocked:** error_code 35 (infringing file) or filename/hash filtered (Heise report), `virus`, `error` -> mark source failed, try next.
  - **Limits:** 21 too many active downloads (use `/torrents/activeCount`), 23 traffic, 36 fair usage, 29 torrent too large.
- Show these states in the UI instead of a generic "BAD LINK".

## C4. Limitations and risks
- Shared client id may throttle harder (B2) -> support own client id and a private-token fallback.
- Cache oracles are unofficial; Otaku's depend on an embedded foreign credential and a reverse-engineered DMM solver (A5). For a personal build prefer: no pre-check, or use the user's own RD cloud list plus probe-on-select (manual select makes probing one item at a time cheap). If a pre-check is wanted, use a public oracle without embedded foreign credentials, label results "unconfirmed".
- Rate limits: 250 req/min; probing many hashes via addMagnet is expensive and clutters the account's torrent list; probe only on user selection.
- Account hygiene: delete probes; set autodelete; avoid parallel multi-IP use; do not share tokens.
- ToS: personal use only, no sharing, no VPS (B7). Anything running the add-on on a cloud box would breach the quoted terms.
- Documentation drift: RD docs are a single page, with no changelog; recheck error_code 37 and endpoint list periodically.
- Unknowns to test against a real account (not done here): actual `expires_in` value; whether the refresh token rotates; whether selectFiles with a subset on a cached torrent returns `downloaded` instantly; how `links[]` order maps when a subset is selected; whether the shared client id has per-id throttling in practice.

## C5. Source index
- Otaku code: `debrid/real_debrid.py`, `debrid/__init__.py`, `debrid/debrid_cache.py`, `windows/resolver.py`, `ui/source_utils.py`, `ui/client.py`, `ui/control.py`, `ui/database.py`, `Main.py:1599-1628`, `settings.xml:1800-1850, 4145-4175`, `context.otaku/info.db` (read-only), git commit fbc473b.
- RD docs: https://api.real-debrid.com/ ; RD terms: https://real-debrid.com/terms
- Secondary: TorrentFreak https://torrentfreak.com/real-debrid-implements-extreme-anti-piracy-filters-to-appease-film-companies-241122/ ; ElfHosted https://store.elfhosted.com/blog/2024/11/22/stremio-after-realdebrid/ ; Heise https://heise.de/-10180564


> Review note (2026-10-10): `debrid_cache.py` line citations in this file were corrected by the lead reviewer against HEAD `420666d` (file is 254 lines, CRLF). Other line numbers were spot-checked (`Main.py:1155`, `real_debrid.py` method lines) and matched.
