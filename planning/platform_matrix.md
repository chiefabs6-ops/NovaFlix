# Platform Support Matrix (v1)

Source decisions: DEC-001, DEC-007, DEC-008, DEC-009, DEC-040. Background: `research/platform_compatibility.md`.

| Platform | Device | Kodi | Python (bundled) | `xbmc.python` | Role |
|---|---|---|---|---|---|
| Fire OS (Android-based) | Fire TV Stick 4K, 2nd gen (2023) | 21.x Omega | 3.11.x (per research) | 3.0.1 | **Primary — release gate** |
| Windows 11 | Owner's PC | 21.x Omega | 3.11.x | 3.0.1 | Secondary — must pass |
| Kodi 22 Piers | — | not supported in v1 | 3.14 | 3.1.0 | Revisit when final |
| Vega OS Fire TV devices | — | Kodi cannot run | — | — | Unsupported |
| Linux / macOS / other Android TV | — | — | — | — | Not tested; not blocked by design (portable code) |

Constraints that follow:
- Pure-Python only; no compiled dependencies.
- Kodi 20+ APIs (`InfoTagVideo`), no deprecated `setInfo`.
- Data under `special://profile/addon_data/<addon id>/`; tokens there in plain text (no keystore) — documented limitation.
- Performance budget sized for a 2 GB-RAM stick (unverified spec; confirm on device).

Confirmed on the owner's device via ADB (2026-10-10):
- Model `AFTKRT` (Fire TV Stick 4K 2nd gen), Android 11 (Fire OS 8), Kodi **21.2**, Kodi ABI **armeabi-v7a (32-bit)**, MemTotal ≈ 1.7 GB, ~5.5 GB free storage.
- Kodi needs Android "All files access" (`MANAGE_EXTERNAL_STORAGE`) to see `.zip` files in `/sdcard/Download`; granted by owner request via `appops`.
- Kodi log readable via `adb logcat -s Kodi` (app data folder is not readable over ADB on Android 11).
- Windows dev machine: Kodi **21.3** installed via winget.
