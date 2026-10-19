"""Torrentio by IMDb id with release languages (Plan 3, Task 1)."""

from helpers import fixture
from resources.lib.sources import torrentio

SERIES = "torrentio/series_tt0903747_2_3.json"
MOVIE = "torrentio/movie_tt1160419.json"


def _flag_line(stream):
    lines = (stream.get("title") or "").split("\n")
    stats = next((i for i, line in enumerate(lines) if "👤" in line or "💾" in line), None)
    return " ".join(lines[stats + 1:]) if stats is not None else ""


def test_imdb_urls():
    assert torrentio.imdb_url(None, "tt0903747", 2, 3, False) == \
        "https://torrentio.strem.fun/stream/series/tt0903747:2:3.json"
    assert torrentio.imdb_url("https://h/", "tt1160419", None, None, True) == "https://h/stream/movie/tt1160419.json"


def test_series_streams_match_episode_and_carry_languages():
    raw = fixture(SERIES)
    found = torrentio.parse_streams(raw, 3, None, (2, 3), False)
    assert found and all(c.match in ("exact", "best_guess") for c in found)
    by_hash = {s["infoHash"].lower(): s for s in raw["streams"]}
    audio = [c for c in found if "sub" not in _flag_line(by_hash[c.info_hash]).lower()]  # "Subs" lines: subtitles
    with_uk = [c for c in audio if "🇬🇧" in _flag_line(by_hash[c.info_hash])]
    assert with_uk and all("en" in c.languages for c in with_uk)
    other = [c for c in audio if _flag_line(by_hash[c.info_hash]) and "🇬🇧" not in _flag_line(by_hash[c.info_hash])]
    assert all(c.languages and "en" not in c.languages for c in other)
    assert all(c.languages == [] for c in found if c not in audio)


def test_languages_are_unique_and_known_codes_only():
    found = torrentio.parse_streams(fixture(SERIES), 3, None, (2, 3), False)
    for c in found:
        assert len(c.languages) == len(set(c.languages))
        assert set(c.languages) <= set(torrentio.FLAGS.values())


def test_movie_streams_skip_extras():
    found = torrentio.parse_streams(fixture(MOVIE), 1, None, None, True)
    assert found and not any("sample" in (c.file_name or "").lower() for c in found)


def test_streams_without_flags_have_no_languages():
    raw = {"streams": [{"infoHash": "a" * 40, "title": "Show.S02E03.1080p.WEB.h264-GRP\n👤 5 💾 1.2 GB ⚙️ 1337x"}]}
    assert torrentio.parse_streams(raw, 3, None, (2, 3), False)[0].languages == []


def test_subtitle_flags_are_not_audio_languages():
    raw = {"streams": [{"infoHash": "a" * 40,
                        "title": "Show.S02E03.1080p.WEB.h264-GRP\n👤 5 💾 1.2 GB ⚙️ 1337x\nMulti Subs / 🇫🇷 / 🇪🇸"}]}
    assert torrentio.parse_streams(raw, 3, None, (2, 3), False)[0].languages == []


def test_title_words_do_not_make_a_film_an_extra():
    raw = {"streams": [{"infoHash": "a" * 40, "title": "The.Menu.2022.1080p.WEB-DL.x264-GRP\n👤 5 💾 1.2 GB ⚙️ 1337x",
                        "behaviorHints": {"filename": "The.Menu.2022.1080p.WEB-DL.x264-GRP.mkv"}}]}
    assert torrentio.parse_streams(raw, 1, None, None, True, titles=["The Menu"])
    assert torrentio.parse_streams(raw, 1, None, None, True) == []  # without the title it looks like a menu extra
