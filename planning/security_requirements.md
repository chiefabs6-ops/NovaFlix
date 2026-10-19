# Security and Reliability Requirements — AniVerse v1

Status: Proposed with the implementation plan; derived from approved decisions (DEC-017, DEC-020, DEC-035, DEC-037, DEC-038) and `research/risks_and_unknowns.md`.

Each requirement has a verification method. "Test" = automated test in `tests/`; "Check" = manual or build-time check.

| ID | Requirement | Verification |
|---|---|---|
| SEC-01 | No credentials, tokens, API keys or client secrets in source code. The only embedded identifier is Real-Debrid's **public** open-source client ID `X245A4XAIBGVM`, which is documented by RD and is not a secret. | Build-time secret scan of package + repo (`tools/build.py`); code review |
| SEC-02 | No real credentials in Git history. Test fixtures are sanitized (placeholder tokens like `TEST_TOKEN`). | Secret scan over `git log -p` before first push and before each release |
| SEC-03 | Tokens, refresh tokens, client secrets, auth/device codes, MAL client ID, RD unrestricted/download URLs never appear in logs at any level. | Test: run flows with sentinel secrets and assert absence in captured log output |
| SEC-04 | Exception messages and notifications are redacted the same way (URLs with query strings and RD download hosts masked). | Test: raise from `net/http.py` with sentinel values; assert redacted `str(exc)` |
| SEC-05 | HTTPS only for every external call; certificate verification on; no `verify=False` equivalents. | Test: `net/http.py` rejects `http://` URLs; code review |
| SEC-06 | Token refresh: proactive (< 10 min to expiry, checked per call) and reactive (401 / code 8 → one refresh + one retry). Refresh failure → clear "Reconnect" dialog, no loop. | Tests with mocked RD responses |
| SEC-07 | Disconnect revokes (`/disable_access_token`, best effort) and deletes all stored RD values; message is truthful if revoke failed. | Test + manual |
| SEC-08 | Timeouts on every request (10 s default, 15 s unrestrict); bounded retries (≤ 2, GET only, exponential backoff); no retry of POST. | Tests |
| SEC-09 | Rate limits: per-host limiter (RD ≤ 200/min; AniList ≤ 30/min; others ≤ 60/min); honour `Retry-After`; RD code 5 / HTTP 429 handled without hammering. | Tests |
| SEC-10 | Expired authorization never presented as "bad source" or "no results"; distinct message (DEC-035). | Tests mapping each RD error code to its presentation |
| SEC-11 | Local storage: user data under Kodi `addon_data` only. Documentation states plainly that Kodi has no secure keystore and tokens are stored in plain text on the device. | Check: README/settings help text |
| SEC-12 | No telemetry; no data sent anywhere except the services needed for a user action (AniList, ani.zip, MAL, MAL-Dubs, AniSkip, Torrentio, Nyaa, Real-Debrid). The RD token is sent **only** to Real-Debrid; the MyAnimeList token **only** to myanimelist.net / api.myanimelist.net. | Test: provider requests contain no RD token; code review |
| SEC-13 | The add-on never claims success it did not observe: "Connected" only after `/user` succeeds; "Playing" only after Kodi reports `onAVStarted`. | Tests + manual |
| SEC-14 | Repository serves over HTTPS with SHA-256 checksums; packages contain no secrets (packages are publicly reachable — DEC-038). | Build check |
| SEC-15 | Plugin→service hand-off (window properties) contains IDs only, never URLs or tokens. | Test |
