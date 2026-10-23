# tests/test_gui_items.py
from resources.lib.gui import cards, items


def test_card_to_listitem():
    card = cards.Card(label="Frieren", label2="Ep 5 · 11:26 left", poster="p.jpg", wide="b.jpg",
                      position=754.0, duration=1440.0, note="(Dub expected Fri 20 Feb)", kind="show")
    item = items.to_listitem(card)
    assert (item.getLabel(), item.label2) == ("Frieren", "Ep 5 · 11:26 left")
    assert item.art == {"poster": "p.jpg", "thumb": "b.jpg", "icon": "p.jpg", "fanart": "b.jpg"}
    assert item.properties["has_wide"] == "true"
    assert item.properties["note"] == "(Dub expected Fri 20 Feb)" and item.properties["kind"] == "show"
    assert item.tag.values["ResumePoint"] == 754.0


def test_tile_icon_and_missing_art():
    item = items.to_listitem(cards.tile("Comedy", ("grid", "genre:Comedy"), icon="grid_view"))
    assert item.properties["icon"] == "av-icon-grid_view.png" and item.art == {}
    assert "ResumePoint" not in item.tag.values


def test_listitem_carries_card_details():
    card = cards.Card(label="Charade", plot="Widowed in Paris.", year="1963", rating="★ 7.9",
                      genres="Thriller, Romance", kind_label="Movie")
    props = items.to_listitem(card).properties
    assert (props["plot"], props["year"], props["rating"]) == ("Widowed in Paris.", "1963", "★ 7.9")
    assert (props["genres"], props["kind_label"]) == ("Thriller, Romance", "Movie")
