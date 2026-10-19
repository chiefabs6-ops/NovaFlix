# Platform compatibility notes for a personal Kodi anime add-on

Date: 2026-10-10. Tags: **CONFIRMED** = checked against a URL/file I fetched; **ASSUMPTION** = not verified, from general knowledge or inference.
Otaku citations are `path:line` at HEAD `420666d` (plugin.video.otaku v5.3.3), paths under `plugin.video.otaku/`.

## 1. Kodi versions and status

| Kodi | Status 2026-10-10 | Evidence |
|---|---|---|
| 20 Nexus | Old, previous-previous stable. Otaku's minimum (README "Kodi 20 Nexus or later"). | Otaku `/README.md` L5-12 (CONFIRMED) |
| 21 Omega | Current stable branch; latest release 21.3-Omega published 2025-10-31 (21.0 2024-04-06, 21.1 2024-08-17, 21.2 2025-01-17). | GitHub API `https://api.github.com/repos/xbmc/xbmc/releases` (CONFIRMED) |
| 22 Piers | **Not final yet.** `22.0rc1-Piers` tagged 2026-09-27 (prerelease); earlier `22.0b2` 2026-08-31, `22.0b1` 2026-06-21, `22.0a3` 2026-04-07. | same GitHub API (CONFIRMED). A web search only surfaced Beta 2 (kodi.tv article, dated Sept 2026), so the RC is newer than most press coverage. |

Kodi's own announcement pages: https://kodi.tv/article/kodi-22-piers-beta-1 (search result, not fetched in full). Recommendation: target Omega (21.x) as the primary, keep code that also works on Nexus 20 if cheap, and test on Piers once final.

## 2. Embedded Python and xbmc.python API version

| Kodi | `xbmc.python` addon API | Python bundled when built with Kodi's own depends (Android, Windows, macOS, iOS) | Evidence |
|---|---|---|---|
| 20.0 Nexus | 3.0.1 | 3.11.0 | `addons/xbmc.python/addon.xml` and `tools/depends/target/python3/Makefile` on tag/branch `20.0-Nexus`, https://raw.githubusercontent.com/xbmc/xbmc/20.0-Nexus/tools/depends/target/python3/Makefile (CONFIRMED) |
| 21.x Omega | 3.0.1 | 3.11.7 (same on 21.3-Omega) | `.../21.3-Omega/tools/depends/target/python3/Makefile` (CONFIRMED) |
| 22 Piers (rc1) | **3.1.0** | **3.14.6** | `.../22.0rc1-Piers/addons/xbmc.python/addon.xml` and `.../tools/depends/target/python3/Makefile` (CONFIRMED) |

Notes:
- The Makefile VERSION is what Kodi's `tools/depends` builds, and the official Android APK, Windows, macOS and iOS builds use that. Official Android builds therefore ship their own CPython (not Android's system Python; there isn't one). ASSUMPTION on a per-package basis for each third-party Kodi build: Linux distro builds link against the distro's system Python, which may differ (e.g. Debian/Ubuntu Python 3.11/3.12 for Omega).
- Piers raises xbmc.python to 3.1.0 and Python to 3.14. An add-on declaring `<import addon="xbmc.python" version="3.0.1"/>` should still install on Piers (Kodi's rule is that the host API must be >= the required version and compatible within the major: ASSUMPTION), but code should avoid anything removed in Python 3.12-3.14 (e.g. `imp`, `distutils`, `asyncore`, `datetime.utcnow()` deprecation warnings, `locale.getdefaultlocale`). Pure-stdlib code written for 3.8+ syntax is safe across all three. Do not use `match` or `type` statements or 3.12+ f-string tricks if you want Nexus compatibility (3.11 is fine for walrus, match).
- Kodi 19 Matrix was Python 3.8-ish and is out of scope.
- Otaku uses walrus operators and f-strings with `=` (`default.py` L33), which need 3.8+, and `3.0.1` as its API pin.

## 3. ListItem / InfoTagVideo changes

- Kodi 20 (python_v20) deprecated `ListItem.setInfo()` and related helpers in favor of `InfoTagVideo` setters from `listitem.getVideoInfoTag()`: header comments in `xbmc/interfaces/legacy/ListItem.h` of 22.0rc1-Piers: "`@python_v20 Partially deprecated. Use explicit setters in InfoTagVideo, InfoTagMusic, InfoTagPicture or InfoTagGame instead`" (L784), plus deprecations of `setUniqueIDs`, `setRating`, `addSeason`, `getUniqueID`, `getRating`, `getVotes`, `addAvailableArtwork`-style helpers, e.g. L363, L399, L427, L516, L548, L580, L818. Source: https://raw.githubusercontent.com/xbmc/xbmc/22.0rc1-Piers/xbmc/interfaces/legacy/ListItem.h (CONFIRMED).
- `setInfo` is **still present** in Piers rc1 (L647, L790 doc example), only documented as partially deprecated, so removal has not happened as of rc1 (CONFIRMED for rc1; future removal ASSUMPTION).
- Practical rule: for Nexus+ targets use `InfoTagVideo` exclusively. Otaku does so: `ui/control.py` L543-601 (`set_videotags`: `getVideoInfoTag()`, `setTitle`, `setMediaType`, `setTvShowTitle`, `setPlot`, `setYear`, `setPremiered`, `setGenres`, `setUniqueIDs`, `setIMDBNumber`, `setResumePoint`).
- API additions relevant to you: `InfoTagVideo.setResumePoint(position, total)` (Otaku passes total = 1 at `ui/control.py` L601, i.e. `setResumePoint(float(resume), 1)`; the second arg is total time, so check semantics before reuse - ASSUMPTION that a total of 1 is a quirk), `ListItem(offscreen=True)` for fast construction (Otaku `windows/resolver.py` L204), `xbmcplugin.addDirectoryItems` bulk add (`ui/control.py` L716).
- Kodi version-dependent behavior in Otaku: InputStream Adaptive property names changed between Nexus and Omega (<20.9 uses `manifest_type`, >21.8 uses `common_headers`), `windows/resolver.py` L523-561 (CONFIRMED in code; the meaning of the thresholds is Otaku's, ISA release notes not checked).

## 4. Android TV and Amazon Fire TV

### 4.1 Platform split (as of 2026-10-10)

- Amazon's newer Fire TV devices run **Vega OS** (Linux-based, not Android). Kodi (an Android APK) cannot be installed on Vega OS. AFTVnews tag page https://www.aftvnews.com/tag/vega-os/ (fetched via WebFetch, CONFIRMED) lists: Fire TV Stick 4K Select (first Vega device), Fire TV Stick HD 2026 (announced 2026-04-15 with Vega OS), the 3rd-gen Fire TV Stick 4K (announced 2026-09-30, Vega OS 2.0), and says "Vega OS doesn't support sideloading or Downloader" (article dated 2026-10-05) and quotes Amazon's developer page: "Starting with Fire TV Stick 4K Select, all future Fire TV Sticks will run on Vega."
- Still **Android-based Fire OS**: Fire TV Stick 4K Max (described as "the last remaining Android-based stick" on 2026-09-30) and Fire TV Stick 4K Plus (being replaced by the 3rd-gen 4K); Fire TV Cube is implied to be Fire OS; the older Fire TV Stick HD (replaced by the Vega HD) was Fire OS; AFTVnews 2025-11-18 says Fire OS runs on everything except the 4K Select (as of then). Also a search-result forum post claims 4K Max 2nd gen (2023) and earlier support sideloading (lower authority, ASSUMPTION).
- Amazon does not clearly mark Vega devices on product pages (AFTVnews 2026-10-05), so check the exact model before buying. **Practical rule: buy an older/used Fire OS stick/Cube or use an Android TV/Google TV device if Kodi is the goal.** Fire OS devices are not guaranteed to receive Kodi-friendly updates long-term (ASSUMPTION).
- Android TV / Google TV (Nvidia Shield, Chromecast with Google TV, Sony/TCL TVs, Xiaomi boxes): Kodi runs as an APK from the Play Store or from kodi.tv (ASSUMPTION based on Kodi's long-standing distribution; not re-verified for 2026).

### 4.2 Kodi sideload on Fire OS

- Fire OS needs "Install unknown apps" enabled for the installer app (Downloader), and Developer options/ADB debugging only if using adb. Kodi is available from kodi.tv as an APK; Amazon Appstore had a Kodi listing historically (ASSUMPTION; availability not verified). Steps are well covered by AFTVnews guide "How to Sideload Apps (e.g., Kodi)" referenced on the tag page above (guide itself not fetched).
- Kodi's own Android notes: for Piers Alpha 1, press coverage reports "Minimum Android version is now 7.0" (preshowexperience.com forum repost of the changelog; androidpctv.com coverage; ASSUMPTION since I could not open the official post). Older Fire OS 5 (Android 5.1) sticks would be outside Piers support; Fire OS 6 is Android 7.1 and OK (ASSUMPTION from Amazon version mapping).
- Architecture: Piers alpha/beta coverage on androidpctv.com still lists 32-bit (armeabi-v7a) and 64-bit (arm64-v8a) builds (CONFIRMED only as press coverage). Kodi's build script handles both CPUs, `cmake/scripts/android/ArchSetup.cmake` in 21.3-Omega and 22.0rc1-Piers has `armeabi-v7a` and `arm64-v8a` branches (CONFIRMED). Many Fire TV sticks run a 64-bit-capable CPU with a **32-bit userspace**, in which case the 32-bit (ARMv7a) Kodi APK is the one that works (ASSUMPTION; Kodi's download page advises ARMV7A for most Fire TV). It does not affect pure-Python add-ons except through memory limits (section 9).

### 4.3 Other Android TV specifics

- No keyboard: text entry uses Kodi's on-screen keyboard or a phone remote app. Design flows to avoid typing (search history, pick-lists, QR/device-code auth).
- The Back button maps to Kodi "previous menu"; long-press/Home leaves the app. Kodi may be killed in the background on low-memory sticks, which will end the service.
- Android "all files" storage permission is not relevant to add-on data, which lives in Kodi's private data dir (section 7).

## 5. Networking, TLS, HTTP libraries

- Python `urllib`/`ssl` in Kodi's embedded Python is available on all platforms. Otaku uses stdlib `urllib` plus a Kodi-bundled CA file: `CERT_FILE = special://xbmc/system/certs/cacert.pem` (`ui/client.py` L44, used in `ssl.create_default_context(cafile=CERT_FILE)` ~L288). Kodi ships that bundle in its resources, so TLS verification does not depend on the Android system CA store (CONFIRMED that Otaku references it; that the file ships on every platform is ASSUMPTION).
- `ssl.PROTOCOL_TLSv1_1` / `PROTOCOL_TLS` constants are deprecated in Python 3.10+ and may emit warnings; Otaku has branches for them (`ui/client.py` L243-259). Use `ssl.create_default_context(cafile=...)` plus `minimum_version = TLSv1_2` instead.
- `script.module.requests` is available from the Kodi Omega repo: v2.31.0, Apache-2.0, depends on certifi (MPL-2.0), chardet (LGPL-2.1), idna, urllib3 1.26.16 (https://mirrors.kodi.tv/addons/omega/addons.xml, CONFIRMED). Otaku does not use it. Options: stdlib `urllib` (no dependency, more code) or declare `script.module.requests` (convenient, but each dependency must install successfully on user's Kodi).
- Kodi's HTTP lib (`xbmcvfs.File` on `http(s)://` URLs, with `|Header=Value` option suffix) is another option but offers less control.
- Environment signals (Otaku `service.py` L238-243): log Python version, SQLite version, platform, Kodi version at start; useful for debugging device issues.
- Some Fire TV/ISP configs have IPv6 problems; Otaku ships settings routes to toggle IPv6 and HTTP/2 (`Main.py` L2331-2433, `toggle_ipv6`, `toggle_http2`): it edits Kodi's `advancedsettings.xml` (`ui/control.py` L76-78 `kodi_advancedsettings_path`). Avoid modifying files outside your add-on in a personal add-on unless essential.

## 6. Pure-Python constraint

Kodi add-ons ship Python source; compiled wheels (`cryptography`, `lxml`, `numpy`, etc.) are not available on Android/Fire OS ABIs unless packaged as Kodi `script.module.*` binary add-ons (rare). Therefore: pure-Python only. `sqlite3` is built into Kodi's Python (Otaku logs its version, `service.py` L242; `database_sync.py` L12-15). Crypto needs beyond `hashlib`/`hmac`/`base64` must be pure Python: Otaku vendors `pyaes` for AES (`ui/pyaes/`, `ui/jscrypto/pyaes.py`, MIT). For a debrid-only add-on you likely need no AES. Use `xml.etree`, `json`, `sqlite3`, `urllib`, `threading`, `concurrent.futures` from the stdlib (all used by Otaku).

## 7. Filesystem paths, data storage, permissions

- Per-add-on writable folder: `special://profile/addon_data/<addon.id>/`, obtained with `xbmcvfs.translatePath(addon.getAddonInfo('profile'))` (Otaku `ui/control.py` L64; CONFIRMED in code). On Android this resolves under the app's private storage (typically `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/userdata/addon_data/...` or the internal data dir depending on install: ASSUMPTION). Windows: `%APPDATA%\Kodi\userdata\addon_data\...`.
- Add-on install dir (`special://home/addons/<id>/`) is replaced on update; **never store user data there**. Otaku violates this lightly: it rewrites `addon.xml` in the install dir (`service.py` L214-235) and keeps `info.db` in the context add-on folder (`ui/control.py` L72) as read-only data. Both get overwritten by updates (`service.py` L245-249 re-applies the toggle after updates).
- Android permissions: Kodi itself holds the storage permissions; add-ons inherit them. Add-on code cannot request new Android permissions.
- Do not assume `os.getcwd()`; use `xbmcvfs.translatePath`. Use `xbmcvfs.exists/mkdirs` (Otaku `ui/database.py` L55-57). SQLite in WAL mode makes `-wal`/`-shm` sidecar files; on FAT/exFAT SD cards or SMB-mapped paths WAL can misbehave (ASSUMPTION), so keep the DB in `addon_data` on internal storage.
- Power loss: Otaku sets `PRAGMA synchronous = OFF` (`ui/database.py` L66) which risks corruption when a stick is unplugged. Use `synchronous=NORMAL` with WAL.
- Backups: user-visible state worth backing up is the add-on's `settings.xml` and your own DB. Kodi's own backup tools or add-ons (e.g. "Backup") only cover what is in `userdata` (ASSUMPTION).

## 8. Token and secret storage (be honest)

- Kodi Python has **no OS keystore API**. Add-on secrets are normally stored as add-on settings, which Kodi persists as plaintext XML in `addon_data/<id>/settings.xml`. Otaku stores `realdebrid.token`, `realdebrid.refresh`, `realdebrid.secret` that way, hidden at settings level 4 so they do not appear in the normal UI (`resources/settings.xml` L4157-4178; set in `debrid/real_debrid.py` L39-42; refreshed by `service.py` L12-24). The token is also placed in a `Bearer` header (`debrid/real_debrid.py` L28-29).
- Consequences: anyone with filesystem access to the Kodi profile (adb on a debug-enabled Fire TV, a backup zip, a shared "export settings" file) can read the token. Otaku's "Export settings" copies the raw `settings.xml` including tokens (`Main.py` L1972-1991), so users could leak tokens if they share it. A stolen RD token gives account access until revoked at real-debrid.com (revoke in the account/apps page; ASSUMPTION about the exact UI).
- Mitigations available to you: use the OAuth2 device flow (no password stored, revocable); store only the refresh/access token; keep the token out of logs (`control.log` has no redaction, see code_architecture.md section 7); never print URLs containing `?auth_token=`/`apikey=` queries; offer a "log out and delete token" action; mark your settings with `<option>hidden</option>` or an internal storage location, which hides but does not encrypt. Light obfuscation (base64/XOR) adds no real security.
- If you ever distribute the add-on with embedded API keys (like `context.otaku/info.db`), they are public. Prefer per-user keys entered in settings.

## 9. UI, remote navigation, memory and performance on low-end sticks

- Skins/controls: Otaku's custom dialogs are `xbmcgui.WindowXMLDialog` subclasses with XML in `resources/skins/Default/1080i/` (e.g. `windows/source_select.py`, `windows/resolver.py` L33 `class Resolver(BaseWindow)`, `windows/get_sources_window.py`); the `Default/1080i` layout scales to 720p/4K by Kodi. Good D-pad behavior needs explicit focus (`<onup>/<ondown>`, `<defaultcontrol>`) in XML and handling of `ACTION_NAV_BACK`/`ACTION_PREVIOUS_MENU` in `onAction` (Otaku `windows/resolver.py` L483-490). Prefer built-in `xbmcgui.Dialog().select/yesno/ok/notification` for 90% of UI on TV: they are remote-friendly without custom XML (Otaku's `control.select_dialog`, `context_menu` L499-535).
- Keymaps: remote keys map through Kodi's `keymap` to actions; add-ons cannot define global key bindings except via skin/keymap files in userdata (ASSUMPTION; Otaku does not do it).
- Memory/performance: Fire TV sticks have 1-2 GB RAM (older ones 1 GB; ASSUMPTION on exact models), and Kodi is the foreground process. Otaku's responses: lazy imports everywhere (`from resources.lib... import` inside functions; `MetaBrowser._get_browser()` lazy singleton), RAM cache in Window properties, bulk `addDirectoryItems` with a thread pool for listitems (`ui/control.py` L714-808), background prefetch threads at startup (`service.py` L334-337), pickled metadata blobs. Observed hazards for low-end devices: the plugin process is spawned per navigation, so Python start-up plus a big module graph (Main.py 2,436 lines) costs time (hence the `reuselanguageinvoker` toggle, `service.py` L214-235); `Window(10000)` properties holding large `repr()` strings; `PRAGMA mmap_size=256MB` (`ui/database.py` L68); thread bursts per scraper.
- Design suggestions: small modules, lazy imports, paginate lists (<= 50 items), cache posters via URLs not downloads, limit worker threads to 4-6, avoid unbounded caches (Otaku's `cache.db` has no TTL purge), keep service startup tiny.

## 10. Packaging and add-on metadata

- Zip layout: top-level folder named exactly as the add-on id (e.g. `plugin.video.myanime/`) with `addon.xml` inside; zip name `<id>-<version>.zip` (observed in Otaku's repo: `repo/zips/plugin.video.otaku/plugin.video.otaku-5.3.3.zip`, CONFIRMED via GitHub API listing). Assets (`icon.png`, `fanart.jpg`) listed in `<assets>`; the repo also stores icon/fanart/changelog beside the zips (the `plugin.video.otaku/` folder listing shows `poster.png, resources`).
- `addon.xml` essentials (compare Otaku `plugin.video.otaku/addon.xml`): `id`, `name`, `version`, `provider-name`; `<requires>` with `xbmc.python` and module imports; `<extension point="xbmc.python.pluginsource" library="default.py"><provides>video</provides>`; optional `<extension point="xbmc.service" library="service.py"/>`; `<extension point="xbmc.addon.metadata">` with `summary`, `description`, `platform`, `license`, `disclaimer`, `assets`. Version scheme: dotted integers; Kodi compares numerically per component (Otaku releases 5.2.99 then 5.3.1 at repo; ASSUMPTION that Kodi's AddonVersion is what you expect on 5.2.99 < 5.3.1; verified conceptually from `CAddonVersion` use in `Repository.cpp` L115-116).
- `reuselanguageinvoker` element: leave false unless designed for it (see code_architecture.md section 12).
- Localization: `resources/language/resource.language.en_gb/strings.po` with numeric string IDs (Otaku has tooling scripts `renumber_string_ids.py`, `symbolic_string.py`).
- Dependency version: declare minimal `xbmc.python` (3.0.1 works for Nexus and Omega; 3.1.0 is Piers-only per section 2). A `3.0.1` pin is installable on 21 and, ASSUMPTION, also on 22.

## 11. Private repository mechanics

Verified in Kodi source `xbmc/addons/Repository.cpp` at tag `21.3-Omega` (https://raw.githubusercontent.com/xbmc/xbmc/21.3-Omega/xbmc/addons/Repository.cpp, CONFIRMED) and in Otaku's real-world repo (`repo/repository.otaku/addon.xml`):

1. **Repository add-on**: an add-on with `<extension point="xbmc.addon.repository" name="...">` containing one or more `<dir>` blocks (Repository.cpp L112-132; the old no-`<dir>` form is rejected with an error, L123-130). Each `<dir>` has: `<info>` (URL of `addons.xml`, optionally `.gz`: Repository.cpp L232-243 decompresses if extension `.gz` or gzip MIME), `<checksum>` (URL of a text file with the hash of `addons.xml`; first token read, L160-181), `<datadir zip="true">` (base URL where `<id>/<id>-<version>.zip` lives), optional `<artdir>` (defaults to datadir, L309-312), optional `minversion`/`maxversion` attributes limiting by Kodi version (L330-331, matching L115-116).
2. **Integrity**: `<checksum>` is compared against `addons.xml` using MD5 by default, or another hash if `<checksum verify="sha256">` is set (`checksum@verify`, L301-305, check at L222-229); per-zip hashes via `<hashes>` (`sha256` etc.; `true` is a deprecated alias for md5, L314-327). Kodi logs a warning that MD5 is "broken and will only guard against unintentional data corruption" (L324-328). Recommendation: use SHA-256 for both. Otaku's own repo uses an MD5 sidecar (`addons.xml.md5`) with no `hashes`, i.e. weaker (CONFIRMED).
3. **Transport warnings**: plain `http` datadir logs "insecure"; `verifypeer=false` on https likewise (L141-148). Use HTTPS with a normal CA-signed certificate. Free options: GitHub Pages or `raw.githubusercontent.com` (Otaku uses raw URLs; the README also advertises a GitHub Pages source), Cloudflare Pages, or your own server. Needs the Kodi TLS stack to trust the host (public CAs fine).
4. **`addons.xml` structure**: `<addons>` root with the concatenated `<addon>` elements of each add-on (copy of each `addon.xml`), as seen in Otaku's `addons.xml` (CONFIRMED). The md5 file contains only the hex digest. Generators: Otaku ships `_repo_generator.py` (script v5; zips folders, writes md5; its source license is unstated). Reimplementing this in ~40 lines of your own Python is straightforward.
5. **Authentication**: Kodi's repository mechanism has **no native auth feature** in `Repository.cpp` (no auth-related options in the parsed `<dir>` fields: only checksum, info, datadir, artdir, hashes, min/max version; grep for "auth" returned nothing). Kodi's URL layer (`CURL`) does support credentials embedded in URLs and `|Header=` protocol options in general (the code even calls `datadir.GetRedacted()` and `HasProtocolOption`, L141-148), so `https://user:pass@host/...` in `<info>`/`<datadir>` *may* work (ASSUMPTION: untested; credentials would be stored in plain text in the repo add-on's addon.xml, visible to anyone who has it). Cleaner "privacy" approaches: unguessable URL path (security through obscurity), IP allowlist/VPN (e.g. Tailscale), or skip the repo and install from zip by hand. A public GitHub repo is publicly readable by anyone who knows the URL; a private GitHub repo cannot be read by Kodi without a token. Do not put secrets in the hosted files.
6. **Install flow**: Settings > Add-ons > Install from zip file (requires "Unknown sources" enabled: Settings > System > Add-ons) for the repository zip; then Install from repository; Kodi polls the repo and auto-updates add-ons (user can disable auto-update per add-on). Dependencies (`script.module.*`) are resolved from the official repository when installed from your repo.
7. **Versioning/rollback**: Kodi installs the highest version found in `addons.xml`. Always bump the version for any change (same version = no update). Keep old zips in `datadir`; Kodi's add-on info screen offers "Versions"/rollback from a repo only when the repo exposes multiple versions (Otaku's zip folder does keep old zips, but only the latest is listed in `addons.xml`, so for a repo that indexes one version per id the rollback route is "install from zip" of an older zip or deleting and reinstalling: ASSUMPTION on UI details). Downgrades via zip are allowed.
8. **Android "unknown sources"**: Kodi's own setting is *Settings > System > Add-ons > Unknown sources* (inside Kodi); Android's per-app "Install unknown apps" permission is only needed for installing the Kodi APK itself, not for add-ons (ASSUMPTION from standard behavior).
9. **Update cadence**: Kodi checks repos on a schedule and after start; users can force "Check for updates" (ASSUMPTION on UI wording; intervals not verified).
10. Otaku's repository follows the pattern: `repository.otaku` zip served from `index.html`, `repo/zips/` containing `addons.xml`, `addons.xml.md5`, one folder per add-on with versioned zips plus icon/fanart. Matches the structure Kodi expects (CONFIRMED via listings).

## 12. Quick compatibility checklist for your add-on

| Concern | Recommendation | Otaku does |
|---|---|---|
| Kodi target | Omega 21.x primary; Nexus 20 OK; test Piers when final | 20+ (README) |
| API pin | `xbmc.python 3.0.1` | same (`addon.xml` L4) |
| Python | stdlib only, no 3.12+ only syntax if you want Nexus | stdlib + bs4 |
| ListItem | `InfoTagVideo` setters only | yes (`ui/control.py` L543-601) |
| HTTP | urllib with `ssl.create_default_context(cafile=special://xbmc/system/certs/cacert.pem)` or `script.module.requests` | urllib, custom (`ui/client.py`) |
| Data | `addon_data` only; WAL + `synchronous=NORMAL`; migrations | `synchronous=OFF`, DB truncate on rebuild |
| Tokens | settings store (plaintext), OAuth device flow, revoke path, log redaction | settings level 4, no redaction |
| Hardware | Fire OS stick (not Vega) or Android TV | n/a |
| Repo | HTTPS, SHA-256 checksum and hashes, bump versions, keep old zips | HTTPS (raw GitHub), MD5 only |
| UI | built-in dialogs first, WindowXML sparingly | heavy custom WindowXML |

## 13. Unresolved / unverified items

1. Kodi 22 final release date (RC1 exists; no final seen).
2. Official Piers minimum Android version (7.0 per press only) and whether any Fire OS 5 stick remains in scope.
3. Whether credentials in repo URLs (`user:pass@`) work with Kodi's HTTP stack for repository operations.
4. Whether `xbmc.python 3.0.1` remains installable on Piers (host is 3.1.0).
5. Exact Fire TV model/OS/ABI table (Fire OS 6/7/8 versions, memory) was not verified from primary Amazon docs.
6. Kodi wiki (kodi.wiki) pages were blocked by Cloudflare (HTTP 403) during research; the repo and API facts above come from Kodi source code instead.
