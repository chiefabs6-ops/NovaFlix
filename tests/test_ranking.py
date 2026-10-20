"""Source list ranking: cinema-recording filter, quality tabs, sort orders, duplicates."""

from resources.lib.models import Candidate
from resources.lib.sources import quality, ranking


def cand(name, info_hash, size_gb=1, origin="torrentio", **kw):
    return Candidate(origin=origin, release_name=name, info_hash=info_hash, size_bytes=int(size_gb * 1e9), **kw)


SOURCES = [
    cand("Movie.2026.HDCAM.2160p-GRP", "1" * 40, 3),
    cand("Movie.2026.1080p.WEBRip.x264-GRP", "2" * 40, 2),
    cand("Movie.2026.1080p.BluRay.x264-GRP", "3" * 40, 9),
    cand("Movie.2026.2160p.WEB-DL.HDR.HEVC-GRP", "4" * 40, 15),
    cand("Movie.2026.2160p.BluRay.REMUX.DV.TrueHD.Atmos-GRP", "5" * 40, 60),
    cand("Movie.2026.720p.HDTV-GRP", "6" * 40, 1),
    cand("Movie.2026.480p.DVDRip-GRP", "7" * 40, 0.7),
    cand("Movie 2026 strange upload", "8" * 40, 4),
    cand("Movie.2026.TELESYNC-GRP", "9" * 40, 1),
]


def names(result):
    return [c.release_name for c in result.shown]


def fresh():
    return [Candidate.from_dict(c.to_dict()) for c in SOURCES]


def test_cam_filter_on_hides_cinema_recordings_whatever_they_claim():
    result = ranking.build(fresh(), ranking.Filters(), False)
    assert result.hidden_cam == 2 and result.hidden_by_filters == 2
    assert not any("CAM" in n or "TELESYNC" in n for n in names(result))


def test_cam_filter_off_lists_them_last_in_other():
    result = ranking.build(fresh(), ranking.Filters(hide_cam=False), False)
    assert result.hidden_cam == 0 and len(result.shown) == len(SOURCES)
    assert names(result)[-2:] == ["Movie.2026.HDCAM.2160p-GRP", "Movie.2026.TELESYNC-GRP"]  # never on top
    assert all(c.quality.tier == quality.OTHER for c in result.shown if c.quality.is_cam)


def test_best_order_prefers_resolution_then_source():
    result = ranking.build(fresh(), ranking.Filters(), False)
    assert names(result) == [
        "Movie.2026.2160p.BluRay.REMUX.DV.TrueHD.Atmos-GRP",
        "Movie.2026.2160p.WEB-DL.HDR.HEVC-GRP",
        "Movie.2026.1080p.BluRay.x264-GRP",
        "Movie.2026.1080p.WEBRip.x264-GRP",
        "Movie.2026.720p.HDTV-GRP",
        "Movie 2026 strange upload",          # unknown resolution: middle score, still listed
        "Movie.2026.480p.DVDRip-GRP",
    ]


def test_tiers_count_each_source_once():
    result = ranking.build(fresh(), ranking.Filters(), False)
    assert result.tiers() == {"uhd": 2, "1080p": 2, "720p": 1, "sd": 1, "other": 1}
    assert sum(result.tiers().values()) == len(result.shown)


def test_tier_of_a_release_with_several_resolution_words():
    result = ranking.build([cand("Movie.2026.4K.UHD.2160p.HDR", "a" * 40)], ranking.Filters(), False)
    assert result.tiers() == {"uhd": 1}


def test_duplicates_are_listed_once():
    twice = fresh() + fresh()
    result = ranking.build(twice, ranking.Filters(), False)
    assert len(result.shown) == 7 and sum(result.tiers().values()) == 7


def test_sort_by_size_and_source_and_hdr():
    by_size = ranking.build(fresh(), ranking.Filters(), False, sort=ranking.SIZE)
    sizes = [c.size_bytes for c in by_size.shown]
    assert sizes == sorted(sizes, reverse=True)
    by_source = ranking.build(fresh(), ranking.Filters(), False, sort=ranking.SOURCE)
    assert [c.quality.source for c in by_source.shown][:3] == ["REMUX", "BluRay", "WEB-DL"]
    by_hdr = ranking.build(fresh(), ranking.Filters(), False, sort=ranking.HDR)
    assert [c.quality.hdr for c in by_hdr.shown][:2] == [["DV"], ["HDR"]]
    by_res = ranking.build(fresh(), ranking.Filters(), False, sort=ranking.RESOLUTION)
    assert [c.quality.resolution for c in by_res.shown][:3] == ["2160p", "2160p", "1080p"]


def test_hardsub_filter_is_optional():
    kor = [cand("Movie.2026.1080p.KORSUB.HDRip", "a" * 40), cand("Movie.2026.1080p.WEB-DL", "b" * 40)]
    assert len(ranking.build(kor, ranking.Filters(), False).shown) == 2  # off by default
    result = ranking.build([Candidate.from_dict(c.to_dict()) for c in kor], ranking.Filters(hide_hardsubs=True),
                           False)
    assert names(result) == ["Movie.2026.1080p.WEB-DL"] and result.hidden_cam == 0


def test_min_resolution_uses_the_parsed_resolution():
    # Torrentio labelled it 2160p from "4K", but the name says 1080p.
    c = cand("Movie.2026.4K.Remastered.1080p.BluRay", "a" * 40, resolution="2160p")
    assert not ranking.build([c], ranking.Filters(min_resolution="2160p"), False).shown


def test_account_and_pinned_stay_on_top_in_best_order():
    account = cand("Movie.2026.720p.WEBRip", "a" * 40, origin="rdcloud", rd_torrent_id="1", rd_file_id=1)
    pinned = cand("Movie.2026.1080p.WEBRip-PIN", "b" * 40, release_group="PIN", resolution="1080p")
    best = cand("Movie.2026.2160p.BluRay.REMUX", "c" * 40)
    result = ranking.build([best, pinned, account], ranking.Filters(), False, "PIN", "1080p")
    assert [c.info_hash[0] for c in result.shown] == ["a", "b", "c"]


def test_titles_keep_title_words_out_of_tags():
    film = cand("Cam.2018.1080p.WEB-DL.x264-GRP", "a" * 40)
    assert not ranking.build([film], ranking.Filters(), False).shown
    film = cand("Cam.2018.1080p.WEB-DL.x264-GRP", "a" * 40)
    assert ranking.build([film], ranking.Filters(), False, titles=["Cam"]).shown


def test_quality_is_never_saved_with_the_candidate():
    result = ranking.build(fresh(), ranking.Filters(), False)
    data = result.shown[0].to_dict()
    assert "quality" not in data and Candidate.from_dict(data).quality is None


def test_spam_and_other_year_are_listed_last_not_hidden():
    sources = [cand("street.fighter.2026.4rabetrip", "a" * 40, 4),
               cand("Van Damme Collection 1988-1998 1080p BluRay", "b" * 40, 9),
               cand("Street.Fighter.2026.720p.WEBRip", "c" * 40, 1),
               cand("Street fighter 2026", "d" * 40, 2)]
    for sort in ranking.SORTS:
        fresh_sources = [Candidate.from_dict(c.to_dict()) for c in sources]
        result = ranking.build(fresh_sources, ranking.Filters(), False, titles=["Street Fighter"], sort=sort,
                               year=2026)
        assert len(result.shown) == 4 and result.hidden_by_filters == 0
        assert {c.info_hash[0] for c in result.shown[-2:]} == {"a", "b"}, sort


def test_year_is_only_checked_when_given():
    c = cand("Van Damme Collection 1988-1998 1080p BluRay", "a" * 40)
    assert ranking.build([c], ranking.Filters(), False).shown[0].quality.other_year is None


def test_warnings_are_coloured_on_the_details_line():
    from resources.lib.views import sources
    spam = cand("street.fighter.2026.4rabetrip 1080p", "a" * 40)
    ranking.build([spam], ranking.Filters(), False)
    line = sources.details_line(spam)
    assert "[COLOR FFFF4D6D]Looks like spam[/COLOR]" in line
    assert line.rsplit(" · ", 1)[-1] == "Not checked yet"  # status stays last and uncoloured
    clean = cand("Movie.2026.1080p.WEB-DL", "b" * 40)
    ranking.build([clean], ranking.Filters(), False)
    assert "[COLOR" not in sources.details_line(clean)
