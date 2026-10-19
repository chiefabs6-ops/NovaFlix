# Risks and Unknowns

Consolidated from all research files (2026-10-10). Each item names its evidence file. Severity: H/M/L for impact on our add-on.

## A. Risks inherited from the reference (things NOT to copy)

| # | Risk | Evidence | Sev | Implication for our design |
|---|---|---|---|---|
| A1 | Otaku embeds a **third-party Real-Debrid credential** in a Torrentio URL for cache checks | `debrid_cache.py:112` (value not reproduced) | H | Never reuse. Use only the user's own authorization. |
| A2 | Reverse-engineered DMM anti-bot "solution" for cache checks | `debrid_cache.py:176-254` | H | Out of scope: bypasses a site's access control and is fragile. |
| A3 | Demo AIOStreams key embedded | `debrid_cache.py:127-174` | M | Do not reuse. |
| A4 | RD access token only refreshed at Kodi startup; no 401 retry | `service.py:12-24`, `real_debrid.py` | H | Refresh at call time + on 401 / error_code 8. |
| A5 | No log redaction; failing URLs logged (incl. embedded credentials); resolved URL placed in exception text | `ui/client.py:497,502`, `windows/resolver.py:386` | H | Central redacting logger; never log query strings or headers. |
| A6 | Dead resolved link does not fall through/retry (HEAD check outside loop) | `playback_trace.md` | M | Design explicit retry that keeps manual choice (DEC-004). |
| A7 | Local watch progress = one integer in a pickled blob; truncated on "Rebuild database" | `code_architecture.md` | H | Own schema with explicit migrations; never wipe history on cache rebuild. |
| A8 | `PRAGMA synchronous = OFF`, silent `OperationalError` swallowing | `ui/database.py:66` | M | Use WAL + normal sync; surface errors. |
| A9 | ~95 routes in one 2,436-line `Main.py`; Kodi imports at module import; no tests | `code_architecture.md` | M | Small modules, Kodi calls behind thin adapters so logic is unit-testable. |
| A10 | Third-party API keys shipped in `context.otaku/info.db` | `metadata_analysis.md` | M | If we need keyed APIs (TMDB, Fanart.tv), user supplies own keys, or we avoid keyed APIs in v1. |
| A11 | Direct-website scrapers churn constantly (most commits are scraper fixes) | `reference_comparison.md` §5, `source_discovery_options.md` | H | Excluded by recommendation; awaiting decision. |

## B. External service risks

| # | Risk | Evidence | Sev |
|---|---|---|---|
| B1 | RD `torrents/instantAvailability` not in official docs; removal (Nov 2024) attested by press, not by an RD notice. No cheap "is it cached?" check. | `real_debrid_analysis.md` | H |
| B2 | RD reportedly rejecting some cached torrents by filename since ~May 2026 — single vendor source, **unverified** | `source_discovery_options.md` | M |
| B3 | **AnimeTosho stopped ingesting 2026-05-09; feed/API server expiring Oct 2026; site closes May 2027** (per its own pages) | `source_discovery_options.md` | H (for any Tosho-based plan) |
| B4 | Torrentio public instance: no published ToS/rate-limit; 2026 health unverified | `source_discovery_options.md` | M |
| B5 | Nyaa RSS works (live-checked) but is not formally documented | `source_discovery_options.md` | M |
| B6 | AniList rate limit: 90/min baseline, reported degraded to 30/min — unverified current value | `metadata_analysis.md` | M |
| B7 | Jikan limits (3/s, 60/min) unverified; Otaku now defaults to Tenrai mirror with unknown terms | `metadata_analysis.md`, `control.py:78` | M |
| B8 | Otaku-Mappings DB (31,182 rows) license not checked; external download dependency | `metadata_analysis.md`, `service.py:54-59` | M |
| B9 | RD ToS: personal use, no account/link sharing, no VPS/cloud use; says nothing specific about API clients | `real_debrid_analysis.md` | L (personal use) |
| B10 | Shared open-source RD client_id may be throttled harder than registered apps (doc statement); effect unmeasured | `real_debrid_analysis.md` | M |

## C. Platform risks

| # | Risk | Evidence | Sev |
|---|---|---|---|
| C1 | New Fire TV devices on **Vega OS cannot run Kodi** (Stick 4K Select, HD 2026, 3rd-gen 4K); 4K Max / 4K Plus still Fire OS (press source) | `platform_compatibility.md` | H — device choice matters |
| C2 | Kodi 22 Piers only at rc1 (2026-09-27); Python 3.14, `xbmc.python` 3.1.0 | `platform_compatibility.md` | M |
| C3 | No secure keystore from Kodi Python — tokens stored as plaintext in `addon_data/.../settings.xml` | `platform_compatibility.md` | M (must be stated honestly) |
| C4 | Kodi repositories have no native auth; `user:pass@` URLs unverified | `platform_compatibility.md` | M for "private" repo |
| C5 | Low-RAM Fire TV sticks: slow Python startup, `reuselanguageinvoker` trade-offs | `platform_compatibility.md` | M |

## D. Open unknowns needing a real account / device (cannot be resolved by reading)

1. ~~RD `expires_in` actual value; whether refresh token rotates.~~ **Resolved 2026-10-11 (live, owner's account):** `expires_in` = 86400 s (24 h); refresh returns a new access token and the **same** refresh token (no rotation). Pending device-credential polls return HTTP 403 with null error fields.
2. Whether single-file `selectFiles` on a cached torrent yields `downloaded` instantly; `links[]` ordering with partial selection. *(Moot for now: TorBox is the playback service, DEC-055.)*
3. Real throttling of shared client_id.
4. ~~Behaviour on user's actual devices / Kodi version.~~ **Resolved:** M1–M8 verified on Windows Kodi 21.3 and Fire TV Stick 4K (AFTKRT) Kodi 21.2.
5. Kodi 22 final date; whether `xbmc.python 3.0.1` add-ons install on Piers.
6. Whether Kodi accepts credentials in repository URLs.

## E. Documentation-quality notes

- Some line numbers in `feature_inventory.md` are approximate (agent-reported).
- `debrid_cache.py` citations in `real_debrid_analysis.md` / `playback_trace.md` were corrected after review; a false "never auto-refreshes" claim was corrected (see A4).
- Fact claims marked UNVERIFIED in sub-docs remain unverified.

## F. Observed during implementation

- 2026-10-11 (M3, Fire TV): one `GetDirectory - Error getting plugin://plugin.video.aniverse/trending` with no AniVerse warning; plugin finished in 97 ms; owner saw no error. Treated as Kodi discarding a request; watch for recurrence.
- Fire TV logcat main buffer is only 256 KB by default and fills with system noise; set `adb logcat -G 16M` after each stick reboot before testing.

## G. Real-Debrid content filter (observed 2026-10-11, owner's account)

- API `POST /torrents/addMagnet` returns HTTP 451 `{"error":"infringing_file","error_code":35}` for every anime release tested (0/11 accepted across SubsPlease, EMBER, Salieri, Tenrai-Sensei, ToonsHub, Feibanyama...). Legal public-domain torrents (Big Buck Bunny, Sintel) were accepted — except once, minutes earlier, when even Big Buck Bunny got 451.
- The website behaves the same way per release: owner added [Salieri] Frieren (refused earlier via API) successfully on real-debrid.com; [EMBER] Frieren was refused on the website ("Infringing torrent"). Conclusion: a content filter applied per release, with some inconsistency over time; not specific to AniVerse's API/app route.
- A torrent already in the account (added on the website) is accepted again by the API and plays — the "add on website, play in AniVerse" route works.
- Matches third-party reports of RD filtering since ~2026-05 (ElfHosted, TROYPOINT, WirelessHack); no official RD statement found.
- Impact: DEC-002/DEC-003 discovery-to-RD playback works only for releases the filter lets through. Pre-checking sources (Q53) proposed so blocked releases are hidden.

## H. M9 hardening findings (2026-10-11)

- **Speed, Fire TV (add-on timings from the stick log, normal use):** cached menus 80–230 ms inside the add-on; first open of a show page needing AniList + ani.zip ~460–800 ms; Upcoming/Recently Aired first open 520–670 ms, then 130–170 ms; playing a source (discovery + TorBox check + resolve) ~5.7–6 s. Menus open in about 0.5 s on screen when cached.
- **Speed, Windows:** each menu spends ~350 ms starting Python and importing the add-on, against 15–47 ms of add-on work. With `reuselanguageinvoker` on, menus after the first take 3–12 ms (first one unchanged at ~380 ms). The stick's share is not measured (see next point), but its CPU is much slower, so the saving there is expected to be larger.
- **Automated UI timing on the stick is not usable:** driving the stick's Kodi over JSON-RPC (one connection per poll) made it time out and Kodi restarted twice; owner stopped these runs. Stick speed is taken from the add-on's own log lines during normal use.
- **Fire TV memory pressure:** Android's low-memory killer closes background apps routinely (YouTube, Live TV, Amazon services, and once Kodi while it was in the background, 12:24). Kodi itself used ~150–156 MB (PSS). `reuselanguageinvoker` keeps a Python interpreter alive, which adds memory; watch for Kodi being killed while in the foreground if it is enabled.
- **Errors reviewed (DEC-035):** messages now name the active service (TorBox/Real-Debrid); a rejected TorBox API key offers to open settings; failed torrents are explained in plain words. All failure paths in architecture §11 have tests, including TorBox failed torrent and missing stream link.
- **Kodi directory cache vs updates:** a menu cached with `cacheToDisc` before an update keeps old links until Kodi restarts (seen: Continue Watching opened the old placeholder). The home menu is no longer disc-cached; other lists only link to routes that exist in every version.
- **Dub labels:** other-language dubs and English-subtitle-only releases were labelled English (fixed, M8 follow-up). Labels remain heuristics from release names.

## I. M12 "AniVerse look" on the stick (2026-10-11, 1.1.0)

- Memory: Kodi 152 MB PSS with the new windows open, same as before the redesign (150–156 MB): no measurable increase (budget was +40 MB).
- Speed: owner reports every screen responsive with the remote; per-menu timings were not in the stick log (AniVerse debug logging off), so no numbers recorded.
- No AniVerse errors in the stick log. Deferred minor findings from the final review are listed in the M12 ledger summary (sidebar current-view marker, grid page-2 failure exits, paging only on down/right, hero buttons inert if Trending fails, confirm focuses Yes first, others).
