from resources.lib import redact

SECRET = "SENTINELTOKEN0123456789abcdef"


def test_registered_secret_is_masked_anywhere():
    redact.register_secret(SECRET)
    text = f"refresh failed for {SECRET} (token={SECRET})"
    assert SECRET not in redact.text(text)


def test_short_or_empty_secrets_are_ignored():
    # Masking "" or "ab" would mangle every message.
    redact.register_secret("")
    redact.register_secret("ab")
    assert redact.text("about a cab") == "about a cab"


def test_url_query_string_is_removed():
    out = redact.text("GET https://api.example.com/v1/x?client_id=abc&code=XYZ failed")
    assert "abc" not in out and "XYZ" not in out
    assert "https://api.example.com/v1/x" in out


def test_url_function_drops_query_and_fragment():
    assert redact.url("https://h.example/p/a?token=1#frag") == "https://h.example/p/a?<redacted>"
    assert redact.url("https://h.example/p/a") == "https://h.example/p/a"


def test_bearer_token_is_masked():
    out = redact.text("Authorization: Bearer abc.def-ghi_123")
    assert "abc.def-ghi_123" not in out


def test_real_debrid_download_links_are_masked():
    out = redact.text("stream https://abc12.download.real-debrid.com/d/ABCDEF123/Episode.01.mkv ready")
    assert "ABCDEF123" not in out
    assert "Episode.01.mkv" not in out
    out = redact.text("link https://real-debrid.com/d/QWERTY987")
    assert "QWERTY987" not in out


def test_sensitive_key_value_pairs_are_masked():
    out = redact.text('{"access_token": "aaa111", "refresh_token": "bbb222", "client_secret": "ccc333"}')
    for value in ("aaa111", "bbb222", "ccc333"):
        assert value not in out


def test_headers_are_masked_by_name():
    headers = {"Authorization": "Bearer X", "X-MAL-CLIENT-ID": "Y", "User-Agent": "AniVerse"}
    masked = redact.headers(headers)
    assert masked["Authorization"] == "<redacted>"
    assert masked["X-MAL-CLIENT-ID"] == "<redacted>"
    assert masked["User-Agent"] == "AniVerse"


def test_magnet_links_are_masked():
    out = redact.text("adding magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=Show")
    assert "dn=Show" not in out
