# tests/test_gui_dialogs.py
"""M12: styled popups keep the exact contracts of the Kodi dialogs they replace."""

import pytest
import xbmcaddon
import xbmcgui

from resources.lib.gui import dialogs, ids
from resources.lib.kodi import ui


@pytest.fixture(autouse=True)
def look_on():
    xbmcaddon.settings["novaflix_look"] = True


def click(control_id):
    return lambda window: window.onClick(control_id)


def back(window):
    window.onAction(xbmcgui.Action(92))


def choose(position):
    def run(window):
        list_id = ids.SOURCES_LIST if ids.SOURCES_LIST in window.controls else ids.MENU_LIST
        window.getControl(list_id).selectItem(position)
        window.onClick(list_id)
    return run


def test_confirm_yes_no_and_back():
    xbmcgui.modal_scripts.extend([click(ids.CONFIRM_YES), click(ids.CONFIRM_NO), back])
    assert ui.confirm("TorBox", "Download it?") is True
    assert ui.confirm("TorBox", "Download it?") is False
    assert ui.confirm("TorBox", "Download it?") is False
    window = xbmcgui.xml_dialogs[-1]
    assert window.xml_file == "novaflix-confirm.xml" and window.properties["message"] == "Download it?"


def test_source_dialog_returns_position_like_kodi():
    rows = [("[A] Show - 01", "1080p · Ready to play"), ("Check more sources (4 not checked)", "")]
    xbmcgui.modal_scripts.append(choose(1))
    assert ui.select_details("Frieren — Episode 1", rows) == 1
    window = xbmcgui.xml_dialogs[-1]
    listed = window.getControl(ids.SOURCES_LIST).items
    assert [i.properties["status"] for i in listed] == ["ready", "action"]
    assert listed[0].properties["note"] == "Ready to play"
    assert window.properties["heading"] == "Frieren — Episode 1"


def test_source_dialog_back_is_cancel():
    xbmcgui.modal_scripts.append(back)
    assert ui.select_details("x", [("a", "b")]) == -1


def test_menu_and_resume_choice():
    xbmcgui.modal_scripts.extend([choose(1), choose(0), choose(1), back])
    assert dialogs.menu("Frieren", ["Mark as watched", "Choose a different source"]) == 1
    assert dialogs.resume_choice(754) is True
    assert dialogs.resume_choice(754) is False
    assert dialogs.resume_choice(754) is None
    labels = [i.getLabel() for i in xbmcgui.xml_dialogs[-1].getControl(ids.MENU_LIST).items]
    assert labels == ["Resume from 12:34", "From start"]


def test_progress_contract():
    progress = ui.Progress("Downloading", "Starting")
    progress.update(42, "42% downloaded")
    window = xbmcgui.xml_dialogs[-1]
    assert window.xml_file == "novaflix-progress.xml" and window.shown
    assert window.getControl(ids.PROGRESS_BAR).percent == 42 and window.properties["message"] == "42% downloaded"
    assert progress.cancelled() is False
    window.onClick(ids.PROGRESS_CANCEL)
    assert progress.cancelled() is True and progress.wait(1) is True
    progress.close()
    assert window.closed


def test_look_off_keeps_kodi_dialogs():
    xbmcaddon.settings["novaflix_look"] = False
    xbmcgui.select_answers.append(0)
    assert ui.select_details("x", [("a", "b")]) == 0
    assert ui.confirm("h", "m") is True  # Kodi fake yesno default
    assert not any(d.xml_file.startswith("novaflix-confirm") for d in xbmcgui.xml_dialogs)


def test_source_dialog_focuses_the_requested_row():
    # The quality row sits on top; the first source is selected so OK still plays the best one.
    rows = [("Quality: All (2) — 4K / UHD 1 · 1080p 1", ""), ("[A] Movie 2160p", "2160p · Ready to play")]
    xbmcgui.modal_scripts.append(back)
    ui.select_details("Movie", rows, focus=1)
    assert xbmcgui.xml_dialogs[-1].getControl(ids.SOURCES_LIST).getSelectedPosition() == 1


def test_source_dialog_shows_the_title_being_played():
    ui.set_window_property("novaflix.source_art", "b.jpg")
    ui.set_window_property("novaflix.source_title", "Charade")
    xbmcgui.modal_scripts.append(back)
    ui.select_details("Charade · Sources", [("Charade 2160p", "Ready to play")])
    window = xbmcgui.xml_dialogs[-1]
    assert (window.properties["art"], window.properties["title"]) == ("b.jpg", "Charade")
    assert window.getControl(ids.SOURCES_LIST).items[0].properties["badge"] == "4K"


def test_confirm_uses_given_labels():
    xbmcgui.modal_scripts.append(click(ids.CONFIRM_YES))
    assert ui.confirm("TorBox", "Download it?", yes="Download and play", no="Not now", note="58 GB") is True
    props = xbmcgui.xml_dialogs[-1].properties
    assert (props["yes"], props["no"], props["note"], props["single"]) == ("Download and play", "Not now", "58 GB", "")


def test_confirm_defaults_to_yes_and_no():
    xbmcgui.modal_scripts.append(back)
    ui.confirm("TorBox", "Download it?")
    props = xbmcgui.xml_dialogs[-1].properties
    assert (props["yes"], props["no"], props["note"]) == ("Yes", "No", "")


def test_message_hides_no_button():
    xbmcgui.modal_scripts.append(click(ids.CONFIRM_YES))
    ui.ok("Charade · Sources", "No sources left after your filters (6 hidden).")
    window = xbmcgui.xml_dialogs[-1]
    assert window.xml_file == "novaflix-confirm.xml"
    assert (window.properties["single"], window.properties["yes"]) == ("true", "OK")


def test_select_uses_styled_menu():
    xbmcgui.modal_scripts.append(choose(1))
    assert ui.select("Which file is this episode?", ["E03.mkv", "E04.mkv"]) == 1
    assert xbmcgui.xml_dialogs[-1].xml_file == "novaflix-menu.xml"


def test_progress_stats_skip_missing_values():
    progress = ui.Progress("Charade", "Downloading on TorBox...")
    progress.update(42, "42% downloaded", {"speed": "18.4 MB/s"})
    props = xbmcgui.xml_dialogs[-1].properties
    assert props["stat_speed"] == "18.4 MB/s"
    assert (props["stat_left"], props["stat_size"], props["stat_seeders"]) == ("", "", "")
    assert props["percent"] == "42%"
    progress.update(50, "50% downloaded")  # the old call shape still works
    progress.close()


def test_look_off_ok_and_select_stay_kodi():
    xbmcaddon.settings["novaflix_look"] = False
    xbmcgui.select_answers.append(1)
    assert ui.select("h", ["a", "b"]) == 1
    ui.ok("h", "m")
    assert not any(d.xml_file in ("novaflix-confirm.xml", "novaflix-menu.xml") for d in xbmcgui.xml_dialogs)


def test_tab_chips_are_chosen_on_the_row():
    import json
    ui.set_window_property("novaflix.source_tabs", json.dumps(
        [{"title": "Quality", "chips": ["All 3", "4K 1", "1080p 2"], "open": 0}]))

    def script(window):
        row = window.getControl(ids.SOURCES_LIST).items[0]
        assert row.properties["kind"] == "tabs" and row.properties["chip_focus"] == "0"
        assert row.properties["chip_open"] == "0" and row.properties["chip2"] == "1080p 2"
        window.onAction(xbmcgui.Action(2))  # right
        window.onAction(xbmcgui.Action(2))
        assert row.properties["chip_focus"] == "2"
        window.onAction(xbmcgui.Action(2))  # stays on the last chip
        window.onAction(xbmcgui.Action(1))  # left
        window.getControl(ids.SOURCES_LIST).selectItem(0)
        window.onClick(ids.SOURCES_LIST)
    xbmcgui.modal_scripts.append(script)
    assert ui.select_details("x", [("Quality: All (3) — 4K / UHD 1 · 1080p 2", ""), ("a 2160p", "Ready to play")]) == 0
    assert ui.get_window_property("novaflix.source_chip") == "1"
