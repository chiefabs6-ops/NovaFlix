# NovaFlix Foundation (Plan 1 of 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the copied AniVerse 1.4.3 code in `C:\Users\danze\Desktop\Kodi Add-On\NovaFlix` into a separate add-on, NovaFlix 0.1.0. It gets its own git repo, its own Kodi identity, no Real-Debrid, a darker accent and the new icon. It must install next to AniVerse on the Fire TV stick without either app affecting the other.

**Architecture:** Fork (decided 2026-10-19). NovaFlix shares no code or runtime dependency with AniVerse. After this plan the app still shows anime content (AniList). The content swap is Plans 2–4. This plan only makes the fork safe to install and publish.

**Tech Stack:** Python 3 (Kodi 21 / xbmc.python 3.0.1), stdlib only in the add-on, pytest with the fakes in `tests/fakes`, Pillow (dev only, `tools/make_assets.py`).

**Spec:** The owner's decisions in chat, 2026-10-19:
- Name NovaFlix, ids `plugin.video.novaflix` / `script.novaflix` / `repository.novaflix`.
- Source repo `https://github.com/chiefabs6-ops/NovaFlix.git`. Update site `https://github.com/chiefabs6-ops/novaflix-repo.git`.
- TorBox only (Real-Debrid removed).
- Darker accent colours. Icon from `c:\Users\danze\Downloads\Neon Crystal N App Icon.png`.
- English-only releases now, Polish later (Plan 3).
- TMDB metadata (Plan 2).
- Keep the AniVerse design.

## Roadmap (later plans, written after this one lands)

| Plan | Delivers |
|---|---|
| 2 – TMDB catalog | `metadata/tmdb.py` (Read Access Token as a hidden setting), title/season/episode models with `tmdb_id` + `imdb_id`, a cached catalog facade (trending, popular movies/shows, now playing, airing today, upcoming, top rated, genres, search, details, seasons, recommendations, collections), a fresh `user.db` schema. Removes AniList, ani.zip, MAL-Dubs, AnimeSchedule, AniSkip, franchise and MyAnimeList. |
| 3 – Sources & playback | Torrentio by IMDb id (`tt…:S:E`), Nyaa removed, English-only filter (a language list so Polish can be added), matcher fixes (`S01E01E02`), dub logic removed, hand-off and history keyed by tmdb id + season + episode, Up next across seasons. |
| 4 – GUI content | Same window design. New sidebar and Home rows, season picker on the show page, movie page, "More like this" and collection rows instead of Related, MAL hub, buttons and menu items removed. |

## Global Constraints

- All work happens in `C:\Users\danze\Desktop\Kodi Add-On\NovaFlix`. Never edit, build or publish anything in `...\AniVerse`, or the `aniverse-repo` / `Anime-Add-On` GitHub repos.
- Add-on version `0.1.0` for `plugin.video.novaflix` and `script.novaflix`. `repository.novaflix` is `1.0.0`.
- Update-site URL: `https://chiefabs6-ops.github.io/novaflix-repo/`. Pages git: `https://github.com/chiefabs6-ops/novaflix-repo.git`.
- Window properties start with `novaflix.` and the profile path is `special://profile/addon_data/plugin.video.novaflix/`.
- The add-on keeps no runtime dependencies beyond `xbmc.python`, `script.module.pyqrcode` and `script.novaflix`.
- No keys or tokens in any file or commit. `tools/build.py release` runs the secret scan.
- Publishing (`git push`, `build.py publish`) only after the owner says yes in chat.
- Run tests with: `.venv\Scripts\python -m pytest -q` from the NovaFlix folder. The baseline before Task 1 is all green.

## Review Focus

1. **Both apps on one stick:** playback started in NovaFlix must never be picked up by AniVerse's service, and the reverse. Pinned by `test_identity.py::test_window_properties_are_novaflix` (Task 2) and the manual check in Task 6.
2. **A leftover AniVerse identifier** in a packaged file (settings `RunPlugin` URL, skin file name, log prefix) would send actions to the wrong add-on. Pinned by `test_identity.py::test_no_aniverse_left_in_packages` (Task 2).
3. **Publishing to the wrong update site** would overwrite AniVerse on the stick. Pinned by `test_build.py::test_repo_urls_are_novaflix` (Task 2) and by deleting `dist/` in Task 1.
4. **A TorBox key that is missing or rejected** must still lead to TorBox settings, not a Real-Debrid login. Pinned by `test_router.py::test_auth_error_opens_torbox_settings` (Task 3).
5. **A baked-in checkerboard around the icon** (the source PNG is RGB with a drawn checkerboard, not transparent). Pinned by `test_assets.py::test_logo_is_only_what_is_inside_the_frame` (Task 4).

---

### Task 1: Own git repo, clean copied artefacts

**Files:**
- Delete: `dist/` (holds a clone of **aniverse-repo** in `dist/pages` plus old AniVerse zips), `.pytest_cache/`, `.superpowers/`, the AniVerse plans and specs `docs/superpowers/plans/2026-10-11-*`, `2026-10-12-*` and `docs/superpowers/specs/2026-10-11-*`, `2026-10-12-*` (keep this plan, `2026-10-19-novaflix-foundation.md`)
- Keep: `planning/`, `research/` (code comments cite their DEC numbers)

NovaFlix currently has no `.git`. `git rev-parse --show-toplevel` inside it returns `C:/Users/danze` (the home-folder repo), so it needs its own.

- [ ] **Step 1: Delete the artefacts listed above.** Verify with `ls dist` → "No such file or directory".
- [ ] **Step 2: Create the repo:** `git init -b main` then `git remote add origin https://github.com/chiefabs6-ops/NovaFlix.git`.
- [ ] **Step 3: Verify:** `git rev-parse --show-toplevel` prints `C:/Users/danze/Desktop/Kodi Add-On/NovaFlix`, and `git remote -v` shows only NovaFlix.git.
- [ ] **Step 4: Run tests.** Run `.venv\Scripts\python -m pytest -q`. Expected: all pass, the same as AniVerse 1.4.3.
- [ ] **Step 5: Commit** the untouched fork as the base, so later diffs show every change:

```bash
git add -A
git commit -m "chore: start NovaFlix from AniVerse 1.4.3"
```

### Task 2: NovaFlix identity everywhere

**Files:**
- Rename (`git mv`): `plugin.video.aniverse/` → `plugin.video.novaflix/`, `script.aniverse/` → `script.novaflix/`, `repository.aniverse/` → `repository.novaflix/`
- Rename: `resources/skins/Default/1080i/aniverse-*.xml` → `novaflix-*.xml` (8 files), `resources/skins/Default/media/aniverse-white.png` → `novaflix-white.png`, `aniverse-icon.png` → `novaflix-icon.png` (in all three add-ons; content replaced in Task 4), `tools/source_art/aniverse-logo-source.png` → `novaflix-logo-source.png`
- Modify: every file that contains `aniverse`/`AniVerse`/`ANIVERSE` under the three add-on folders, `tools/`, `tests/`, `pages/`, `INSTALL.md`, `pyproject.toml` (94 files; `planning/` and `research/` are left alone)
- Create: `tests/test_identity.py`

**Interfaces:**
- Produces: `router.PLUGIN_ID == "plugin.video.novaflix"`, `monitor.HANDOFF_PROPERTY == "novaflix.playing"`, `OPEN_SHOW_PROPERTY == "novaflix.open_show"`, `GUI_PROPERTY == "novaflix.gui"`, `sync.KICK_PROPERTY == "novaflix.mal_kick"`, `errors.NovaFlixError` (renamed from `AniVerseError`, same hierarchy), the setting id `novaflix_look` (was `aniverse_look`).

- [ ] **Step 1: Write the failing tests** in `tests/test_identity.py`:

```python
PACKAGES = ["plugin.video.novaflix", "script.novaflix", "repository.novaflix"]

def test_no_aniverse_left_in_packages():
    # every text file (not .png) in PACKAGES + tools/build.py + tools/dev_kodi.py
    hits = [...]  # (path, line_no) where re.search(r"aniverse", line, re.I)
    assert hits == []

def test_window_properties_are_novaflix():
    from resources.lib.playback import monitor
    from resources.lib.myanimelist import sync
    for name in (monitor.HANDOFF_PROPERTY, monitor.OPEN_SHOW_PROPERTY, monitor.GUI_PROPERTY, sync.KICK_PROPERTY):
        assert name.startswith("novaflix.")

def test_addon_ids_and_versions():
    # parse each addon.xml
    assert ids == {"plugin.video.novaflix": "0.1.0", "script.novaflix": "0.1.0", "repository.novaflix": "1.0.0"}
    assert plugin <requires> imports script.novaflix version 0.1.0
    assert launcher.py runs "RunPlugin(plugin://plugin.video.novaflix/launch)"
    assert settings.xml <section id="plugin.video.novaflix">
```

Add to `tests/test_build.py`:

```python
def test_repo_urls_are_novaflix():
    assert build.REPO_URL == "https://chiefabs6-ops.github.io/novaflix-repo/"
    assert build.PAGES_GIT == "https://github.com/chiefabs6-ops/novaflix-repo.git"
    assert build.ADDONS == ("plugin.video.novaflix", "script.novaflix", "repository.novaflix")
```

- [ ] **Step 2: Run them and confirm they fail.** Run `.venv\Scripts\python -m pytest tests/test_identity.py tests/test_build.py -q`. Expected: FAIL (import path or ids).
- [ ] **Step 3: Do the folder and file renames** with `git mv`.
- [ ] **Step 4: Replace the text.** Do a case-preserving replace in the files listed above: `AniVerse` → `NovaFlix`, `aniverse` → `novaflix`, `ANIVERSE` → `NOVAFLIX`. Then edit the values the replace does not fix:
  - `addon.xml` files: versions per Global Constraints. Plugin `<summary>`: "Personal TV shows and movies add-on with TorBox playback". Plugin `<description>`: "Browse TV shows and movies, choose a source yourself and play it through your own TorBox account. For personal use." `<news>`: "0.1.0: First NovaFlix build."
  - `repository.novaflix/addon.xml`: name "NovaFlix Repository", with the three URLs under `https://chiefabs6-ops.github.io/novaflix-repo/`.
  - `tools/build.py`: `PAGES_GIT` as above. The `ALLOWED` secret entries stay as they are.
  - `tests/conftest.py`: plugin path `plugin.video.novaflix`.
- [ ] **Step 5: Run the full suite.** Run `.venv\Scripts\python -m pytest -q`. Expected: all pass, including the 4 new tests. Fix every test that still names the old ids or files.
- [ ] **Step 6: Commit.**

```bash
git add -A
git commit -m "feat: NovaFlix add-on identity (ids, profile, properties, update site)"
```

### Task 3: Remove Real-Debrid (TorBox only)

**Files:**
- Delete: `plugin.video.novaflix/resources/lib/debrid/realdebrid.py`, `debrid/auth.py`, `views/account.py`, `tests/test_realdebrid.py`
- Modify: `debrid/service.py`, `router.py` (`ROUTES`, `report_error`), `service_main.py` (`housekeeping`, delete `check_real_debrid` and its constants), `views/sources.py` (`_setup_service`), `resources/settings.xml` (delete the `playback_service` setting and the `realdebrid` category), `strings.po` (delete the strings only RD used: 30114, 30115, 30116, 30127, 30135, 30137, 30204, 30205), the tests that cover these modules (`test_service.py`, `test_router.py`, `test_settings_actions.py`, `test_sources.py`, `test_playback.py`, `test_redact.py`)

**Interfaces:**
- Produces: `service.client(directory=None) -> TorBox | None` (TorBox when `torbox_api_key` is set). `service.label() -> "TorBox"`. `service.TORBOX` stays. `service.active()` and `service.REAL_DEBRID` are removed; update every caller.
- Unchanged: the `rd/cloud`, `rd/torrent`, `rd/play`, `rd/add_magnet` routes ("My TorBox" screens). Only `rd/account` goes.

- [ ] **Step 1: Write the failing tests:**

```python
# tests/test_service.py
def test_client_is_torbox_when_key_set(): ...      # setting torbox_api_key="TORBOXKEY-1" -> isinstance(client, TorBox)
def test_client_is_none_without_key(): ...         # -> None
def test_no_real_debrid_modules():
    for name in ("realdebrid", "auth"):
        with pytest.raises(ImportError): importlib.import_module(f"resources.lib.debrid.{name}")
    assert "rd/account" not in router.ROUTES

# tests/test_router.py
def test_auth_error_opens_torbox_settings():
    # report_error(errors.AuthError("x"), "play") with confirm answered yes -> open_settings called once
    # and the dialog heading is "TorBox"

# tests/test_settings_actions.py
def test_settings_have_no_real_debrid():
    text = open(settings.xml).read()
    assert "playback_service" not in text and "realdebrid" not in text and "rd/account" not in text
```

- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Remove the code and settings listed above.** `housekeeping()` keeps the MAL and dub steps; those go in Plan 2.
- [ ] **Step 4: Run the full suite.** Expected: all pass. Delete RD-only assertions in the listed tests rather than rewriting them.
- [ ] **Step 5: Commit.**

```bash
git add -A
git commit -m "feat: TorBox is the only playback service; Real-Debrid removed"
```

### Task 4: New icon, fanart and darker accent

**Files:**
- Create: `tools/source_art/novaflix-logo-source.png` (copy of `c:\Users\danze\Downloads\Neon Crystal N App Icon.png`, 1254×1254 RGB with a drawn checkerboard)
- Modify: `tools/make_assets.py` (palette constants, `LOGO_SOURCE`, `LOGO_INSIDE`, `LOGO_RADIUS`, `logo()` targets, new `fanart()`), the 8 `novaflix-*.xml` skins, `net/phone_keyboard.py` (page CSS), `pages/mal-login.html`, `tests/test_assets.py`
- Regenerate: everything in `resources/skins/Default/media/`, `novaflix-icon.png` in all three add-ons, `fanart.png` in the plugin and the repository

**Values:**
- Logo crop (measured on the source: neon frame spans x 58–1195, y 73–1179): `LOGO_INSIDE = (50, 65, 1203, 1187)`, `LOGO_RADIUS = 150`. The existing `logo()` masks and pads to a square.
- `fanart()`: 1920×1080, `BG` base with a soft `VIOLET` glow top left and a `CYAN` glow bottom right (use the existing `glow()`/`gradient()` helpers). No logo or text.
- Palette (ARGB in the XML, `#rrggbb` in CSS, tuples in `make_assets.py`). Text colours (`FFFFFFFF`, `FFF5F7FF`, `FFA8B5D1`, `FFD6DEF5`, `FF7F8CAD`) and status colours (`FF34D399`, `FFF5B04F`, `FFFFC857`, `FFFF4D6D`) stay.

| Role | Old | New |
|---|---|---|
| BG | `FF050B18` | `FF02050D` |
| PANEL | `FF0C1930` | `FF070F1F` |
| panel raised | `FF132443` | `FF0C1730` |
| panel line | `FF1A2747` | `FF111B33` |
| CYAN accent | `FF00CFFF` | `FF00A6D6` |
| VIOLET accent | `FFA855F7` | `FF8B3FE0` |
| PURPLE | `FF702CFF` | `FF5B1FD6` |
| BLUE | `FF087BFF` | `FF0663CC` |
| focus blue | `FF5A8BFF` | `FF4A72D9` |
| phone input border `#5a6bff` | | `#4a58d9` |

- [ ] **Step 1: Write the failing tests** in `tests/test_assets.py`. Update the existing icon tests to `novaflix-icon.png` and the three add-ons, then add:

```python
OLD_ACCENTS = ["FF050B18", "FF0C1930", "FF132443", "FF1A2747", "FF00CFFF", "FFA855F7", "FF702CFF", "FF087BFF", "FF5A8BFF"]

def test_skins_use_the_darker_palette():
    for xml in glob(SKINS + "/*.xml"):
        text = open(xml).read().upper()
        assert not [c for c in OLD_ACCENTS if c in text], xml

def test_phone_page_uses_the_darker_palette():
    css = phone_keyboard.PAGE.lower()
    assert "#050b18" not in css and "#00cfff" not in css and "#a855f7" not in css

def test_fanart_is_1920x1080():
    for addon in ("plugin.video.novaflix", "repository.novaflix"):
        assert png_size(os.path.join(ROOT, addon, "fanart.png")) == (1920, 1080)
```

`test_logo_is_only_what_is_inside_the_frame` (corners transparent, centre opaque) stays and now checks the new logo.
- [ ] **Step 2: Run them and confirm they fail.** Run `.venv\Scripts\python -m pytest tests/test_assets.py -q`.
- [ ] **Step 3: Apply the palette** to `make_assets.py`, the skins, the phone page and `pages/mal-login.html`. Set the logo constants. Add `fanart()` and call it from `main()`.
- [ ] **Step 4: Regenerate.** Run `.venv\Scripts\python tools\make_assets.py`. Expected: no error, and the files above have changed (`git status`).
- [ ] **Step 5: Run the full suite.** Expected: all pass.
- [ ] **Step 6: Visual check.** Open `plugin.video.novaflix\novaflix-icon.png` and `resources\skins\Default\media\av-logo.png`. Expected: neon frame with the N and "NOVAFLIX", no grey or white checkerboard in the corners. If any shows, raise `LOGO_RADIUS` by 10 and repeat Step 4.
- [ ] **Step 7: Commit.**

```bash
git add -A
git commit -m "feat: NovaFlix icon, fanart and darker accent colours"
```

### Task 5: Install guide, release build, first publish

**Files:**
- Modify: `INSTALL.md` (rewrite for NovaFlix: source `https://chiefabs6-ops.github.io/novaflix-repo/`, name the source `novaflix`, install `repository.novaflix-1.0.0.zip`, then NovaFlix from "NovaFlix Repository"; same update, rollback and publish sections with NovaFlix names)

- [ ] **Step 1: Update `INSTALL.md`** as above.
- [ ] **Step 2: Build the release.** Run `.venv\Scripts\python tools\build.py release`. Expected output: `plugin.video.novaflix 0.1.0: added`, `script.novaflix 0.1.0: added`, `repository.novaflix 1.0.0: added`, then the `dist\repo` path. The secret scan must pass.
- [ ] **Step 3: Check the output.** `dist\repo\addons.xml` lists only novaflix ids, and `dist\repo\repository.novaflix\repository.novaflix-1.0.0.zip` exists.
- [ ] **Step 4: Commit.**

```bash
git add -A
git commit -m "docs: NovaFlix install guide; release 0.1.0"
```

- [ ] **Step 5: Ask the owner** in chat for approval to push. Then run `git push -u origin main` and `.venv\Scripts\python tools\build.py publish`. Expected: `published plugin.video.novaflix 0.1.0, script.novaflix 0.1.0, repository.novaflix 1.0.0`.
- [ ] **Step 6: Owner turns on GitHub Pages** for novaflix-repo (Settings → Pages → Deploy from branch → `main` / root). Expected: `https://chiefabs6-ops.github.io/novaflix-repo/addons.xml` opens in a browser within about 2 minutes.

### Task 6: Side-by-side check (owner, manual)

NovaFlix 0.1.0 still shows anime. This check only proves the two apps live together safely. PC Kodi first. Fire TV stick only if the owner wants it now; otherwise at the end of Plan 4.

- [ ] **Step 1:** Install the repository and NovaFlix as described in `INSTALL.md`. Expected: Video add-ons shows **two** tiles, AniVerse (old icon) and NovaFlix (new icon).
- [ ] **Step 2:** Open NovaFlix → Settings. Expected: no Real-Debrid category and no playback-service choice. Enter the TorBox key.
- [ ] **Step 3:** Open NovaFlix and check the look. Expected: same layout as AniVerse, darker colours, new logo in the sidebar.
- [ ] **Step 4:** Play any episode in NovaFlix, stop it after 2 minutes, then open AniVerse → Continue Watching. Expected: that episode is **not** listed in AniVerse.
- [ ] **Step 5:** Play an episode in AniVerse, stop it after 2 minutes, then open NovaFlix → Continue Watching. Expected: it is **not** listed in NovaFlix, and AniVerse resumes it normally.
- [ ] **Step 6:** Check `kodi.log`. Expected: NovaFlix lines start with `[plugin.video.novaflix]`, and no errors from either add-on.
