"""English-only release filter (Plan 3, Task 3) and the English / Polish source list tabs."""

import pytest

from helpers import fixture
from resources.lib.models import Candidate
from resources.lib.sources import language, torrentio


def cand(name, languages=(), file_name=None):
    return Candidate(origin="torrentio", release_name=name, file_name=file_name, info_hash="a" * 40,
                     languages=list(languages))


@pytest.mark.parametrize("name,languages,kept", [
    ("Breaking Bad / Сезон: 2 MVO (LostFilm) + Original", ["en", "ru"], True),  # Russian voice-over plus the original
    ("Breaking Bad Full 1080p PT-BR", ["pt"], False),
    ("Breaking.Bad.S02E03.1080p.WEB.h264-GRP", [], True),                     # no language evidence at all
    ("Breaking.Bad.S02E01-13.1080p.NF.WEB-DL.ITA-ENG.DDP5.1", [], True),
    ("Film.2021.1080p.ITA.AC3", [], False),
    ("Dune.2021.4K.MULTi.VFF.2160p.HDR.WEB", [], True),
    ("[SUB ITA] Show S01E01 1080p", [], True),                                 # subtitles say nothing about audio
    ("Breaking Bad (S02)(2009)(1080p)( EN 5.1+SPA 2.0)", [], True),
    ("Film.2021.PL.1080p.WEB-DL", [], False),
])
def test_english_only(name, languages, kept):
    assert language.allowed(cand(name, languages)) is kept


def test_polish_can_be_added_later():
    polish = cand("Film.2021.PL.1080p.WEB-DL")
    assert language.allowed(polish, ("en", "pl")) and not language.allowed(polish, ("en",))
    assert language.allowed(cand("Film 2021 Lektor PL 1080p"), ("en", "pl"))
    assert language.allowed(cand("x", ["pl"]), ("en", "pl"))


def test_file_name_counts_as_evidence():
    assert not language.allowed(cand("Show S01 1080p", file_name="Show.S01E03.ITA.mkv"))


def test_split_counts_hidden():
    kept, hidden = language.split([cand("A.1080p", []), cand("B PT-BR", ["pt"]), cand("C", ["en", "ru"])])
    assert [c.release_name for c in kept] == ["A.1080p", "C"] and hidden == 1


def test_recorded_breaking_bad_list():
    found = torrentio.parse_streams(fixture("torrentio/series_tt0903747_2_3.json"), 3, None, (2, 3), False)
    kept, hidden = language.split(found)
    assert kept and hidden
    assert all("en" in c.languages or not c.languages or language.MULTI in language.languages_of(c)
               or "en" in language.languages_of(c) for c in kept)
    assert not any(c.languages == ["pt"] for c in kept)


@pytest.mark.parametrize("name", ["Cast.Away.2000.1080p.BluRay.x264", "The.Italian.Job.2003.1080p.BluRay",
                                  "Spanish.Prisoner.1997.1080p"])
def test_language_words_in_titles_are_not_audio(name):
    # Words of the film's own title are never audio evidence.
    assert language.allowed(cand(name), title="The Italian Job" if "Italian" in name else
                            "The Spanish Prisoner" if "Spanish" in name else "Cast Away")


# -- review fixes ------------------------------------------------------------------------

def test_episode_name_words_are_not_audio():
    seinfeld = cand("Seinfeld.S02E11.1080p.WEB-DL", file_name="Seinfeld.S02E11.The.Chinese.Restaurant.1080p.WEB-DL.mkv")
    assert language.allowed(seinfeld, title=["Seinfeld", "The Chinese Restaurant"])
    friends = cand("Friends.S01E05.1080p", file_name="Friends.S01E05.The.One.with.the.East.German.Laundry.Detergent.mkv")
    assert language.allowed(friends, title=["Friends", "The One with the East German Laundry Detergent"])


@pytest.mark.parametrize("name", ["Movie.2021.1080p.WEB.H264-GER", "Movie.2021.1080p.WEB.x264-HUN",
                                  "Some.Movie.Spa.Weekend.2020.1080p", "Show.S01E02.Ita.Story.1080p"])
def test_group_tags_and_title_case_words_are_not_audio(name):
    assert language.allowed(cand(name))


# -- language tabs -----------------------------------------------------------------------

@pytest.mark.parametrize("name,languages,tabs", [
    ("Dune.2021.1080p.BluRay.x264-GRP", [], {"en"}),                          # no evidence: English
    ("Inception (2010) [PL] [BRRip] [XviD] [Lektor PL]", ["pl"], {"pl"}),
    ("Film.2021.PL.1080p.WEB-DL", [], {"pl"}),
    ("Film.2021.Dubbing.PL.Napisy.PL.1080p", [], {"pl"}),
    ("Oppenheimer.2023.Eng.Fre.Ger.Ita.Spa.Cze.Pol.2160p.BluRay.Remux-SGF", [], {"en", "pl"}),
    ("Film.2021.1080p.WEB-DL.Napisy.PL", [], {"en"}),                         # Polish subtitles only
    ("Film.2021.1080p.WEB-DL.PLSUBBED", [], {"en"}),
    ("Film.2021.1080p.ITA.AC3", [], set()),
    ("Dune.2021.4K.MULTi.VFF.2160p.HDR.WEB", [], {"en"}),                     # MULTi without Polish stated
    # VisionQuest, live 2026-10-20: an English-only WEB-DL whose flag line lists its subtitle tracks.
    ("VisionQuest S01E01 No Strings 2160p DSNP WEB-DL DDP5 1 Atmos DV HDR H 265-FLUX",
     ["en", "ja", "it", "pt", "es", "ko", "zh", "fr", "de", "nl", "pl", "cs", "hu", "tr"], {"en"}),
    ("VisionQuest.S01E01-E01.MULTi.2160p.DSNP.WEB-DL.DV.HDR.H.265.DDP5.1.Atmos-K83", ["en", "pl"], {"en", "pl"}),
    ("VisionQuest (2026) [S01E01-02] PLDUB.480p.DSNP.WEB-DL.H.264.DDP5.1-K83", [], {"pl"}),
])
def test_language_tabs(name, languages, tabs):
    c = cand(name, languages)
    assert {t for t in language.TABS if language.in_tab(c, t)} == tabs


def test_tabs_count_releases_in_no_tab():
    en, pl, both, ita = cand("A.1080p"), cand("B PL", ["pl"]), cand("C", ["en", "pl"]), cand("D.ITA")
    found, hidden = language.tabs([en, pl, both, ita])
    assert found == {"en": [en, both], "pl": [pl, both]} and hidden == 1
