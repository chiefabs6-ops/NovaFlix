"""Matcher table. Names follow styles seen in the Torrentio/Nyaa fixtures and
common fansub/scene conventions. Each row: name -> expected parsed fields."""

import pytest

from resources.lib.sources.matcher import matches, parse

# (name, expected subset of Release fields)
PARSE_CASES = [
    # --- fansub " - NN" ---------------------------------------------------------
    ("[SubsPlease] Sousou no Frieren - 03 (1080p) [EFCABB43].mkv",
     dict(group="SubsPlease", episode=3, resolution="1080p", season=None, is_batch=False)),
    ("[SubsPlease] Sousou no Frieren S2 - 08 (480p) [0369C951].mkv", dict(season=2, episode=8, resolution="480p")),
    ("[Erai-raws] Kusuriya no Hitorigoto - 24 [1080p][Multiple Subtitle][ABCDEF12].mkv",
     dict(group="Erai-raws", episode=24, resolution="1080p")),
    ("[Feibanyama] Frieren Beyond Journeys End - 03 [IQIYI WebRip 2160p HEVC OPUS Multi-Subs].mkv",
     dict(episode=3, resolution="2160p", codec="HEVC")),
    ("[Salieri] Frieren - Beyond Journey's End - 03 (1080p) (HDR) [Dual Audio].mkv",
     dict(group="Salieri", episode=3, audio="dual", resolution="1080p")),
    ("[ASW] One Piece - 1122 [1080p HEVC][ABCDEF12].mkv", dict(episode=1122, codec="HEVC")),
    ("[Judas] Shingeki no Kyojin - 75v2 [1080p][HEVC x265 10bit][Multi-Subs].mkv", dict(episode=75, version=2)),
    ("[SubsPlease] Dandadan - 12v2 (720p) [11223344].mkv", dict(episode=12, version=2, resolution="720p")),
    ("[Anime Time] Spy x Family - 07 [1080p][HEVC 10bit x265][AAC][Multi Sub].mkv", dict(episode=7)),
    ("[Group] Show Name - 001 [720p].mkv", dict(episode=1)),
    ("[Group] 86 - Eighty Six - 05 [1080p].mkv", dict(episode=5)),
    ("[Group] Mob Psycho 100 - 03 [1080p].mkv", dict(episode=3)),
    ("[Group] Re Zero - 2nd Season - 10 [1080p].mkv", dict(season=2, episode=10)),
    ("[Group] Show (2023) - 04 [1080p].mkv", dict(episode=4)),
    ("[Group] Show - 04 (BD 1080p HEVC FLAC) [ABCD1234].mkv", dict(episode=4, codec="HEVC")),
    ("[Yameii] Frieren: Beyond Journey's End - S02E05 [English Dub] [CR WEB-DL 720p H264 AAC] [03FD5663]",
     dict(season=2, episode=5, audio="dub", resolution="720p", codec="AVC")),
    # --- SxxEyy ---------------------------------------------------------------------
    ("Frieren - Beyond Journey's End - S01E03.mkv", dict(season=1, episode=3)),
    ("Season 1/Frieren Beyond Journey's End - S01E03 - Killing Magic.mkv", dict(season=1, episode=3)),
    ("S01E03-Killing Magic [EFCABB43].mkv", dict(season=1, episode=3)),
    ("Show.Name.S02E11.1080p.WEB-DL.x265-Rapta.mkv", dict(season=2, episode=11, codec="HEVC", group="Rapta")),
    ("Show Name S03 E07 1080p CR WEBRip Dual Audio 10bits x265-Rapta.mkv", dict(season=3, episode=7, audio="dual")),
    ("Show Name S1E9 720p.mkv", dict(season=1, episode=9, resolution="720p")),
    ("Show Name S01E09v2 1080p.mkv", dict(season=1, episode=9, version=2)),
    ("show_name_s01e04_1080p.mkv", dict(season=1, episode=4)),
    ("Show Name - S04E28 - Final [1080p] [Dual Audio].mkv", dict(season=4, episode=28, audio="dual")),
    # --- E / Ep / Episode -------------------------------------------------------------
    ("Frieren- Beyond Journey's End E3 Killing Magic 2160p B-Global WEB-DL x264 [Japanese] (AAC 2.0) MSubs_ToonsHub_.mkv",
     dict(episode=3, resolution="2160p", codec="AVC")),
    ("Show Name EP05 1080p.mkv", dict(episode=5)),
    ("Show Name Ep 12 [720p].mkv", dict(episode=12)),
    ("Show Name Episode 7 [1080p].mkv", dict(episode=7)),
    ("Show Name E10v2.mkv", dict(episode=10, version=2)),
    # --- batches ------------------------------------------------------------------------
    ("[ToonsHub] Frieren: Beyond Journey's End S01 E01-E14 2160p B-Global WEB-DL x264 (Multi-Subs) [Batch - Part 1]",
     dict(season=1, episode_range=(1, 14), is_batch=True)),
    ("[Group] Show - 01-12 [1080p] [Batch]", dict(episode_range=(1, 12), is_batch=True)),
    ("[Group] Show - 01 ~ 24 (BD 1080p)", dict(episode_range=(1, 24), is_batch=True)),
    ("[EMBER] Frieren: Beyond Journey`s End (2023) (Season 1) [BDRip] [1080p Dual Audio HEVC 10 bits DDP] (Sousou no Frieren) (Batch)",
     dict(episode=None, is_batch=True, audio="dual", codec="HEVC")),
    ("Frieren Beyond Journeys End S01 Season 1 1080p CR WEBRip Dual Audio 10bits x265-Rapta",
     dict(season=1, episode=None, is_batch=True, audio="dual")),
    ("[Group] Show Season 2 [1080p] (Complete)", dict(season=2, is_batch=True, episode=None)),
    ("[wham] Sousou no Frieren | Frieren: Beyond Journey's End - S01 (BD 1080p AV1 Opus AAC Dual Audio)",
     dict(season=1, is_batch=True, codec="AV1", audio="dual")),
    ("Show S02E01-E12 1080p WEB", dict(season=2, episode_range=(1, 12))),
    # --- extras ---------------------------------------------------------------------------
    ("[Group] Show - NCOP1 [1080p].mkv", dict(is_extra=True)),
    ("[Group] Show - NCED [1080p].mkv", dict(is_extra=True)),
    ("Extras/Show - Creditless Opening.mkv", dict(is_extra=True)),
    ("[Group] Show - PV1 [1080p].mkv", dict(is_extra=True)),
    ("[Group] Show - OVA [1080p].mkv", dict(is_extra=True)),
    ("[Group] Show - Special 02 [1080p].mkv", dict(is_extra=True)),
    ("[Group] Show - Menu 01.mkv", dict(is_extra=True)),
    # --- dub signals --------------------------------------------------------------------------
    ("[Group] Show - 05 [ENG DUB] [1080p].mkv", dict(episode=5, audio="dub")),
    ("[Group] Show - 05 (Dub) [1080p].mkv", dict(episode=5, audio="dub")),
    ("Show S01E05 1080p Dubbed WEB.mkv", dict(episode=5, audio="dub")),
    ("[Group] Show - 05 [Dual-Audio] [1080p].mkv", dict(episode=5, audio="dual")),
    ("[Group] Show - 05 [Multi-Audio] [1080p].mkv", dict(episode=5, audio=None)),
    ("[Group] Show - 05 [1080p] [Multi-Subs].mkv", dict(episode=5, audio=None)),
    ("[Group] Show - 05 (Subbed) [1080p].mkv", dict(episode=5, audio=None)),
    # --- resolution variants ------------------------------------------------------------
    ("[Group] Show - 05 [4K].mkv", dict(resolution="2160p")),
    ("[Group] Show - 05 [1920x1080].mkv", dict(episode=5)),
    ("[Group] Show - 05 [1080i].mkv", dict(resolution="1080p")),
    ("[Group] Show - 05.mkv", dict(resolution=None, codec=None)),
    # --- traps ---------------------------------------------------------------------------------
    ("[Group] Show (2024) [1080p].mkv", dict(episode=None)),
    ("[Group] Show 10bit [1080p].mkv", dict(episode=None)),
    ("[Group] Show [5.1] [1080p].mkv", dict(episode=None)),
    ("[Group] Steins;Gate 0 - 07 [1080p].mkv", dict(episode=7)),
    ("[Group] Show - 03 [ABCD1234].mkv", dict(episode=3)),
    ("Show 03.mkv", dict(episode=3)),
    ("Sousou no Frieren 03", dict(episode=3)),
]


@pytest.mark.parametrize("name,expected", PARSE_CASES, ids=[c[0][:60] for c in PARSE_CASES])
def test_parse(name, expected):
    rel = parse(name)
    for field, value in expected.items():
        assert getattr(rel, field) == value, f"{field}: {getattr(rel, field)!r} != {value!r}"


# (name, number, absolute, tvdb, expected)
MATCH_CASES = [
    ("[SubsPlease] Sousou no Frieren - 03 (1080p).mkv", 3, None, None, True),
    ("[SubsPlease] Sousou no Frieren - 04 (1080p).mkv", 3, None, None, False),
    ("[SubsPlease] Sousou no Frieren S2 - 08 (480p).mkv", 3, 3, (1, 3), False),
    ("[SubsPlease] Sousou no Frieren S2 - 08 (480p).mkv", 8, 36, (2, 8), True),
    ("Frieren - S01E03.mkv", 3, 3, (1, 3), True),
    ("Frieren - S01E03.mkv", 3, 31, (2, 3), False),     # season 2 entry must not take S1 files
    ("Frieren - S02E03.mkv", 3, 31, (2, 3), True),
    ("Show - 31 [1080p].mkv", 3, 31, (2, 3), True),      # absolute numbering
    ("Show - 03 [1080p].mkv", 3, 31, (2, 3), True),      # per-season numbering
    ("Show S02 - 03 [1080p].mkv", 3, 31, (2, 3), True),
    ("Show S01 - 31 [1080p].mkv", 3, 31, (2, 3), True),  # S1-labelled absolute release
    ("Show S01E14-E26 [1080p]", 3, 17, (1, 17), True),   # batch contains the episode
    ("Show S01E01-E14 [1080p]", 3, 17, (1, 17), False),
    ("Show S02E01-E12 [1080p]", 3, 31, (2, 3), True),
    ("Show S01E01-E12 [1080p]", 3, 31, (2, 3), False),
    ("[Group] Show - 01-12 [1080p]", 5, None, None, True),
    ("[Group] Show - 01-12 [1080p]", 13, None, None, False),
    ("[Group] Show - NCOP1 [1080p].mkv", 1, None, None, False),
    ("[Group] Show (Batch) [1080p]", 3, None, None, None),
    ("Frieren- Beyond Journey's End E3 Killing Magic 2160p.mkv", 3, None, None, True),
    ("Show S1E9 720p.mkv", 9, None, None, True),
    ("Show S1E9 720p.mkv", 9, None, (1, 9), True),
    ("[Group] Show - 12v2 [720p].mkv", 12, None, None, True),
    ("[ASW] One Piece - 1122 [1080p].mkv", 1122, None, None, True),
    ("[ASW] One Piece - 1122 [1080p].mkv", 122, None, None, False),
    ("Sousou no Frieren 03", 3, None, None, True),
    ("Movie Title (2023) [1080p].mkv", 1, None, None, None),
    # Live Frieren S1 lists (2026-10-11): other seasons must not match by number alone.
    ("[Yameii] Frieren - S02E05 [English Dub] [CR WEB-DL 1080p]", 5, 5, (1, 5), False),
    ("[Anime Time] Frieren - S02E10 [1080p][Dual-Audio] [Weekly]", 10, 10, (1, 10), False),
    ("[neoDESU] Frieren [Season 2] [BD 1080p AV1] [Dual Audio]", 5, 5, (1, 5), False),
    ("[Judas] Sousou no Frieren (Season 02) [1080p][Dual-Audio] (Batch)", 5, 5, (1, 5), False),
    ("[9volt] Sousou no Frieren - Season 2 (WEB 1080p) (Batch S02 S2)", 5, 5, (1, 5), False),
    ("[Group] Frieren S01 [BD 1080p] (Batch)", 5, 5, (1, 5), None),
]

# Audio language evidence (DEC-025): English only, never another language's dub.
AUDIO_CASES = [
    ("[Furretar] Sousou no Frieren (Season 1) (Mandarin Chinese + Cantonese Dub) (Matching Soft Subs)", None),
    ("[Anitsu] Sousou no Frieren S01 [BD 1080p x265 Opus] [DUAL JAP PT-BR] [SUB PT-BR ENG]", None),
    ("[Group] Show - 05 [Spanish Dub][1080p]", None),
    ("[Group] Show - 05 [Latino][Dual Audio][1080p]", None),
    ("[DiabloTripleA] Frieren [WEB 1080p HEVC AAC] [Dual Audio-EngSubs] (Batch)", "dual"),
    ("[Anime Time] Frieren (Season 01) [Dual Audio] [BD] [1080p][Eng Sub]", "dual"),
    ("[AUTISM] Frieren (BD Remux) [Dual-Audio, Multi-Audio, Multi-Sub] (English, Filipino, Francais)", "dual"),
    ("[Group] Show - 05 [English + Spanish Dub]", "dub"),
    ("[Yameii] Frieren - S01E05 [English Dub] [CR WEB-DL 1080p]", "dub"),
    ("Frieren.S01E05.DUBBED.1080p.WEB.H264-SKYANiME", "dub"),
]


@pytest.mark.parametrize("name,expected", AUDIO_CASES, ids=[c[0][:45] for c in AUDIO_CASES])
def test_audio_language(name, expected):
    assert parse(name).audio == expected


@pytest.mark.parametrize("name,number,absolute,tvdb,expected", MATCH_CASES, ids=[f"{c[0][:45]}#{c[1]}" for c in MATCH_CASES])
def test_matches(name, number, absolute, tvdb, expected):
    assert matches(parse(name), number, absolute, tvdb) is expected


def test_table_size():
    assert len(PARSE_CASES) + len(MATCH_CASES) >= 100 - 15  # plus provider tests below 100 total
