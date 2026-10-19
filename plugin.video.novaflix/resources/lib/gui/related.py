# plugin.video.novaflix/resources/lib/gui/related.py
"""More like this view of the app window: a movie's collection and TMDB's recommendations as
Home-style rows. Rows are filled from the top, so empty ones are always at the bottom and hidden by the layout."""

from resources.lib.gui import ids, items, lists
from resources.lib.kodi import log, ui


class RelatedView:
    def __init__(self, app):
        self.app = app
        self.key = None
        self.rows = []

    def load(self, media_type, tmdb_id):
        self.key = f"more:{media_type}:{tmdb_id}"
        self.rows = []
        w = self.app.window
        for n, control_id in enumerate(ids.RELATED_ROWS):
            w.getControl(control_id).reset()
            w.setProperty(f"rel{n}_title", "")
        for name in ("related_title", "related_notice", "related_status"):
            w.setProperty(name, "")
        w.setProperty("loading", "true")
        self.app.loader.start({self.key: lambda: lists.more_like_this(media_type, int(tmdb_id))}, self._deliver)

    def _deliver(self, key, page, error):
        if key != self.key:
            return
        w = self.app.window
        w.setProperty("loading", "")
        if error:
            log.warning(f"{key}: {type(error).__name__}: {error}")
            w.setProperty("related_status", ui.string(30241))
            w.setFocusId(ids.SIDEBAR)
            return
        w.setProperty("related_title", page.title)
        w.setProperty("related_notice", page.notice)
        w.setProperty("related_status", page.empty)
        self.rows = [row_cards for _, row_cards in page.rows]
        for n, (title, row_cards) in enumerate(page.rows):
            w.setProperty(f"rel{n}_title", title)
            w.getControl(ids.RELATED_ROWS[n]).addItems(items.to_listitems(row_cards))
        self.focus()

    def focus(self):
        w = self.app.window
        target = ids.RELATED_ROWS[0] if self.rows else ids.SIDEBAR
        if w.getFocusId() not in ids.RELATED_ROWS[:len(self.rows)]:
            w.setFocusId(target)

    def selected(self, control_id):
        n = ids.RELATED_ROWS.index(control_id)
        if n >= len(self.rows):
            return None
        position = self.app.window.getControl(control_id).getSelectedPosition()
        row = self.rows[n]
        return row[position] if 0 <= position < len(row) else None

    def on_click(self, control_id):
        card = self.selected(control_id)
        if card:
            self.app.run(card.action)
