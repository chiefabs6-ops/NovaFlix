# plugin.video.novaflix/resources/lib/gui/checks.py
"""Background availability checks for next-episode cards (Continue Watching row and grid). Each next
episode is checked once per screen load; the card's label and action change in place when its result
arrives. Grids check the rows around the selection as the owner scrolls. One failed check only affects
its card."""

from resources.lib.gui import cards
from resources.lib.kodi import ui
from resources.lib.sources import availability

MAX_CHECKS = 20  # cards checked from `start` on; grids check further as the owner scrolls (GRID_AHEAD)
GRID_COLUMNS = 6
GRID_AHEAD = 18  # from the selected card's row: the rows on screen and the next one


class AvailabilityChecks:
    def __init__(self, app):
        self.app = app
        self.results = {}      # (media_type, tmdb_id, season, episode) -> Availability, for this screen load
        self.started = set()
        self.target = None     # (control_id, cards) shown now

    def reset(self):
        self.results.clear()
        self.started.clear()
        self.target = None

    def follow_grid(self, control_id, page_cards, position):
        """The grid selection moved: check the rows around it."""
        if position >= 0:
            self.watch(control_id, page_cards, position - position % GRID_COLUMNS, GRID_AHEAD)

    def watch(self, control_id, page_cards, start=0, count=MAX_CHECKS):
        """Cards were just put into control_id (or the selection moved): apply known results,
        check the unchecked ones among page_cards[start:start + count]."""
        self.target = (control_id, page_cards)
        jobs = {}
        for index, card in enumerate(page_cards):
            if not card.check or card.avail != "checking":
                continue
            if card.check in self.results:
                self._apply(control_id, index, card, self.results[card.check])
            elif card.check not in self.started and start <= index < start + count:
                self.started.add(card.check)
                jobs["%s:%d:%d:%d" % card.check] = lambda key=card.check: availability.check(*key)
        if jobs:
            self.app.loader.start(jobs, self._deliver)

    def _deliver(self, name, result, error):
        media_type, tmdb_id, season, episode = name.split(":")
        key = (media_type, int(tmdb_id), int(season), int(episode))
        if key not in self.started:
            return  # checked for a screen load that has been reset since
        result = result if error is None else availability.Availability(availability.UNKNOWN)
        self.results[key] = result
        if self.target is None:
            return
        control_id, page_cards = self.target
        for index, card in enumerate(page_cards):
            if card.check == key and card.avail == "checking":
                self._apply(control_id, index, card, result)

    def _apply(self, control_id, index, card, result):
        cards.apply_availability(card, result, ui.string)
        control = self.app.window.getControl(control_id)
        if index < control.size():
            item = control.getListItem(index)
            item.setLabel2(card.label2)
            item.setProperty("avail", card.avail)
