# AniVerse v1 — release checklist (M11)

**Result (2026-10-11): passed. Released as 1.0.1, tag `v1.0.1`.** 1.0.1 fixes a show-page crash on the 32-bit stick found during this check (dub hint dates past 2038 for long-running shows).

Gate devices (DEC-040): Fire TV Stick 4K 2nd gen (AFTKRT, Kodi 21.2) and Windows Kodi 21.3.
"Verified" = owner checked it on that device in the milestone named; automated tests cover
every feature as well (full suite green at release).

## v1 features (DEC-043)

| ID | Feature | Status | Where verified |
|---|---|---|---|
| F-HOME | Home menu & sections | ✅ | M3/M8, PC + stick |
| F-SEARCH | Search | ✅ | M3, PC + stick |
| F-DETAILS | Show page & episodes | ✅ | M3, PC + stick |
| F-DUB-BADGE | DUB badge | ✅ | M3, PC + stick |
| F-MAL-READ | MyAnimeList lists | ✅ | M4, PC + stick |
| F-FAVS | Favourites | ✅ | M4, PC + stick; kept through 0.9.1 → 0.9.2 → 0.9.1 (M10) |
| F-RD-AUTH | Real-Debrid connection | ✅ | M5, PC + stick (Real-Debrid now optional, DEC-055) |
| F-RD-STATUS | Account status + warning | ✅ | M5 (Real-Debrid only) |
| F-SRC-SELECT | Manual source list | ✅ | M6, PC + stick |
| F-SRC-AGG / F-SRC-NYAA | Torrentio / Nyaa search | ✅ | M6; language and season fixes in M8 |
| F-SRC-RDCLOUD | My TorBox / My Real-Debrid + add magnet | ✅ | M5/M6 |
| F-DUB-LABEL / F-DUB-FILTER | Dub labels, dub-only view | ✅ | M6; other-language dubs fixed M8 |
| F-PLAY | Playback | ✅ | M7 via TorBox (DEC-054/055), PC + stick |
| F-RD-NOTREADY | Download-then-play | ✅ | M7 via TorBox |
| F-HISTORY | History & resume | ✅ | M8, PC + stick |
| F-CONTINUE | Continue Watching | ✅ | M8, PC + stick |
| F-AUDIO-PREF / F-SUBS-SIGNS | Audio language, Signs & Songs | ✅ | M8, PC + stick |
| F-SKIP | Skip intro/ending | ✅ | M8, PC + stick |
| F-UPNEXT | Up next | ✅ | M8, PC + stick |
| F-CACHE | Clear cache | ✅ | M2/M8 |
| F-ERRORS | Error messages | ✅ | M9 review (service-aware wording) |
| F-LOG | Redacted logging | ✅ | automated tests (SEC-03/04/05) |
| F-CONTEXT | Context menu (DEC-036) | ✅ | M11 on stick (1.0.1): Related & sequels, Choose a different source; other items M4/M8 |
| F-REPO | Repository | ✅ stick; Windows repo install not done (PC uses developer installs) | M10: install, update, rollback on stick. Update *notification* replaced by automatic install (DEC-059) |

## Final manual checks (owner)

1. ✅ Stick updated to **1.0.1** from the repository (Kodi checks about daily; "Check for updates" on the repository forces it).
2. ✅ One Piece opens (1.0.1 fix). Hold OK on a show in any list → **Related & sequels** opens its related entries (or says there are none).
3. ✅ Hold OK on an episode → **Choose a different source** searches again and shows the source list.
4. ✅ History, favourites and Continue Watching are still there after the update.
5. Optional, Windows: install the repository on the PC Kodi as in `INSTALL.md` (the PC currently has AniVerse from a developer install).

## Known limitations of v1

- **Playback service:** TorBox is the default (DEC-055). Real-Debrid stays selectable but refuses most anime releases through its content filter (risk list G). TorBox's free plan has monthly download limits; a source TorBox has not cached counts against them.
- **Logins in plain text:** the TorBox key, Real-Debrid login and MyAnimeList client ID are stored in Kodi's settings on each device in plain text (Kodi has no keystore). Anyone with file access to the device can read them.
- **Dub detection is a guess from release names.** A source can be labelled wrongly; the "no English audio track" notice catches this at playback.
- **Dub dates** come from AnimeSchedule.net and are estimates.
- **Third-party services without guarantees:** AniList, ani.zip, Torrentio, Nyaa, AniSkip, MAL-Dubs and AnimeSchedule can each fail; each failure is shown or skipped on its own and never blocks the others.
- **History is per device;** there is no backup or sync in v1.
- **The stick runs short of memory;** Android sometimes closes Kodi while it is in the background (risk list H). The add-on stays loaded between menus (DEC-058), which uses some extra memory.
- **The repository is public** (GitHub Pages cannot require a login). It holds only the built zips, which are checked for keys before every release; the source code stays private.
- **Updates install automatically** on the stick (DEC-059); a rollback only stays if Auto-update is turned off for AniVerse.
