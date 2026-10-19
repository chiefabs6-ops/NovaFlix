# plugin.video.novaflix/resources/lib/gui/malhub.py
"""My Anime List view of the app window: one card per MyAnimeList status with its count and
share of the whole list. Counts load in the background, each status on its own; a card opens
that status as a grid ("mal:<status>")."""

from resources.lib.gui import ids, lists
from resources.lib.kodi import ui
from resources.lib.metadata import mal
from resources.lib.views import mylists

SUBTITLES = {"watching": 30294, "plan_to_watch": 30295, "completed": 30296, "on_hold": 30297, "dropped": 30298}


class MalHubView:
    def __init__(self, app):
        self.app = app
        self.counts = {}
        self.failed = False

    def load(self):
        w = self.app.window
        self.counts, self.failed = {}, False
        client_id, username = mylists._mal_settings()
        w.setProperty("mal_title", ui.string(30289))
        w.setProperty("mal_user", username)
        for status in mal.STATUSES:
            w.setProperty(f"mal_{status}_title", ui.string(mylists.STATUS_STRINGS[status]))
            w.setProperty(f"mal_{status}_text", ui.string(SUBTITLES[status]))
            w.setProperty(f"mal_{status}_count", "...")
        self._bars()
        if not mylists._mal_ready(client_id, username):
            self.app.report(mal.MalSetupMissing("MyAnimeList client ID or username missing"))
            self.app.back()
            return
        self.focus()
        self.app.loader.start({s: (lambda s=s: lists.mal_count(s)) for s in mal.STATUSES}, self._deliver)

    def _deliver(self, status, result, error):
        if error:
            if not self.failed:  # one report for the whole view, then leave it like a failed grid
                self.failed = True
                self.app.report(error)
                self.app.back()
            return
        count, more = result
        self.counts[status] = count
        self.app.window.setProperty(f"mal_{status}_count", f"{count}+" if more else str(count))
        self._bars()

    def _bars(self):
        total = sum(self.counts.values())
        for status, control_id in zip(mal.STATUSES, ids.MAL_BARS):
            share = round(100 * self.counts.get(status, 0) / total) if total else 0
            self.app.window.getControl(control_id).setPercent(share)

    def focus(self):
        self.app.window.setFocusId(ids.MAL_CARDS[0])

    def on_click(self, control_id):
        status = mal.STATUSES[ids.MAL_CARDS.index(control_id)]
        self.app.open_grid(f"mal:{status}")
