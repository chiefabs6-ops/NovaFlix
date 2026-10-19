# plugin.video.novaflix/resources/lib/gui/ids.py
"""Control IDs shared by the Python controllers and the XML layouts (M12).
tests/test_layouts.py checks every ID listed in WINDOW_IDS exists in its layout."""

SIDEBAR = 100
SIDEBAR_SETTINGS = 101
HERO_PLAY = 201
HERO_INFO = 202
HOME_ROWS = (300, 310, 320, 330)
HOME_RETRY = 340
GRID = 400
MAL_CARDS = (420, 421, 422, 423, 424)   # watching, plan to watch, completed, on hold, dropped
MAL_BARS = (430, 431, 432, 433)         # share bars of the first four cards
RELATED_ROWS = (800, 810, 820, 830, 840, 850)
SHOW_PLAY = 500
SHOW_FAVOURITE = 501
SHOW_RELATED = 502
SHOW_MAL = 503
SHOW_EPISODES = 510
SOURCES_LIST = 600
CONFIRM_YES = 700
CONFIRM_NO = 701
PROGRESS_BAR = 710
PROGRESS_CANCEL = 711
MENU_LIST = 720
PROMPT_BUTTON = 9000

ACTION_BACK = {9, 10, 92}        # parent dir, previous menu, back
ACTION_CONTEXT = {117}           # context menu / hold OK
ACTION_MOVE_RIGHT = 2
ACTION_MOVE_DOWN = 4
ACTION_MOVES = {1, 2, 3, 4, 5, 6}  # left, right, up, down, page up, page down

# Each task that adds a layout adds its entry here.
WINDOW_IDS = {
    "novaflix-prompt.xml": [PROMPT_BUTTON],
    "novaflix-login.xml": [9000],
    "novaflix-confirm.xml": [CONFIRM_YES, CONFIRM_NO],
    "novaflix-progress.xml": [PROGRESS_BAR, PROGRESS_CANCEL],
    "novaflix-sources.xml": [SOURCES_LIST],
    "novaflix-menu.xml": [MENU_LIST],
    "novaflix-show.xml": [SHOW_PLAY, SHOW_FAVOURITE, SHOW_RELATED, SHOW_MAL, SHOW_EPISODES],
    "novaflix-app.xml": [SIDEBAR, SIDEBAR_SETTINGS, HERO_PLAY, HERO_INFO, *HOME_ROWS, HOME_RETRY, GRID, *MAL_CARDS, *MAL_BARS,
                         *RELATED_ROWS],
}
