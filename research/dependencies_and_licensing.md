# Otaku dependencies, licensing, and published releases

Source: Goldenfreddy0703/Otaku HEAD `420666d` (2026-09-18). Paths relative to repo root. Dated 2026-10-10.
This is a plain-language research summary, not legal advice.

## 1. Kodi add-on dependencies (from addon.xml)

`plugin.video.otaku/addon.xml` `<requires>` (L3-9; CONFIRMED by reading the file and by the published copy, see section 5):

| Import | Version | Purpose in Otaku | License (Kodi Omega mirror listing) |
|---|---|---|---|
| `xbmc.python` | 3.0.1 | Kodi Python API level; same value for Nexus 20 and Omega 21 (see platform_compatibility.md) | part of Kodi (GPL-2.0-or-later) |
| `script.module.beautifulsoup4` | any | HTML scraping in 14 modules (`from bs4 import BeautifulSoup`; e.g. `pages/nyaa.py` L4) | MIT (Omega mirror lists v4.12.2; depends on `script.module.soupsieve` 2.4.1, MIT) |
| `script.module.inputstreamhelper` | any | Checks/installs InputStream Adaptive (and Widevine) for HLS/DASH playback (`windows/resolver.py` L516-567) | MIT (v0.8.6; depends on `script.module.pysocks`) |
| `script.module.pyqrcode` | any | Draws a QR code PNG for Real-Debrid device-auth screen (`debrid/real_debrid.py` L52-90, writes `qr_code.png`) | BSD-3-Clause (v1.2.1+matrix.4) |
| `context.otaku` | 1.0.34 | Companion context-menu add-on, also hosts `info.db` and icon packs (`ui/control.py` L69-72) | GPL-3.0 (own addon.xml L63) |

`context.otaku/addon.xml`: imports only `xbmc.python 3.0.1`; extension `kodi.context.item` with 12 items; license GPL-3.0.

Version-pin observation: HEAD `plugin.video.otaku` requires `context.otaku` >= 1.0.34, while the context folder at HEAD is 1.0.35 (both published, see section 5).

Licenses of the Kodi modules come from the Kodi Omega mirror index, https://mirrors.kodi.tv/addons/omega/addons.xml (fetched 2026-10-10; CONFIRMED). Not declared by Otaku but used at runtime:
- `inputstream.adaptive` (GPL-2.0-or-later per same index, v21.5.25) is pulled in by inputstreamhelper when needed.
- `script.trakt` is referenced only through a window property (`ui/player.py` L224-228), not imported.
- No dependency on `script.module.requests` (Apache-2.0 on the Omega mirror), `urllib3`, or `certifi`; Otaku uses the stdlib `urllib` (`ui/client.py`).

Kodi itself does not need to be GPL-compatible with Python add-ons in any special way; add-ons run in Kodi's embedded Python and import its modules (`xbmc`, `xbmcgui`, ...).

## 2. Vendored third-party code in the repo

Checked headers of every bundled library-like file:

| Path | Origin / license | Evidence |
|---|---|---|
| `plugin.video.otaku/resources/lib/ui/pyaes/` (`__init__.py`, `aes.py`, `blockfeeder.py`, `util.py`) | pyaes by Richard Moore, MIT, Copyright (c) 2014 | MIT header at top of each file (L1-14 approx.) |
| `plugin.video.otaku/resources/lib/ui/jscrypto/pyaes.py` | pyaes by Marti Raudsepp, MIT, Copyright (c) 2010 (`bitbucket.org/intgr/pyaes`) | docstring L3-7 and copyright L29 |
| `.../ui/jscrypto/jscrypto.py`, `pkcs7.py` | CryptoJS-compatible EVP key derivation and PKCS#7 padding helper; no header, no license stated | file heads; `pkcs7.py` docstring cites RFC 2315 |
| `.../ui/jsunpack.py` | Dean Edwards p.a.c.k.e.r unpacker: Copyright (C) 2013 Bstrdsmkr, "additional fixes by mortael, jairoxyz", adapted from js-beautify (Einar Lielmanis, Stefano Sanfilippo); GPL-3.0-or-later header | file head L1-30 |
| `.../ui/megacloud_extractor.py` | "Ported from https://github.com/Goldenfreddy0703/mega-embed-2" (same maintainer's repo). Pulls decryption keys at runtime from `raw.githubusercontent.com/yogesh-hacker/MegacloudKeys/.../keys.json` (L14). No license header | file head L3, L14 |
| `.../ui/megaplay_extractor.py`, `embed_extractor.py`, `pages/*.py` | Site-specific scraping code; no headers. Many extractors in the embed_extractor design follow the long-standing Kodi "ResolveURL"-style registry pattern but no provenance statement exists. Do not assume a license beyond the project's GPL-3.0 | file heads |
| `.../debrid/debrid_cache.py` L207 | comment "DMM Secret Generation (ported from POV)" - POV is another Kodi add-on (license not stated here; POV-family add-ons are GPL-licensed in my understanding: ASSUMPTION) | `debrid/debrid_cache.py` L207 |
| `.../ui/control.py` L925 | `arc4` function: comment "Thanks to 123Venom" | `ui/control.py` L868-925 |
| `.../pages/__init__.py` L330-364 | comments say filtering and sort keys are "like Seren" / "Seren-style" (Seren is a GPL-3.0 add-on by nixgates; ASSUMPTION on exact license): behavior borrowed, copy extent unknown | `pages/__init__.py` L330, L334, L364 |
| `context.otaku/resources/images/icons/{coloured,exodus,seren,white,...}` | Icon sets named after other add-ons (Exodus, Seren). Artwork licensing not stated | `context.otaku/resources/images/icons/` |
| `context.otaku/info.db` | SQLite file shipping 14 API client IDs/keys for third-party services (values not reproduced here) | opened read-only; schema `info(api_name, api_key, client_id, client_secret, description)` |
| Binary files (`.dll/.so/.exe/.pyd`) | none tracked (`git ls-files` filter returned none) | - |

Files in the stale fork `lf` (lukefanning, at `69641fa` 2024-12-27, 0 unique commits) that no longer exist at HEAD: `script.otaku.mappings` (addon.xml says license **GPL-2.0**, v24.12.01) and `script.otaku.themepak` (GPL-2.0, v0.0.13). At HEAD the mappings are instead downloaded at runtime from the `Otaku-Mappings` GitHub repo (`service.py` L54-63). The license of that mappings database and of its upstream data sources was not examined.

## 3. Project license and lineage

- Declared license: **GPL-3.0** in `plugin.video.otaku/addon.xml` L23 `<license>GPL-3.0</license>`, `context.otaku/addon.xml` L63, full text in `/LICENSE` ("GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007"), per-file GPLv3-or-later header in `plugin.video.otaku/resources/lib/Main.py` L2-17 and `default.py` L2-17.
- Lineage: `README.md` L9-10: "This is a **fork of the original Kaito addon** made by **SwagOtaku**. All credit goes to SwagOtaku." Git history confirms: first commit `08da2ed` 2020-10-10 by "SwagOtaku", 955 commits total at HEAD. A remnant of the name remains at `pages/gogoanime.py` L17 (`arm2.vercel.app/api/kaito-b`). The upstream repository `SwagOtaku/plugin.video.kaito` license was not fetched here; Otaku's own history carries GPL-3.0 headers from the start of the fork, but I did not verify the Kaito repo (UNVERIFIED).
- Extra non-GPL wording: the add-on description says "None of its code and resources may be sold or redistributed for any commercial purposes" (`addon.xml` `<disclaimer>`, README disclaimer L). Under GPL-3.0 section 10/12, extra restrictions on top of the license are "further restrictions" and can be removed by recipients; still, treat it as the author's stated intent and keep it non-commercial.

## 4. What GPL-3.0 means for you (plain language)

1. **Personal use, no distribution: unconstrained.** You can read the code, copy pieces, modify them, and run them on your own devices without publishing anything. GPL obligations attach only when you *convey* (give copies to other people).
2. **If you copy or adapt Otaku code and give the add-on to anyone else, GPL-3.0 applies to your add-on.** "Anyone else" includes friends, family and a private repository other people can pull from. Then you must: (a) license your whole add-on under GPL-3.0 (or compatible); (b) keep the existing copyright notices and license headers; (c) mark your changes; (d) make the complete corresponding source available to the people who receive it (a public or recipients-only source repo or zip of readable `.py` files is enough, and a Kodi add-on distributes its Python source anyway); (e) not add further restrictions. You do not have to publish to the *world*, only offer source to the people you gave it to.
3. **A private repo for your own devices only is not "conveying to others".** Several of your own devices belong to you; the license treats that as personal use. The line is giving it to a third party. Since you said "private" and not "public", a household or family use case needs a judgement; if in doubt, comply with GPL.
4. **Writing independent code avoids GPL obligations.** Learning from Otaku's approach (ideas, API behavior, which endpoints exist, architecture) is not copying code. Facts (API URLs, field names, Real-Debrid REST endpoints) are not copyrightable the same way. Do not paste, translate line-by-line, or lightly paraphrase code. A clean approach: derive requirements from the public API docs (Real-Debrid, AniList, Kodi) rather than from Otaku source, and write your own implementation. You may then choose any license.
5. **Dependencies are separate.** Your add-on can `<import>` MIT/BSD modules (beautifulsoup4, inputstreamhelper, pyqrcode) without becoming GPL, and these can be used in GPL or non-GPL add-ons. Vendored MIT code (pyaes) can be reused if you keep its MIT notice.
6. **Mixed pieces to watch if you copy anything:** `jsunpack.py` (GPL-3.0-or-later, fine only under GPL), pyaes (MIT, keep notice), unlabelled extractors (no clear license: treat as GPL-3.0 by project license), icons of other projects (unknown), `info.db` API keys (not licensed to you; register your own keys).
7. **GPL does not cover what the code does, only the code.** It says nothing about whether scraping or streaming specific sites is lawful (see disclaimer, section 6).
8. Not legal advice. For anything beyond personal use, get a real opinion.

## 5. Published releases verification (https://github.com/Goldenfreddy0703/repository.otaku)

Fetched 2026-10-10 via `raw.githubusercontent.com` and the GitHub contents/commits API (CONFIRMED):

- Repo root: `.gitmodules, README.md, _repo_generator.py, index.html, repo/, repository.otaku-1.0.zip`. Latest commits (all titled "Rawr"): 2026-09-20, 2026-09-13, 2026-08-23.
- Index `repo/zips/addons.xml` (md5 file `addons.xml.md5` = `cdce9a1fb95fff27f3b8d337cece75fd`, which I recomputed over the downloaded `addons.xml`: it matches):
  - `context.otaku` **1.0.35** (zip folder holds 1.0.33, 1.0.34, 1.0.35)
  - `plugin.video.otaku` **5.3.3** (zip folder tail: 5.2.99, 5.3.1, 5.3.2, 5.3.3; requires `context.otaku` 1.0.34)
  - `repository.otaku` 1.0
- **Match with source HEAD: yes.** Source `plugin.video.otaku/addon.xml` is 5.3.3 and `context.otaku/addon.xml` is 1.0.35, identical to the published index (including the `context.otaku` >= 1.0.34 requirement). I compared version strings and import list; I did not byte-compare the zip contents against the source tree.
- Repository add-on (`repo/repository.otaku/addon.xml`, fetched): one `<dir>` with `<info compressed="false">`, `<checksum>`, `<datadir zip="true">`, all three at `https://raw.githubusercontent.com/Goldenfreddy0703/repository.otaku/master/repo/zips/...`; no `<hashes>` or `checksum@verify`. The README advertises `https://goldenfreddy0703.github.io/repository.otaku` as the file-manager source (the index.html there only links the repo zip).
- The generator `_repo_generator.py` (`SCRIPT_VERSION = 5`, `KODI_VERSIONS = [krypton, leia, matrix, nexus, repo]`) zips each add-on folder and refreshes addons.xml and the md5. This is a common community script, useful as a template for the private repo (provenance/license of the script unverified).
- README manual-install links point at older versions (`context.otaku-1.0.29`, `plugin.video.otaku-5.2.45`) - README is stale.

## 6. Disclaimer / legal posture

`plugin.video.otaku/addon.xml` `<disclaimer>` (L22): the add-on "DO NOT host, create, or distribute any of the content displayed in the addon, it simply scrapes ad financed public websites. It is the responsibility of the user to ensure that they are following all applicable laws and regulations in their country", and that it is not affiliated with Team Kodi. Note in terms of what the code actually does: several scrapers target pirate-adjacent streaming and torrent index sites (`pages/`), and the debrid layer resolves torrent magnets via Real-Debrid. Using debrid services with copyrighted torrents may violate law or the services' terms depending on jurisdiction; the disclaimer does not change that. Team Kodi's own stance: Kodi's forum rules ban support for add-ons that facilitate piracy, and official Kodi repository will not host such add-ons (general knowledge; no URL fetched here, ASSUMPTION). A personal add-on that only plays media you have rights to (your own debrid cloud files, legally obtained content) avoids most of the risk.

## 7. Third-party service terms to check before building

Not researched in depth here, but these matter for a personal add-on: Real-Debrid API terms and its device-code OAuth (Otaku uses an embedded public client ID from `info.db`; the open-source device-flow client ID is meant to be shared, user-specific secrets are issued per install, `debrid/real_debrid.py` L36-45), AniList/MAL/Kitsu/Simkl API terms and rate limits, fanart.tv / TMDB / TVDB key policies (each has its own free-tier terms and attribution rules), and `api.tenrai.org` (unofficial Jikan-compatible host).
