# plugin.video.novaflix/resources/lib/gui/show.py
"""Show page window (M12): banner hero, Play/Resume, Favourite, Related, MyAnimeList, episode row.
Availability (sources/availability.py, the same check as Continue Watching): the Play episode is
checked once per page load and shown under the buttons; episodes with a saved result get a dot."""

import xbmcgui

from resources.lib import router
from resources.lib.gui import actions, cards, dialogs, ids, items
from resources.lib.gui.loader import Loader, PlaybackWatch, Ticker, report
from resources.lib.kodi import paths, ui
from resources.lib.metadata.catalog import Catalog
from resources.lib.myanimelist import auth, progress, sync
from resources.lib.sources import availability
from resources.lib.storage.favourites import Favourites
from resources.lib.storage.history import History


class ShowWindow(xbmcgui.WindowXML):
    page = None

    def onInit(self):
        self.page.on_init()

    def onAction(self, action):
        self.page.on_action(action)

    def onClick(self, control_id):
        self.page.on_click(control_id)


class ShowPage:
    def __init__(self, window, anilist_id, loader):
        self.window = window
        self.anilist_id = int(anilist_id)
        self.loader = loader
        self.result = None
        self.data = None
        self.cards = []
        self.next = (1, 0)
        self.watch = PlaybackWatch()
        self._started = False
        self.avail = {}        # episode -> Availability: saved results and this page's checks
        self.checking = set()  # episodes whose check is running (never started twice)

    def on_init(self):
        if self._started:  # Kodi calls onInit again when fullscreen video closes
            show_id = actions.take_open_show()  # End episode: this page, or another show's
            if show_id and show_id != self.anilist_id:
                self.result = ("show", show_id)
                self.window.close()
            return
        self._started = True
        self.window.setProperty("loading", "true")
        self.loader.start({"show": self._fetch}, self._deliver)

    def _fetch(self):
        catalog = Catalog()
        show = catalog.show(self.anilist_id)
        episodes = catalog.episodes(show)
        return {"show": show, "episodes": episodes, "fanart": catalog.fanart(show),
                "dub": catalog.dub_estimates(show, [e.number for e in episodes]),
                "dub_status": catalog.dub_status(show),
                "mal": progress.show_entry(show.mal_id, network=False),
                "mal_login": auth.MalStore(paths.profile_dir()).logged_in,
                "avail": availability.cached_episodes(show.anilist_id, [e.number for e in episodes])}

    def _deliver(self, name, data, error):
        self.window.setProperty("loading", "")
        if error:
            report(error, "show page")
            self.window.close()
            return
        self.data = data
        self.avail.update(data["avail"])
        self._fill_header()
        self.refresh()
        self.window.setFocusId(ids.SHOW_PLAY)
        # MyAnimeList progress arrives on its own: the page never waits for MAL (spec §6).
        mal_id = data["show"].mal_id
        if mal_id and data["mal"] is None:
            self.loader.start({"mal": lambda: progress.show_entry(mal_id)}, self._deliver_mal)

    def _deliver_mal(self, name, entry, error):
        if entry and self.data:
            self.data["mal"] = entry
            self.refresh()

    def _fill_header(self):
        show, w = self.data["show"], self.window
        hero = cards.hero(show, self.data["fanart"], ui.string)
        for key in ("title", "alt", "plot", "meta", "art"):
            w.setProperty(key, hero[key])
        w.setProperty("dark", "true" if hero["dark"] else "")
        w.setProperty("poster", show.poster or "")
        w.setProperty("genres", " · ".join(show.genres[:4]))
        dub = items.DUB_TEXT.get(self.data["dub_status"])
        w.setProperty("dub", ui.string(dub) if dub else "")
        w.setProperty("has_related", "true" if show.relations else "")
        w.setProperty("related_label", ui.string(30034))
        w.setProperty("episodes_title", ui.string(30261))

    def refresh(self):
        """Episodes, ticks, progress and button labels; re-run after playback and marks."""
        if not self.data:
            return
        show, episodes = self.data["show"], self.data["episodes"]
        states = progress.merge_states(History(paths.profile_dir()).states(self.anilist_id), self.data.get("mal"))
        self.cards = [cards.episode_card(show, ep, states.get(ep.number), self.data["dub"].get(ep.number), ui.string)
                      for ep in episodes]
        for card in self.cards:
            known = self.avail.get(card.action[2])
            card.avail = known.state if known else ""
        control = self.window.getControl(ids.SHOW_EPISODES)
        position = max(control.getSelectedPosition(), 0)
        control.reset()
        control.addItems(items.to_listitems(self.cards))
        if self.cards:
            control.selectItem(min(position, len(self.cards) - 1))
        self.next = cards.next_episode([e.number for e in episodes], states)
        episode, resume_s = self.next
        if show.is_movie:
            label = ui.string(30235)
        elif resume_s:
            label = ui.string(30247) % (episode, cards.clock(resume_s))
        else:
            label = ui.string(30246) % episode
        self.window.setProperty("play_label", label)
        self._show_availability(episode)
        self.window.setProperty("no_episodes", "" if episodes else ui.string(30035))
        self.window.setProperty("mal", progress.mal_line(self.data.get("mal"), ui.string))
        favs = Favourites(paths.profile_dir())
        try:
            favourite = self.anilist_id in favs.ids()
        finally:
            favs.close()
        self.window.setProperty("favourite_label", ui.string(30249 if favourite else 30248))
        self.window.setProperty("favourited", "true" if favourite else "")
        mal_action = self._mal_action()
        self.window.setProperty("mal_label", ui.string({"mal_add": 30307, "mal_remove": 30308}[mal_action])
                                if mal_action else "")

    def _mal_action(self):
        """The MyAnimeList button: "mal_add", "mal_remove" or None (hidden: no MAL ID, or the
        owner's entry is not known yet / MAL unreachable). Logged out: Add, which explains the login."""
        if not self.data["show"].mal_id:
            return None
        if not self.data["mal_login"]:
            return "mal_add"
        entry = self.data.get("mal")
        if entry is None:
            return None
        return "mal_remove" if entry.get("list_status") else "mal_add"

    def _show_availability(self, number):
        """Status line for the Play episode: saved result at once, else checking until the
        background check answers. A failed check reads "could not check", never "no streams"."""
        known = self.avail.get(number)
        if known is None:
            self.window.setProperty("avail", "checking")
            self.window.setProperty("avail_line", ui.string(30299) % number)
            if number not in self.checking:
                self.checking.add(number)
                self.loader.start({str(number): lambda: availability.check(self.anilist_id, number)},
                                  self._deliver_availability)
            return
        self.window.setProperty("avail", known.state)
        self.window.setProperty("avail_line", cards.availability_text(known, number, ui.string,
                                                                      cards.SHOW_AVAIL_TEXT))

    def _deliver_availability(self, name, result, error):
        number = int(name)
        self.checking.discard(number)
        self.avail[number] = result if error is None else availability.Availability(availability.UNKNOWN)
        self.refresh()

    def _reload_availability(self):
        """After playback: the played episode's sources are saved now; read the saved results again."""
        numbers = [e.number for e in self.data["episodes"]]
        self.loader.start({"avail": lambda: availability.cached_episodes(self.anilist_id, numbers)},
                          self._deliver_saved)

    def _deliver_saved(self, name, saved, error):
        if saved:
            self.avail.update(saved)
            self.refresh()

    def on_click(self, control_id):
        if not self.data:
            return
        if control_id == ids.SHOW_PLAY and self.data["episodes"]:
            actions.play_episode(self.anilist_id, *self.next)
        elif control_id == ids.SHOW_FAVOURITE:
            self._toggle_favourite()
        elif control_id == ids.SHOW_MAL:
            self._mal_button()
        elif control_id == ids.SHOW_RELATED:
            self.result = ("related", self.anilist_id)
            self.window.close()
        elif control_id == ids.SHOW_EPISODES:
            card = self._selected()
            if card:
                actions.episode_choice(self.anilist_id, card.action[2])

    def _mal_button(self):
        """Same add / remove as the long-press menu of a card (actions.mal_edit)."""
        key = self._mal_action()
        if not key:
            return
        entry = self.data.get("mal") if self.data["mal_login"] else None
        changed = actions.mal_edit(key, self.anilist_id, self.data["show"], entry)
        if changed is not None:
            self.data["mal"] = changed
            self.refresh()

    def on_action(self, action):
        if action.getId() in ids.ACTION_BACK:
            self.window.close()
        elif action.getId() in ids.ACTION_CONTEXT and self.window.getFocusId() == ids.SHOW_EPISODES:
            self._episode_menu()

    def _selected(self):
        position = self.window.getControl(ids.SHOW_EPISODES).getSelectedPosition()
        return self.cards[position] if 0 <= position < len(self.cards) else None

    def _toggle_favourite(self):
        favs = Favourites(paths.profile_dir())
        try:
            if self.anilist_id in favs.ids():
                favs.remove(self.anilist_id)
                ui.notify("NovaFlix", ui.string(30064))
            else:
                favs.add(self.data["show"])
                ui.notify(self.data["show"].title, ui.string(30063))
        finally:
            favs.close()
        self.refresh()

    def _episode_menu(self):
        card = self._selected()
        if not card:
            return
        number = card.action[2]
        choice = dialogs.menu(card.label, [ui.string(30222 if card.watched else 30221), ui.string(30230)])
        if choice == 0:
            watched = not card.watched
            History(paths.profile_dir()).mark(self.anilist_id, number, watched)
            sync.queue(paths.profile_dir(), self.data["show"].mal_id, "watched" if watched else "unwatched", number)
            self.data["mal"] = progress.apply(self.data.get("mal"), "watched" if watched else "unwatched", number)
            self.refresh()
        elif choice == 1:
            actions.play_url(router.build_url("play", id=self.anilist_id, ep=number, refresh=1))

    def tick(self):
        text = actions.phone_search()
        if text:  # the paired phone asked for a search: the results open in the NovaFlix window
            self.result = ("grid", f"search:{text}")
            self.window.close()
            return
        if self.watch.ended():
            self.refresh()
            if self.data:
                self._reload_availability()


def open_show(anilist_id, loader=None, start_ticker=True):
    window = ShowWindow("novaflix-show.xml", ui.addon().getAddonInfo("path"), "Default", "1080i")
    page = ShowPage(window, anilist_id, loader or Loader())
    window.page = page
    ticker = Ticker(page.tick)
    if start_ticker:
        ticker.start()
    try:
        window.doModal()
    finally:
        ticker.stop()
        page.loader.cancel()  # a late result must not report after the page is gone
    return page.result
