# How Otaku gets streams from free anime sites (research only)

Source: Goldenfreddy0703/Otaku v5.3.3 clone, HEAD 420666d (commit date 2026-09-17), 955 commits.
Paths below are relative to `plugin.video.otaku/`. Nothing was executed. Only homepage HEAD/GET probes were made (section 6).
Tags: CONFIRMED = read in code or measured. ASSUMPTION = inferred.

## 1. Providers, defaults, base URLs

Orchestration list of active "embed" (free-site) providers: `resources/lib/pages/__init__.py:28-37`.
Active (not commented out): animepahe, animix, hianime, anikoto, watchnixtoons2.
Commented out in orchestration: aniwave (`__init__.py:34`), animekai (`__init__.py:36`). `gogoanime.py` is not imported at all. CONFIRMED.
The `provider.aniwave` toggle still exists in settings (`resources/settings.xml:938`, default true) but has no effect because the module is not wired in. CONFIRMED. `provider.animekai` and `provider.gogo` are commented out in settings (`settings.xml:902`, `:943`).

Defaults (all `true` in `resources/settings.xml`): anikoto :907, animepahe :912, animix :925, hianime :956, watchnixtoons2 :961. The "alt" mirrors (animepahealt :917, gogoalt :948) default false. CONFIRMED.
Torrent providers (nyaa :758, animetosho :771, torrentio :804 default true; nekobt :799 false) only run when a debrid is enabled (`__init__.py:104-108`). The free-site providers run with no debrid. CONFIRMED.

| Provider | Base URL | file:line |
|---|---|---|
| animepahe | https://animepahe.pw/ (alt: Google Translate proxy `animepahe-pw.translate.goog`) | pages/animepahe.py:16 |
| animixplay | https://animixplay.la/ (plus video host play2.echovideo.ru) | pages/animixplay.py:14, :83 |
| hianime | https://hianime.ms/ (embeds from megaplay.buzz; proxies animanga.fun) | pages/hianime.py:15-23 |
| anikoto | https://anikototv.to/ (referer only; embeds from megaplay.buzz) | pages/anikoto.py:10-11 |
| watchnixtoons2 (WCO) | https://www.wcostream.tv/ (embed.wcostream.com) | pages/watchnixtoons2.py:15, :499 |
| aniwave (disabled) | https://aniwave.se/ | pages/aniwave.py:14 |
| animekai (disabled) | https://animekai.to/ plus enc-dec.app helper API | pages/animekai.py:13, :20-22 |
| gogoanime (not wired) | https://gogoanime3.cc/ | pages/gogoanime.py:25 |

## 2. Per-provider mechanics

Common: shows are keyed by MAL id (`getSources` receives `mal_id`, `__init__.py:84`). Sub/dub preference comes from the `general.source` setting (1 = sub only, 2 = dub only). CONFIRMED (e.g. anikoto.py:27-31, animixplay.py:17-21).

- **anikoto** (anikoto.py:11-100). No search. Builds `megaplay.buzz/stream/mal/{mal_id}/{ep}/{sub|dub}` directly from MAL id and episode number. Sub/dub is a path segment. Calls the MegaPlay extractor. Returns a direct HLS m3u8 plus caption tracks and intro/outro skip times. Source dict `'type': 'direct'`.
- **hianime** (hianime.py:27-420). Searches the site by title and MAL keywords, scores candidates, reads the details page MAL id to confirm, then parses the watch page for a stream token or ids. Builds a megaplay.buzz `s-2`/`ani`/`mal` URL per lang (`:288-295`). Server names ryu/volt/ayame. Sub and dub are separate megaplay requests. Returns direct HLS, wrapped in a third-party "proxy" URL (`:297-310`, hosts animanga.fun) for some servers. Subtitles optionally routed through the same proxy.
- **animepahe** (animepahe.py:70-202). Uses MAL-Sync (malsync endpoint) to map MAL id to an animepahe slug, falls back to the site's `api?m=search&q=title`. Episode via `api?m=release` pages of 30 (`:155-160`). Fetches the play page, reads `#resolutionMenu` buttons, one per quality/audio. `data-audio == 'eng'` = DUB, else SUB (`:41, :44-46`). Returns `type: 'embed'` (not resolved here). Embed hosts handled: those in the user's `embed.config` list, effectively kwik (`embed_extractor.py:179`).
- **animixplay** (animixplay.py:14-120). Title search via `api/search` POST. Dub is a separate catalog entry whose name ends "dub" (`:42-45, :63`). Reads an episode list from the page, then a playlist host `play2.echovideo.ru` (`:83-95`), reads `getSources`, returns `type: 'direct'` (`:100-114`) with `|Referer=..&Origin=..&User-Agent=iPad` appended.
- **watchnixtoons2 / WCO** (watchnixtoons2.py). Title search (romaji, English, cleaned; `:36-52`), episode-range mapping (`:148-170`). SUB and DUB are separate episode pages (lang 2/3, `:253-256`). Skips movies (`:140`). Extracts from `embed.wcostream.com` players: API-style tokenised URLs, m3u8, or jwplayer sources (`:598-670`). Returns direct. Cartoon/western-animation-leaning catalogue; weakest anime coverage (ASSUMPTION based on site name).
- **aniwave / animekai / gogoanime** (disabled). Not reachable in this version. Mechanics noted in section 3.

## 3. Extraction layer and where it crosses the line

Plain, benign steps (no protection defeated): fetching HTML, parsing buttons/JSON with BeautifulSoup/regex, building a Referer/Origin/User-Agent header string, reading an unencrypted JSON `getSources` response.

- **MegaPlay extractor** (`ui/megaplay_extractor.py`, 68 lines). Fetch embed page with a Firefox UA and Referer, regex the player `data-id`, call `/stream/getSources?id=...` with `X-Requested-With`, read plain JSON (`sources`, `tracks`, `intro`, `outro`). In this version the payload is not decrypted. One fallback guesses `index-f2.m3u8` from a subtitle URL path (`:46-52`). CONFIRMED. Relies on header spoofing (Referer/UA) so the host thinks the request came from the parent site. This is the main path for hianime and anikoto. Assessment: header spoofing of a hotlink check is soft; I would flag it as a grey area but it is not decryption or DRM.
- **kwik** (`embed_extractor.py:179-187`). Fetch embed page, unpack packed JavaScript (`ui/jsunpack.py`), regex `const source = '...'` for the m3u8. Needs Referer. The packer is obfuscation, not DRM. Unpacking is de-obfuscation of the host's player page.
- **filemoon, streamwish/filelions, lulu, mixdrop, fusevideo, mp4upload, yourupload, okru, voe, streamtape, dood**: all registered in `embed_extractor.py:~572-690`. Each regex-scrapes the embed page. Several unpack packed JS (`__get_packed_data`, :86-100). Voe base64 + reverse-decodes an inline blob (:303-315). Streamtape rebuilds a URL from split JS string pieces (:274-292). Dood requests a "pass_md5" style URL and appends a random suffix plus timestamp token (:255-272). These defeat host-side URL obfuscation designed to stop simple scraping. Plainly: this is reverse-engineering obfuscated player pages.
- **goload/gogo family** (`embed_extractor.py:330-380`). AES-CBC encrypt/decrypt with static keys hard-coded in the add-on (`:352`). Legacy; only relevant to the gogoanime path that is not wired in. Would cross the line (key embedding to decrypt a protected payload). Do not reproduce.
- **MegaCloud extractor** (`ui/megacloud_extractor.py`, 261 lines; used only by animekai path, `embed_extractor.py:692-710`). Fetches a decryption key set from a third-party GitHub repo at runtime (`:11-25`), derives a key with custom hashing/XOR/shift (`:40-65`), decrypts the encrypted `sources` payload. CONFIRMED. This is key scraping plus decryption of intentionally obfuscated/encrypted sources. Crosses the line.
- **animekai** (disabled; `pages/animekai.py:20-22, :164-200`). Sends tokens and encrypted blobs to an unaffiliated service `enc-dec.app` to encrypt requests and decrypt responses. Outsources the decryption. Crosses the line.
- **aniwave** (disabled; `pages/aniwave.py:274-300`). Generates a "vrf" request signature with RC4 and a fixed key plus char-shift, and decrypts the returned URL. Crosses the line (reimplements the site's request-signing/encryption).
- **WCO ad-verify** (`watchnixtoons2.py:363-410`). Calls an ad script URL with a random flag, POSTs `{nonce, status:'clear', id}` to `/ad-verify`, then loads the player with that nonce and sleeps 5 s (`:409`). The site's ad gate is told that the ad check "cleared" without an ad being shown. This is spoofing an access/monetisation check. Crosses the line.
- **Cloudflare / anti-bot** (`ui/client.py`). TLS-version retry for 403 `cf-alert-error` (`:424-450`). For real Cloudflare/DDoS-Guard challenges (`:455-493`), if the user turns on `fs_enable`, it calls an external FlareSolverr instance (`cfcookie`, `:1011-1052`) to get `cf_clearance` and reuses that cookie/UA. Without FlareSolverr it just logs "has a Cloudflare challenge" and gives up. Also optional Google Translate mirrors (`translate.goog`) for animepahe/nyaa/animetosho as alternate URLs (animepahe.py:16). FlareSolverr use is bypassing an access control. Crosses the line (opt-in in Otaku).
- **Random User-Agent / "iPad" UA**: many sources use `User-Agent=iPad` (anikoto.py:90, animixplay.py:104) to receive HLS directly. UA spoofing only.

## 4. Playback

- Source dicts carry `hash` = stream URL plus optional `|Header=val&Header2=val` suffix (e.g. anikoto.py:90, animepahe.py:20, animixplay.py:104). `type` is `direct` or `embed` (embeds resolved via `embed_extractor.load_video_from_url`, `windows/resolver.py:156-158`).
- `windows/resolver.py:prefetch_play_link` (:361-399) splits headers off, HEADs the URL, sets Content-Type to `application/vnd.apple.mpegurl` or `video/MP2T` if absent.
- `_handle_playback` (:198-300) sets MimeType and runs hooks. `_HLS_HOOK` (:540-575) when `inputstreamadaptive.enabled`: sets `inputstream` to inputstream.adaptive, `manifest_type=hls`, strips the `|headers` off the URL, and passes the headers via `inputstream.adaptive.stream_headers` (:557-558), and `common_headers`/`manifest_headers` on newer Kodi (:562-565). Line :560 also sets `license_key` to `'|' + headers + '||R{SSM}'` as a trick to carry headers on older ISA. It is not DRM. DASH hook at :515-535 is similar.
- Without ISA, the plain `|Referer=` suffix on the URL is used by Kodi's own player.
- Subtitles: tracks (`kind == captions`) are collected into `subs` with per-sub headers (anikoto.py:46-57, hianime.py:327-352). The resolver downloads each via `embed_extractor.get_sub` to `special://temp/TemporarySubs*` (`embed_extractor.py:522-566`), detects language from label (`detect_sub_lang`, :481), then `item.setSubtitles([...])` (resolver.py:224). CONFIRMED. These are soft subs from the stream host. Hard-sub (burned in) is unavoidable on many sources.

## 5. Maintenance burden (git log counts)

| File | 12 mo | 3 mo | Notes |
|---|---|---|---|
| pages/__init__.py | 8 | 1 | orchestration |
| pages/animepahe.py | 8 | 3 | "update animepahe domain" 2026-04-05; "Small fixes (#495)" 2026-09-18; v5.3.3 2026-09-13 |
| pages/hianime.py | 5 | 1 | "fix hianime" 2026-03-24 |
| pages/watchnixtoons2.py | 3 | 1 | |
| pages/animixplay.py | 3 | 1 | |
| pages/anikoto.py | 2 | 1 | new-ish provider (only 2 commits) |
| pages/animekai.py | 2 | 0 | disabled 2026-04 |
| pages/aniwave.py | 2 | 0 | disabled |
| pages/gogoanime.py | 2 | 0 | disabled |
| ui/embed_extractor.py | 6 | 1 | |
| ui/megaplay_extractor.py | 2 | 1 | v5.3.3 2026-09-13 |
| ui/megacloud_extractor.py | 0 | 0 | unchanged in window (ASSUMPTION: used by disabled path only) |
| ui/jsunpack.py | 0 | 0 | |
| ui/client.py (CF handling) | 11 | 1 | |
| ui/player.py | 8 | 0 | |
| windows/resolver.py | 10 | 1 | |

Commit messages are mostly batch "Updated Version vX" bundles, so counts understate granularity. Only a few messages name a specific break: "fix hianime", "update animepahe domain". Providers disabled during the window (aniwave, animekai, gogo) suggest breakage ended in removal. Mix of domain swaps and layout changes is the repeating pattern (ASSUMPTION from commit titles only; diffs not reviewed).

## 6. Reachability (single homepage request, 2026-10-11, from this machine)

| URL | Result |
|---|---|
| https://animepahe.pw/ | 403 |
| https://animixplay.la/ | 200 |
| https://hianime.ms/ | 200 |
| https://www.wcostream.tv/ | 403 |
| https://anikototv.to/ | 200 |
| https://megaplay.buzz/ | 200 |
| https://aniwave.se/ | 000 (no response/failed connection) |
| https://animekai.to/ | 000 (no response/failed connection) |
| https://gogoanime3.cc/ | 302 (redirect, not followed) |
| https://enc-dec.app/ | 200 |

A 403 on a homepage from plain curl is consistent with Cloudflare bot challenge (ASSUMPTION; body not inspected). It means a plain HTTP client, as Kodi's would be without FlareSolverr, likely fails there. Reachability here says nothing about whether API/stream endpoints work.

## 7. Legal / ToS (factual)

These sites host or link to anime that is generally not licensed for free distribution in the user's region. Embed hosts (kwik, megaplay, dood, etc.) are third-party file hosts. Scraping them usually breaks their ToS (many forbid automated access) and distribution/streaming of unlicensed copyrighted content may be infringing depending on jurisdiction. Several steps in section 3 circumvent technical measures (encryption, request signing, ad gates, bot challenges). In EU/Ireland law (owner's email domain is .ie; ASSUMPTION about location) circumventing effective technical protection measures is separately restricted. Otaku itself does the work inside the user's add-on; it ships no media. Not legal advice.

## 8. Assessment for AniVerse

- Steps that do NOT cross the project rule: calling a documented/public API, parsing HTML or plain JSON, setting a standard Referer/UA for hotlink checks (grey area for the latter), passing headers to inputstream.adaptive, subtitle download. Roughly: anikoto and the megaplay path as written (plain JSON, no decryption) and animixplay's `getSources` (plain JSON) are the closest to "clean". Even so, they scrape unlicensed hosts and rely on Referer spoofing, so the legal/ToS concerns in section 7 still apply.
- Steps that cross it: megacloud key fetching and decryption, enc-dec.app, aniwave vrf, goload static-key AES, WCO ad-verify spoofing, FlareSolverr/Cloudflare bypass, obfuscation reversal on dood/streamtape/voe (borderline: de-obfuscation, but it exists to defeat anti-scraping).
- Reliability expectation: low to medium. animepahe and WCO already 403 to plain HTTP (section 6), embed hosts rotate domains, and Otaku touches provider files every few weeks. Expect to chase breakage monthly if built.
- Maintenance cost: high and permanent (domain swaps, header/token changes, host rotation). Otaku has had a full-time maintainer for this; a personal add-on would carry that alone.
- Alternative: other debrid services (TorBox, AllDebrid, Premiumize) are another option the owner could evaluate for the torrent path; they have their own content policies, and Real-Debrid's 451 "infringing_file" suggests hash-level blocking that other services may handle differently (ASSUMPTION; not tested). Licensed streaming (e.g. Crunchyroll via their own add-ons or apps) is outside Otaku's design.
