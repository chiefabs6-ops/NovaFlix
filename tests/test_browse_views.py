import copy

import xbmc
import xbmcgui
import xbmcplugin

from helpers import FakeNet, fixture
from resources.lib import errors, router
from resources.lib.kodi import paths
from resources.lib.metadata import dubs

BASE = "plugin://plugin.video.aniverse/"
TRENDING = fixture("anilist_trending.json")
FRIEREN = fixture("anilist_media_154587.json")
ANIZIP = fixture("anizip_154587.json")
AIRING = fixture("anilist_airing.json")
DUBS = fixture("mal_dubs.json")


def labels():
    return [item.getLabel() for _, _, item, _ in xbmcplugin.directory_items]


def urls():
    return [url for _, url, _, _ in xbmcplugin.directory_items]


def dispatch(path, query=""):
    router.dispatch([BASE + path, "1", query])


def test_trending_lists_shows_with_info_and_next_page():
    FakeNet().route("graphql.anilist.co", TRENDING)
    dispatch("trending")
    media = TRENDING["data"]["Page"]["media"]
    shows = [i for _, u, i, _ in xbmcplugin.directory_items if "/show?" in u]
    assert len(shows) == len(media)
    assert shows[0].tag.values["MediaType"] in ("tvshow", "movie")
    assert shows[0].art.get("poster")
    if TRENDING["data"]["Page"]["pageInfo"]["hasNextPage"]:
        assert labels()[-1] == "Next page"
        assert "page=2" in urls()[-1]
    assert xbmcplugin.content[1] == "tvshows"
    assert xbmcplugin.end_calls[-1][1] is True


def test_dub_badge_shown_for_dubbed_titles():
    data = copy.deepcopy(TRENDING)
    data["data"]["Page"]["media"][0]["idMal"] = 52991
    FakeNet().route("MAL-Dubs", DUBS)
    dubs.refresh(paths.profile_dir())
    FakeNet().route("graphql.anilist.co", data)
    dispatch("trending")
    assert "DUB" in labels()[0]


def test_network_failure_shows_friendly_message_without_traceback():
    FakeNet().route("graphql.anilist.co", OSError("offline"))
    dispatch("popular")
    assert xbmcgui.notifications[-1][1].startswith("Couldn't load this")
    assert xbmcplugin.end_calls[-1][1] is False
    assert not any("Traceback" in m for _, m in xbmc.log_records)


def test_rate_limit_shows_busy_message(monkeypatch):
    from resources.lib.net import http
    monkeypatch.setattr(http, "_sleep", lambda s: None)

    class Limited:
        def __call__(self, *a):
            return 429, {"Retry-After": "120"}, b""

    http.set_transport(Limited())
    dispatch("trending")
    assert "busy" in xbmcgui.notifications[-1][1]


def test_recently_aired_labels_include_episode_and_link_to_show():
    FakeNet().route("graphql.anilist.co", AIRING)
    dispatch("recent")
    first = AIRING["data"]["Page"]["airingSchedules"][0]
    assert f"Episode {first['episode']}" in labels()[0]
    assert f"id={first['media']['id']}" in urls()[0]


def test_genres_menu_links_to_genre_lists():
    FakeNet().route("graphql.anilist.co", fixture("anilist_genres.json"))
    dispatch("genres")
    assert "Action" in labels() and "Hentai" not in labels()
    assert any("genre?name=Slice+of+Life" in u for u in urls())


def test_lists_display_our_label_so_badges_show():
    FakeNet().route("graphql.anilist.co", TRENDING)
    dispatch("trending")
    assert xbmcplugin.label_masks == ["%L"]


def test_new_search_entry_is_an_action_not_a_folder():
    dispatch("search")
    assert xbmcplugin.directory_items[0][3] is False


def test_search_new_opens_keyboard_then_updates_container():
    xbmcgui.input_answers.append("frieren")
    dispatch("search/new")
    assert xbmcplugin.end_calls == []
    assert xbmc.builtins_executed == [f"Container.Update({BASE}search/results?q=frieren)"]


def test_search_new_cancelled_does_nothing():
    dispatch("search/new")
    assert xbmc.builtins_executed == []


def test_search_results_are_listed_and_remembered():
    FakeNet().route("graphql.anilist.co", TRENDING)
    dispatch("search/results", "?q=frieren")
    assert any("/show?" in u for u in urls())
    xbmcplugin.reset()
    dispatch("search")
    assert labels()[0] == "New search..."
    assert "frieren" in labels()
    assert labels()[-1] == "Clear recent searches"


def test_search_results_empty_notifies():
    data = copy.deepcopy(TRENDING)
    data["data"]["Page"]["media"] = []
    data["data"]["Page"]["pageInfo"]["hasNextPage"] = False
    FakeNet().route("graphql.anilist.co", data)
    dispatch("search/results", "?q=zzzz")
    assert xbmcgui.notifications[-1][1] == "Nothing found"


def test_clear_recent_searches():
    FakeNet().route("graphql.anilist.co", TRENDING)
    dispatch("search/results", "?q=frieren")
    dispatch("search/clear")
    xbmcplugin.reset()
    dispatch("search")
    assert labels() == ["New search..."]


def test_show_page_lists_related_then_episodes():
    data = copy.deepcopy(FRIEREN)
    media = data["data"]["Media"]
    media["status"], media["nextAiringEpisode"], media["episodes"] = "FINISHED", None, 28
    FakeNet().route("graphql.anilist.co", data).route("api.ani.zip", ANIZIP)
    dispatch("show", "?id=154587")
    assert labels()[0] == "Related & sequels"
    assert labels()[1] == "1. The Journey`s End"
    assert labels()[5] == "Episode 5"  # no ani.zip data in trimmed fixture
    assert len(labels()) == 1 + 28
    episode_item = xbmcplugin.directory_items[1][2]
    assert episode_item.tag.values["Episode"] == 1
    assert episode_item.properties["IsPlayable"] == "true"
    assert xbmcplugin.content[1] == "episodes"


def test_show_page_without_aired_episodes_explains_why():
    data = copy.deepcopy(FRIEREN)
    data["data"]["Media"]["status"] = "NOT_YET_RELEASED"
    data["data"]["Media"]["nextAiringEpisode"] = None
    FakeNet().route("graphql.anilist.co", data).route("api.ani.zip", ANIZIP)
    dispatch("show", "?id=154587")
    assert labels()[-1] == "No episodes have aired yet"


def _franchise(**rows):
    from resources.lib.metadata.franchise import ROWS, Franchise
    return Franchise(title="Frieren", rows={name: rows.get(name, []) for name in ROWS})


def _related_with(monkeypatch, result):
    from resources.lib.metadata import catalog
    from resources.lib.models import Show, ShowRef
    shown = Show(anilist_id=154587, title="Frieren",
                 relations=[ShowRef(anilist_id=2, relation="SEQUEL", format="TV", title="x")])
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, i: shown)
    monkeypatch.setattr(catalog.Catalog, "franchise", lambda self, i: result)
    dispatch("related", "?id=154587")


def test_related_page_lists_rows_in_order_with_year_and_format(monkeypatch):
    from resources.lib.models import RelationNode as N
    _related_with(monkeypatch, _franchise(
        movies=[N(5, "The Movie", "MOVIE", start=(2024, 1, 1))],
        sequels=[N(2, "Season 2", "TV", start=(2026, 1, 9)), N(3, "Season 3", "TV")],
        side_stories=[N(4, "Mini", "ONA", start=(2024, 3, 1))]))
    assert labels() == ["[Sequels] Season 2 (2026 · TV)", "[Sequels] Season 3 (TV)",
                        "[Side stories] Mini (2024 · ONA)", "[Movies] The Movie (2024 · Movie)"]
    assert urls()[0] == BASE + "show?id=2"


def test_home_entries_now_route_to_real_sections():
    dispatch("")
    by_label = dict(zip(labels(), urls()))
    assert by_label["Trending Now"] == BASE + "trending"
    assert by_label["Search"] == BASE + "search"
    assert by_label["Genres"] == BASE + "genres"


def test_related_entries_show_dub_badge(monkeypatch):
    from resources.lib.models import RelationNode as N
    FakeNet().route("MAL-Dubs", DUBS)
    dubs.refresh(paths.profile_dir())
    _related_with(monkeypatch, _franchise(sequels=[N(2, "Season 2", "TV", mal_id=52991)]))
    assert labels()[0].startswith("[Sequels]") and "DUB" in labels()[0]
