# plugin.video.novaflix/resources/lib/gui/items.py
"""Card -> xbmcgui.ListItem for the NovaFlix layouts (M12)."""

import xbmcgui


def to_listitem(card):
    item = xbmcgui.ListItem(label=card.label, label2=card.label2, offscreen=True)
    art = {}
    if card.poster:
        art.update(poster=card.poster, icon=card.poster)
    icon = ""
    if card.wide and card.wide.startswith("icon:"):
        icon = f"av-icon-{card.wide[5:]}.png"
    elif card.wide:
        art.update(thumb=card.wide, fanart=card.wide)
    if art:
        item.setArt(art)
    item.setProperty("watched", "true" if card.watched else "")
    item.setProperty("note", card.note)
    item.setProperty("status", card.status)
    item.setProperty("kind", card.kind)
    item.setProperty("avail", card.avail)
    item.setProperty("icon", icon)
    item.setProperty("has_wide", "true" if card.wide and not icon else "")
    for key in ("plot", "year", "rating", "genres", "kind_label", "badge"):
        item.setProperty(key, getattr(card, key))
    if card.position > 0 and card.duration > 0:
        item.getVideoInfoTag().setResumePoint(card.position, card.duration)
    return item


def to_listitems(cards):
    return [to_listitem(c) for c in cards]
