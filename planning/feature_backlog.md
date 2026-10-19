# Feature Backlog

Nothing below is approved for v1 unless its status says **Approved** and cites a decision ID. Complexity: S / M / L.

## Required for v1 (approved — DEC-043)

| ID | Feature | Description | Acceptance criteria | Depends on | Risks | Cx |
|---|---|---|---|---|---|---|
| F-SEARCH | Search | On-screen keyboard search; matches English, romaji, native, synonyms; recent searches | Finds a show by any of its titles; TV + movies only in results (DEC-014) | DEC-012, DEC-014 | AniList rate limit | S-M |
| F-DETAILS | Show page & episode list | Info, art, episode list (titles/thumbs from episode-detail source), related/sequels, specials/OVAs grouped | Episodes numbered 1..N per entry; specials only here; missing data shown as absent | DEC-011, DEC-013, DEC-014 | Episode-detail source choice | M |
| F-PLAY | Playback pipeline | Matcher picks episode file; RD add/select-file/unrestrict; Kodi playback; player monitor for progress/completion; cleanup per DEC-019 | Plays chosen source on Fire TV; bad link → message + back to list; progress recorded; added torrent removed after start | DEC-002, DEC-004, DEC-019 | Undocumented RD behaviours (risks D1-D2) | L |
| F-RD-AUTH | Real-Debrid connection | Authorize, show status, disconnect | Authorize on TV without keyboard; token refreshed automatically; disconnect removes local tokens | DEC-002 | Plaintext token storage (C3) | M |
| F-SRC-SELECT | Manual source list | Kodi select dialog, 2 lines/source, grouped & sorted; optional filters; "same as last episode" pin | No auto-selection; missing fields absent, not guessed; header shows hidden count; pin matches release group+resolution | DEC-004, DEC-021–024 | Sparse metadata from some sources | M |
| F-HISTORY | Local watch history & resume | Watched at ≥90 %, resume position, last watched; manual mark watched/unwatched | Survives cache clear and add-on updates; resume offered on replay; manual marks persist | DEC-005, DEC-028, DEC-032 | Kodi resume vs add-on state divergence | M |
| F-MAL-READ | MyAnimeList lists (read-only) | Menus for owner's public MAL list by status, opening the matching show | Lists load with client ID + username only; no MAL login; entries open correct show via MAL ID; clear message if list private/user not found | DEC-015, DEC-011 | MAL API availability; title-ID mismatches when AniList lacks `idMal` | S-M |
| F-SRC-RDCLOUD | Sources from own RD account + add magnet | Find the episode file in torrents already in the owner's RD account; allow adding a magnet | Correct file listed for a matching episode; magnet add shows progress and clear outcome | DEC-003 | Filename matching errors | M |
| F-SRC-AGG | Aggregator search | Query a Torrentio-compatible service by anime ID for an episode; configurable URL | Results for a known-airing episode; service down → clear message, Nyaa still tried; RD token never sent | DEC-003 | Third-party availability; Kitsu ID mapping | M |
| F-SRC-NYAA | Nyaa fallback search | Nyaa RSS text search, results marked "best guess" | Results labelled; bracket tags stripped before episode-number parsing | DEC-003 | Undocumented RSS; weak matching | M |
| F-RD-NOTREADY | Download-then-play for not-ready sources | Ask to download; modal progress (percent, speed, seeders, status); auto-play when done; cancel asks keep/remove; 10-min stall prompt | Bad links never offered download; account errors distinct; progress updates without exceeding RD rate limit; plays automatically on `downloaded` | DEC-020 | Long waits; stuck torrents | M |
| F-RD-STATUS | Account status + expiry warning | Settings shows username/type/expiry; warn < 7 days | Warning at most once per day | DEC-018 | — | S |
| F-AUDIO-PREF | Preferred audio language | Setting (default English) applied on playback start | English track selected when present; otherwise Kodi default, no error | DEC-027 | Missing/wrong track language tags | S |
| F-DUB-LABEL | Dub labelling of sources | Mark English-audio sources from name/aggregator evidence | Never labels dub without evidence; unknown shown as unknown | DEC-025 | Heuristic accuracy | S-M |
| F-DUB-FILTER | Dub-only source view | Only dub-labelled sources; "No English dub found" + "Show all sources anyway" | Unknown-audio sources hidden in dub view, visible in show-all | DEC-025 | Heuristic labels miss some dubs | S |
| F-DUB-BADGE | DUB badge in catalog | Best-effort from MAL-Dubs dataset (AGPL data, downloaded at runtime, weekly) | Badge on known dubbed titles; partial marked; failure keeps last copy | DEC-025 | Community data accuracy; external file availability | S |
| F-SUBS-SIGNS | Signs & Songs auto-subtitle | With English audio, enable forced/Signs & Songs English track if present | Enabled when identifiable; off otherwise | DEC-026 | Track metadata quality | S |
| F-CONTINUE | Continue Watching | Home menu of started shows with next episode / resume point | Most recent first; updates right after playback | DEC-029 | — | S |
| F-UPNEXT | Up next prompt | Near end: "Next: Episode N — choose source"; pre-search during credits | OK opens source list for next episode; no auto-play; playback unaffected | DEC-030 | Kodi player-monitor timing on low-end device | M |
| F-FAVS | Local favourites | Add/remove from remote; home menu list | Persist across restarts/updates | DEC-031 | — | S |
| F-HOME | Home menu & catalog sections | 12 entries per DEC-033 | Each entry loads with remote only; empty states explained | DEC-033, DEC-011 | AniList rate limits | M |
| F-CACHE | Cache with Clear button | TTLs per DEC-034; separate from user data | Clear cache leaves history/favourites intact | DEC-034 | — | S |
| F-ERRORS | Error presentation | Notifications vs actionable dialogs | Each RD/MAL error class maps to a specific message | DEC-035 | — | S |
| F-CONTEXT | In-add-on context menu | Items per DEC-036 | All items reachable via remote menu button | DEC-036 | — | S |
| F-LOG | Redacted logging + debug toggle | Central logger with redaction | Automated test: no token/URL/key appears in logs or exception text | DEC-037 | — | S |
| F-REPO | Private repository (GitHub Pages) | Public Pages repo with zips, addons.xml, SHA-256; source in private repo | Installs on Fire TV Stick 4K 2nd gen + Windows; update notification works; rollback to previous of 3 versions works | DEC-006, DEC-038, DEC-039 | Packages publicly reachable (no secrets inside) | M |
| F-SKIP | Skip intro/ending button | AniSkip times by MAL ID + episode; shown only when duration matches | Button appears for matching episodes; hidden on mismatch; AniSkip failure never affects playback | DEC-041 | Dub timing mismatch; third-party availability | M |

## Desired for v1
_(none — every workshop answer was placed in Required; owner may move items here to trim scope)_

## Future possibilities
- **Backup/restore** of history, favourites, settings (DEC-042).
- **Background downloads** — "Hide" progress, keep browsing, notify when ready (DEC-020 Q15c).
- **MyAnimeList two-way sync** — first feature after v1 (DEC-015): update episode count/status after completing an episode. Needs MAL OAuth login (no TV device flow).
- AniList tracker sync — excluded from v1 by DEC-005; not requested.

## Explicitly excluded
| Feature | Reason |
|---|---|
| Other debrid/playback services in v1 | DEC-002 |
| Remote watch-history sync in v1 | DEC-005 |
| Direct-stream website scrapers | DEC-003 |
| AnimeTosho provider | DEC-003 (service shutting down) |
| Self-hosted Jackett/Prowlarr in v1 | DEC-016 |
| Automatic source selection / autoplay | DEC-004 |
| External subtitle search (OpenSubtitles etc.) in v1 | DEC-026 |

## Awaiting research or decision
| Feature | Blocking decision |
|---|---|
| Episode-detail metadata source choice | DEC-011 open question |
| **Dub release-date hint** (owner request 2026-10-11): on a show's episode list, when not all episodes are dubbed yet, show a hint on undubbed episodes such as "English dub expected on <date>", like Otaku's testing build. Needs research on Otaku's data source (likely AnimeSchedule.net, `AnimeSchedule.py`) and its key/terms. Scheduled for after M6. | Research + owner decision |
