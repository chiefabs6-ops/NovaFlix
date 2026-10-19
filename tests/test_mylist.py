"""My List and search history (Plan 4, Task 1)."""

from helpers import fixture
from resources.lib import media
from resources.lib.kodi import paths
from resources.lib.storage import mylist, searches
from resources.lib.storage.mylist import MyList


def bb():
    return media.title_from(fixture("tmdb/tv_1396.json"), media.TV)


def dune():
    return media.title_from(fixture("tmdb/movie_438631.json"), media.MOVIE)


def test_my_list_add_contains_remove_newest_first(monkeypatch):
    clock = iter([1.0, 2.0])
    monkeypatch.setattr(mylist, "_clock", lambda: next(clock))
    my = MyList(paths.profile_dir())
    my.add(bb())
    my.add(dune())
    assert my.contains("tv", 1396) and my.contains("movie", 438631) and not my.contains("tv", 1)
    saved = my.all()
    assert [t.key for t in saved] == ["movie:438631", "tv:1396"]
    assert (saved[1].title, saved[1].poster, saved[1].year) == ("Breaking Bad", bb().poster, 2008)
    my.remove("movie", 438631)
    assert [t.key for t in my.all()] == ["tv:1396"]


def test_search_history_keeps_ten_newest_without_duplicates(monkeypatch):
    clock = iter(range(1, 100))
    monkeypatch.setattr(searches, "_clock", lambda: float(next(clock)))
    directory = paths.profile_dir()
    for n in range(12):
        searches.remember(directory, f"q{n}")
    searches.remember(directory, "q5")
    recent = searches.recent(directory)
    assert recent[0] == "q5" and len(recent) == 10 and len(set(recent)) == 10 and "q0" not in recent
