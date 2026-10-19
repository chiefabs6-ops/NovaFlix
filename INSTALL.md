# Installing and updating NovaFlix

NovaFlix is installed from its own Kodi repository, served by GitHub Pages at
`https://chiefabs6-ops.github.io/novaflix-repo/`. Install the repository once; after that Kodi
tells you when a NovaFlix update is available (DEC-039).

The repository holds only the built add-on zips. It contains no logins or keys: your TorBox key
and TMDB key stay in Kodi's settings on each device.

## First install (Fire TV Stick and Windows, Kodi 21)

1. **Allow unknown sources** (once per device): Settings → System → Add-ons → turn on
   **Unknown sources**, and confirm the warning.
2. **Add the address as a source:** Settings → File manager → **Add source** → `<None>` →
   type `https://chiefabs6-ops.github.io/novaflix-repo/` → OK → name it `novaflix` → OK.
3. **Install the repository:** Settings → Add-ons → **Install from zip file** → `novaflix` →
   `repository.novaflix` → `repository.novaflix-1.0.0.zip`. Wait for "NovaFlix Repository installed".
4. **Install NovaFlix:** Add-ons → **Install from repository** → NovaFlix Repository →
   Video add-ons → **NovaFlix** → Install. Kodi also installs the QR-code helper it needs.

NovaFlix and AniVerse are separate add-ons: each has its own settings, history and update repository.

If NovaFlix is already installed from a zip, step 4 is still worth doing: Kodi then knows NovaFlix
comes from this repository and offers its updates. Settings, history and favourites are kept.

## Automatic install or notify (DEC-039, DEC-059)

The Fire TV stick is set to install updates automatically (owner's choice, DEC-059). To be asked first instead:

- Kodi-wide: Settings → System → Add-ons → **Updates** → "Notify, but don't install updates".
- Or only for NovaFlix: Add-ons → My add-ons → Video add-ons → NovaFlix → turn **Auto-update** off.

When an update is published, Kodi shows a notice; install it from NovaFlix's add-on page → **Update**.

## Going back to an earlier version

The repository keeps the last 3 versions of NovaFlix.

1. Add-ons → My add-ons → Video add-ons → NovaFlix → **Update** (or **Versions**).
2. Pick the older version from the list.
3. Turn Auto-update off for NovaFlix, or Kodi may install the newest version again.

Your watch history survives a rollback. If an older version finds history saved by a newer one it
cannot read, it says "Please update" and leaves the data untouched (DEC-039).

## Publishing an update (owner/developer)

1. Raise `version` in `plugin.video.novaflix/addon.xml`.
2. `.venv\Scripts\python tools\build.py release` — secret scan, tests, version check, zips,
   checksums, `addons.xml`; output in `dist/repo`.
3. Copy `dist/repo` into the Pages repository (`chiefabs6-ops/novaflix-repo`) and push.
   Kodi picks the update up at its next repository check (on start, then about daily).
