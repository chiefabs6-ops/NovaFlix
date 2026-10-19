# tests/test_gui_dialogs.py
"""M12: styled popups keep the exact contracts of the Kodi dialogs they replace."""

import pytest
import xbmcaddon
import xbmcgui

from resources.lib.gui import dialogs, ids
from resources.lib.kodi import ui


@pytest.fixture(autouse=True)
def look_on():
    xbmcaddon.settings["aniverse_look"] = True


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
    assert window.xml_file == "aniverse-confirm.xml" and window.properties["message"] == "Download it?"


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
    assert window.xml_file == "aniverse-progress.xml" and window.shown
    assert window.getControl(ids.PROGRESS_BAR).percent == 42 and window.properties["message"] == "42% downloaded"
    assert progress.cancelled() is False
    window.onClick(ids.PROGRESS_CANCEL)
    assert progress.cancelled() is True and progress.wait(1) is True
    progress.close()
    assert window.closed


def test_look_off_keeps_kodi_dialogs():
    xbmcaddon.settings["aniverse_look"] = False
    xbmcgui.select_answers.append(0)
    assert ui.select_details("x", [("a", "b")]) == 0
    assert ui.confirm("h", "m") is True  # Kodi fake yesno default
    assert not any(d.xml_file.startswith("aniverse-confirm") for d in xbmcgui.xml_dialogs)
