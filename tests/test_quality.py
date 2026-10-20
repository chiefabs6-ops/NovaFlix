"""Release-title quality parser (sources/quality.py). Each row: name -> expected Quality fields."""

import pytest

from resources.lib.models import Candidate
from resources.lib.sources import quality
from resources.lib.sources.quality import parse

PARSE_CASES = [
    ("Movie.2026.1080p.BluRay.x264-GROUP",
     dict(resolution="1080p", source="BluRay", video_codec="AVC", cam=None, tier="1080p")),
    ("Movie.2026.2160p.WEB-DL.HEVC-GROUP",
     dict(resolution="2160p", source="WEB-DL", video_codec="HEVC", cam=None, tier="uhd")),
    ("Movie.2026.720p.WEBRip.x265-GROUP", dict(resolution="720p", source="WEBRip", video_codec="HEVC", cam=None)),
    ("Movie.2026.480p.DVDRip-GROUP", dict(resolution="480p", source="DVDRip", cam=None, tier="sd")),
    ("Movie.2026.2160p.BluRay.REMUX.DV.HDR10.DTS-HD.MA-GROUP",
     dict(resolution="2160p", source="REMUX", hdr=["DV", "HDR10"], audio=["DTS-HD MA"], cam=None, tier="uhd")),
    ("Movie.2026.1080p.WEB-DL.DDP5.1.H.264-GROUP",
     dict(source="WEB-DL", video_codec="AVC", audio=["DDP"], channels="5.1")),
    ("Movie.2026.1080p.BluRay.TrueHD.7.1.Atmos-X", dict(audio=["TrueHD", "Atmos"], channels="7.1")),
    ("Movie 2026 2160p UHD BluRay DTS:X HDR10+ HEVC", dict(audio=["DTS:X"], hdr=["HDR10+"], source="BluRay")),
    ("Movie.2026.WEB-DL.DD+5.1", dict(audio=["DDP"], channels="5.1", resolution=None, tier="other")),
    # loose resolution words
    ("Movie.2026.4K.HDR", dict(resolution="2160p", resolution_exact=False, hdr=["HDR"])),
    ("Movie.2026.UHD.BluRay", dict(resolution="2160p", source="BluRay")),
    ("Movie.2026.FHD.WEB", dict(resolution="1080p", source="WEB")),
    ("Movie.2026.Full.HD", dict(resolution="1080p")),
    ("Movie.2026.HD.WEBRip", dict(resolution="720p", source="WEBRip")),
    ("Movie.2026.SD.TVRip", dict(resolution="SD", tier="sd")),
    ("Movie.2026.576i.PAL.DVD", dict(resolution="576p", source="DVDRip")),
    ("Movie 4K Remastered 1080p BluRay", dict(resolution="1080p", resolution_exact=True)),  # pixel height wins
    # HD / HDR / technical tags are never cinema recordings
    ("Movie.2026.HDR.HD", dict(cam=None, hdr=["HDR"], resolution="720p")),
    ("Movie.2026.1080p.BluRay.DTS-HD.MA.5.1", dict(cam=None, resolution="1080p", audio=["DTS-HD MA"])),
    ("Movie.2026.1080p.HDTV.x264", dict(cam=None, source="HDTV")),
    ("Movie.2026.1080p.HDRip", dict(cam=None, source="HDRip")),
]


@pytest.mark.parametrize("name,expected", PARSE_CASES)
def test_parse(name, expected):
    q = parse(name)
    got = {k: getattr(q, k) for k in expected}
    assert got == expected


CAM_CASES = [
    ("Movie.2026.HDCAM.1080p-GROUP", "CAM"),
    ("Movie.2026.CAMRip-GROUP", "CAM"),
    ("Movie.2026.CAM-Rip.x264", "CAM"),
    ("Movie 2026 HD CAM", "CAM"),
    ("Movie 2026 Hindi HQ Cam", "CAM"),
    ("movie_2026_camrip", "CAM"),
    ("Movie.2026.HDTS-GROUP", "TS"),
    ("Movie.2026.HD-TS.x264", "TS"),
    ("Movie.2026.TS.XviD", "TS"),
    ("Movie.2026.TSRip", "TS"),
    ("Movie.2026.TELESYNC-GROUP", "TS"),
    ("Movie 2026 Tele Sync", "TS"),
    ("Movie.2026.HDTC", "TC"),
    ("Movie.2026.TeleCine", "TC"),
    ("Movie.2026.PDVD", "PDVD"),
    ("Movie.2026.PreDVDRip", "PDVD"),
    ("Movie.2026.Pre-DVD", "PDVD"),
]


@pytest.mark.parametrize("name,tag", CAM_CASES)
def test_cinema_recordings(name, tag):
    q = parse(name)
    assert q.cam == tag and q.is_cam
    assert q.tier == quality.OTHER  # its claimed resolution says nothing about its picture


NOT_CAM = [
    "Movie.2026.HDR.2160p.WEB-DL",
    "Movie.2026.HD.720p",
    "Movie.2026.1080p.BluRay.DTS.x264",           # "TS" inside "DTS"
    "Lots.Of.Bits.Tsunami.Ghosts.2026.1080p",     # "ts" inside words
    "Movie.2026.1080p.WEB.MPEG-TS",               # transport stream, not a telesync
    "Movie.2026.1080p.M2TS.BluRay",
    "Movie.2026.1080p.WEB-DL.mkv",
    "Show.S01E01.1080p.WEB.ts",                   # .ts file extension
    "Movie.2026.Webcam.Footage.1080p",            # "cam" inside a word
    "Movie.2026.Scam.1080p",
    "Movie.2026.KORSUB.HDRip",                    # burned-in subtitles are not a cinema recording
    "Movie.2026.HC.HDRip.x264",
]


@pytest.mark.parametrize("name", NOT_CAM)
def test_not_cinema_recordings(name):
    assert parse(name).cam is None


def test_title_words_are_never_tags():
    # A film called "Cam" (2018) and an episode called "TS" are not cinema recordings.
    assert parse("Cam.2018.1080p.WEB-DL.x264-GRP").cam == "CAM"
    assert parse("Cam.2018.1080p.WEB-DL.x264-GRP", ["Cam"]).cam is None
    assert parse("Show.S01E02.TS.1080p.WEB", ["Show", "TS"]).cam is None


def test_hardcoded_subtitles_are_a_separate_warning():
    assert parse("Movie.2026.KORSUB.HDRip").hardsub == "KORSUB"
    assert parse("Movie.2026.Kor.Subs.720p").hardsub == "KORSUB"
    assert parse("Movie.2026.HC.HDRip").hardsub == "HC"
    assert parse("Movie.2026.1080p.WEB-DL").hardsub is None


def test_conflicting_tags_are_unknown_not_guessed():
    q = parse("Movie.2026.720p.1080p.WEB")
    assert q.resolution is None and "conflicting resolution" in q.warnings and q.tier == quality.OTHER
    q = parse("Movie.2026.1080p.BluRay.WEB-DL")
    assert q.source is None and "conflicting source" in q.warnings
    # Same family is no conflict.
    assert parse("Movie.2026.1080p.BluRay.REMUX").source == "REMUX"
    assert parse("Movie.2026.1080p.WEB-DL.WEB").source == "WEB-DL"


@pytest.mark.parametrize("name", ["", "   ", None, 42, "...", "_-_", "a.b-c d", "Ünïcødé ☃ 1080p", "[]()"])
def test_odd_names_are_safe(name):
    q = parse(name)
    assert q.cam is None
    assert quality.score(q) == quality.score(quality.Quality()) or q.resolution


def test_unknown_format_keeps_everything_unknown():
    q = parse("Some.Random.Upload.2026.mkv")
    assert (q.resolution, q.source, q.video_codec, q.hdr, q.audio, q.cam) == (None, None, None, [], [], None)
    assert q.tier == quality.OTHER


def test_candidate_quality_file_first_then_pack_then_provider_label():
    c = Candidate(origin="torrentio", release_name="Show.S01.2160p.WEB-DL.DV-GRP",
                  file_name="Show.S01E03.1080p.mkv", resolution="2160p")
    q = quality.of_candidate(c)
    assert (q.resolution, q.source, q.hdr) == ("1080p", "WEB-DL", ["DV"])  # file says 1080p
    c = Candidate(origin="torrentio", release_name="Some Upload", resolution="720p")
    assert quality.of_candidate(c).resolution == "720p"  # Torrentio's own label
    c = Candidate(origin="torrentio", release_name="Show.S01.HDTS", file_name="Show.S01E03.1080p.mkv")
    assert quality.of_candidate(c).is_cam  # a cinema tag in any name counts


def test_score_order_is_explainable():
    s = {n: quality.score(parse(n)) for n in [
        "M.2160p.BluRay.REMUX.DV.TrueHD.Atmos", "M.2160p.WEB-DL.HDR", "M.1080p.BluRay.x264",
        "M.1080p.WEBRip", "M.720p.HDTV", "M.480p.DVDRip", "M.HDCAM.2160p"]}
    names = sorted(s, key=s.get, reverse=True)
    assert names == ["M.2160p.BluRay.REMUX.DV.TrueHD.Atmos", "M.2160p.WEB-DL.HDR", "M.1080p.BluRay.x264",
                     "M.1080p.WEBRip", "M.720p.HDTV", "M.480p.DVDRip", "M.HDCAM.2160p"]


def test_weights_can_be_changed_without_code_changes():
    weights = {k: (dict(v) if isinstance(v, dict) else v) for k, v in quality.WEIGHTS.items()}
    weights["source"]["WEBRip"] = 50
    assert quality.score(parse("M.1080p.WEBRip"), weights) > quality.score(parse("M.1080p.BluRay"), weights)


def test_summary_for_the_details_line():
    q = parse("Movie.2026.2160p.BluRay.REMUX.DV.HDR10.TrueHD.7.1.Atmos-GRP")
    assert quality.summary(q) == ["REMUX", "DV HDR10", "TrueHD Atmos 7.1"]
    assert quality.summary(quality.Quality()) == []


# Live names, 2026-10-20 (Street Fighter / The Odyssey source lists).
@pytest.mark.parametrize("name,kind", [
    ("street.fighter.2026.4rabetrip.mp4", "betting"),
    ("street.fighter.2026.1xbet.rip.mp4", "betting"),
    ("Movie 2026 MelBet 1080p", "betting"),
    ("Watch_Street_Fighter_(2026)_Free_HD___Movies_-_Fli.mp4", "watch free"),
    ("Movie 2026 Free HD Movies Online", "watch free"),
])
def test_spam(name, kind):
    q = parse(name)
    assert q.spam == kind and q.suspect and q.tier == quality.OTHER


@pytest.mark.parametrize("name", ["Watchmen.2009.1080p.BluRay", "Free.Guy.2021.1080p.WEB-DL",
                                  "Movie.2026.1080p.WEB-DL.DDP5.1-BETTER"])
def test_not_spam(name):
    assert parse(name).spam is None


def test_hq_pre_is_a_cinema_copy():
    assert parse("Street Fighter 2026.1080p.HQ Pre.Multi.AAC 2.0.x264").cam == "PDVD"


def test_other_year_for_movies():
    def year_of(name, year):
        return quality.of_candidate(Candidate(origin="torrentio", release_name=name), year=year).other_year
    assert year_of("15 Filmow z Jean-Claude Van Damme 1988-1998 [1080p.BluRay]", 2026) == 1998
    assert year_of("The Odyssey - Prologue (2025) IMAX 4K", 2026) is None   # a year either side is fine
    assert year_of("Dune.1984.1080p.BluRay", 2021) == 1984
    assert year_of("Blade.Runner.1982.Final.Cut.2007.Remaster.1080p", 1982) is None  # its own year is there
    assert year_of("Movie.1080p.WEB-DL", 2026) is None          # no year stated: never marked
    assert year_of("Movie.2026.1920x1080.WEB", 2026) is None    # a size is not a year
    assert year_of("Dune.1984.1080p.BluRay", None) is None      # TV / unknown year: never marked
