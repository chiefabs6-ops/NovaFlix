# Installing and updating AniVerse

AniVerse is installed from its own Kodi repository, served by GitHub Pages at
`https://chiefabs6-ops.github.io/aniverse-repo/`. Install the repository once; after that Kodi
tells you when an AniVerse update is available (DEC-039).

The repository holds only the built add-on zips. It contains no logins or keys: your TorBox key,
Real-Debrid login and MyAnimeList details stay in Kodi's settings on each device.

## First install (Fire TV Stick and Windows, Kodi 21)

1. **Allow unknown sources** (once per device): Settings → System → Add-ons → turn on
   **Unknown sources**, and confirm the warning.
2. **Add the address as a source:** Settings → File manager → **Add source** → `<None>` →
   type `https://chiefabs6-ops.github.io/aniverse-repo/` → OK → name it `aniverse` → OK.
3. **Install the repository:** Settings → Add-ons → **Install from zip file** → `aniverse` →
   `repository.aniverse` → `repository.aniverse-1.0.0.zip`. Wait for "AniVerse Repository installed".
4. **Install AniVerse:** Add-ons → **Install from repository** → AniVerse Repository →
   Video add-ons → **AniVerse** → Install. Kodi also installs the QR-code helper it needs.

If AniVerse is already installed from a zip, step 4 is still worth doing: Kodi then knows AniVerse
comes from this repository and offers its updates. Settings, history and favourites are kept.

## Automatic install or notify (DEC-039, DEC-059)

The Fire TV stick is set to install updates automatically (owner's choice, DEC-059). To be asked first instead:

- Kodi-wide: Settings → System → Add-ons → **Updates** → "Notify, but don't install updates".
- Or only for AniVerse: Add-ons → My add-ons → Video add-ons → AniVerse → turn **Auto-update** off.

When an update is published, Kodi shows a notice; install it from AniVerse's add-on page → **Update**.

## Going back to an earlier version

The repository keeps the last 3 versions of AniVerse.

1. Add-ons → My add-ons → Video add-ons → AniVerse → **Update** (or **Versions**).
2. Pick the older version from the list.
3. Turn Auto-update off for AniVerse, or Kodi may install the newest version again.

Your watch history survives a rollback. If an older version finds history saved by a newer one it
cannot read, it says "Please update" and leaves the data untouched (DEC-039).

## Publishing an update (owner/developer)

1. Raise `version` in `plugin.video.aniverse/addon.xml`.
2. `.venv\Scripts\python tools\build.py release` — secret scan, tests, version check, zips,
   checksums, `addons.xml`; output in `dist/repo`.
3. Copy `dist/repo` into the Pages repository (`chiefabs6-ops/aniverse-repo`) and push.
   Kodi picks the update up at its next repository check (on start, then about daily).
