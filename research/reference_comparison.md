# Reference Comparison — Otaku Kodi Add-on Candidates

Research date: 2026-10-10. Method: read-only `git clone --filter=blob:none` of each repository into a scratch directory, plus GitHub REST API metadata (`api.github.com/repos/...`). No add-on code was executed.

Legend: **CONFIRMED** = directly observed in repository contents, git history, or API response. **ASSUMPTION** = inference not directly verified.

---

## 1. Repository comparison

| Attribute | Goldenfreddy0703/Otaku | lukefanning/Otaku |
|---|---|---|
| Accessible | Yes (CONFIRMED) | Yes (CONFIRMED) |
| GitHub fork? | Yes — parent and source: `SwagOtaku/plugin.video.kaito` (API `parent`/`source`) | Yes — parent `Goldenfreddy0703/Otaku`, source `SwagOtaku/plugin.video.kaito` |
| Created | 2022-08-20 | 2024-12-01 |
| Last push | 2026-09-18 | 2024-12-29 |
| HEAD | `420666d` 2026-09-18 "Small fixes (#495)" | `69641fa` 2024-12-27 "Updated Version" |
| Commits on default branch | 955 | 873 |
| Unique commits vs. the other | 82 commits not in lukefanning | **0** commits not in Goldenfreddy (`git log main..lfmain` empty; merge-base = lukefanning HEAD) |
| Stars / forks | 180 / 42 | 0 / 0 |
| License | GPL-3.0 (`LICENSE`, `addon.xml` `<license>`) | GPL-3.0 |
| `plugin.video.otaku` version | **5.3.3** | **0.5.38** |
| `xbmc.python` import | **3.0.1** (Kodi 20+) | **2.24.0** (legacy Kodi 18-era API level) |
| `context.otaku` version | 1.0.35 | 0.0.15 |
| Bundled sibling add-ons | `context.otaku` only | `context.otaku`, `script.otaku.mappings` (24.12.01), `script.otaku.themepak` (0.0.13) |
| Extra deps (manifest) | beautifulsoup4, inputstreamhelper, pyqrcode | beautifulsoup4, dateutil, inputstreamhelper, six, kodi-six, requests, web-pdb, themepak, mappings |
| GitHub Releases | None published (API returned empty list); versions shipped through a separate Kodi repo `Goldenfreddy0703/repository.otaku` (README) | None |
| Remote branches | `main`, `Otaku-Testing`, `features`, `Download-Manager`, `Anilist-Discover`, `theasguard-patch-1` (`git ls-remote`) | `main` |

**Conclusion (CONFIRMED):** lukefanning/Otaku is a stale snapshot of Goldenfreddy0703/Otaku as of 2024-12-27. It contains no independent work.

## 2. Lineage

1. **SwagOtaku/plugin.video.kaito** — original author. First commit in the shared history: `08da2ed` 2020-10-10 "Initial commit" by SwagOtaku. Upstream last commit 2021-05-29 (API); repo not archived but inactive.
2. **Goldenfreddy0703/Otaku** — fork (2022), renamed to Otaku, maintained by Goldenfreddy0703 (602 commits) and gujal/Gujal (244), plus community contributors. README: "This is a fork of the original Kaito addon made by SwagOtaku. All credit goes to SwagOtaku."
3. **Two code lines existed in parallel** (CONFIRMED via history):
   - Legacy line `0.5.x` on `main` (e.g. 0.5.43 at `f550be6~1`, 2025-04-13), `xbmc.python 2.24.0`, using `kodi-six`/`six` for Py2/Py3.
   - Rewritten line `5.x` developed in a separate testing add-on/branch (`Otaku-Testing` branch at 5.1.13, 2024-11-10, `xbmc.python 3.0.0`; `sync_to_testing.py` copies changes to `plugin.video.otaku.testing`).
   - **`f550be6` 2025-09-11 "Updated Version v5.0.1 to v5.2.45"** replaced the legacy line on `main`: 630 files changed, +27,934 / −31,007. This commit deleted `script.otaku.mappings` and `script.otaku.themepak`.
4. **lukefanning/Otaku** — forked 2024-12 and stopped; therefore holds only the legacy 0.5.38 architecture.

## 3. Compatibility

| | Goldenfreddy HEAD (5.3.3) | lukefanning (0.5.38) |
|---|---|---|
| Kodi | README: "Kodi 20 Nexus or later (does not support Kodi 19 or earlier)"; badge "Kodi 20+/21" | Legacy API level; designed around Kodi 18/19 Py2/Py3 shims (ASSUMPTION from `xbmc.python 2.24.0` + `kodi-six`) |
| Python | Py3 only (`xbmc.python 3.0.1`) | Py2/Py3 via `six` |
| Kodi 22 | Not stated in README — **unverified** | n/a |
| Platform | `<platform>all</platform>` | `all` |

Detailed platform research: `platform_compatibility.md`.

## 4. Architectural differences (high level)

- Goldenfreddy 5.x is a ground-up rewrite on the Kodi 20+ API: Python 3 only, no `six`, mappings folded into the main add-on (no separate `script.otaku.mappings`), themes moved into the add-on/context add-on (no themepak). Real-Debrid code lives at `plugin.video.otaku/resources/lib/debrid/real_debrid.py` (354 lines) alongside AllDebrid, Premiumize, Debrid-Link, TorBox.
- Code size (5.3.3): ~34k lines of Python in `plugin.video.otaku`. Largest modules: `Main.py` (2,436), `AniListBrowser.py` (1,644), `pages/watchnixtoons2.py` (1,244), `ui/client.py` (1,143), `OtakuBrowser.py` (1,104).
- No automated test suite found (no `tests/` dir, no CI workflow in `.github`) — CONFIRMED by tree listing.
- Code-level detail: `code_architecture.md`, `playback_trace.md`, `metadata_analysis.md`, `real_debrid_analysis.md`.

## 5. Relevant release history (Goldenfreddy `main`)

| Date | Version | Note |
|---|---|---|
| 2020-10-10 | 0.0.x | Kaito origins (SwagOtaku) |
| 2025-04-13 | 0.5.43 | Last legacy version on `main` |
| 2025-09-11 | 5.2.45 | Rewrite merged (`f550be6`) |
| 2026-03 → 05 | 5.2.79 – 5.2.99 | Frequent point releases (scraper fixes typical) |
| 2026-08-16 | 5.3.0 – 5.3.1 | |
| 2026-08-18 | 5.3.2 | Includes settings.xml fix #489 |
| 2026-09-13 | 5.3.3 | `f57ef3a` |
| 2026-09-18 | (unreleased) | `420666d` "Small fixes (#495)" — after 5.3.3 |

Release cadence is high and many commits are scraper/website fixes, which indicates the direct-website scraping layer needs constant maintenance (supporting evidence in `source_discovery_options.md`).

Whether the Kodi repository (`repository.otaku`) currently serves exactly 5.3.3 is checked in `dependencies_and_licensing.md`.

## 6. Recommended reference

**Goldenfreddy0703/Otaku, tag-equivalent commit `f57ef3a` (v5.3.3), with `420666d` noted as post-release fixes.**

Why:
- It is the actively maintained upstream; lukefanning is a strict subset with no unique work.
- It targets the Kodi 20+/Python 3 API that a new Android TV / Fire TV add-on must use. The legacy 0.5.x line relies on deprecated APIs (`ListItem.setInfo` era, `six` shims) we would not adopt.
- Its Real-Debrid, metadata, and source-selection code reflects 2025–2026 service changes (e.g. post-`instantAvailability` behaviour — see `real_debrid_analysis.md`).
- Caveat: newest ≠ cleanest. The rewrite is large, has no tests, and mixes many concerns in big modules. We use it to learn behaviour and API usage, not as a structural template.

The legacy 0.5.x line (lukefanning) is useful only for one thing: the standalone `script.otaku.mappings` shows how cross-provider ID mappings were previously packaged.

## 7. Unresolved questions

1. Does `repository.otaku` currently publish 5.3.3 / context 1.0.35? **Resolved: yes** — published `addons.xml` lists plugin.video.otaku 5.3.3 and context.otaku 1.0.35 (version strings only; zip contents not diffed). See `dependencies_and_licensing.md`.
2. Is Kodi 22 supported/tested by Otaku 5.3.x? No statement found.
3. Why the separate `Otaku-Testing` branch is behind `main` (33 unique, 105 behind) — likely abandoned staging; not material.
4. No upstream test suite exists, so behavioural claims rest on code reading, not observed runs.
