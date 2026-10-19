"""Minimal fake of Kodi's xbmcgui module for tests."""

NOTIFICATION_INFO = "info"
NOTIFICATION_WARNING = "warning"
NOTIFICATION_ERROR = "error"

notifications = []
# Answers returned by Dialog().yesno, consumed in order; default True.
yesno_answers = []
yesno_calls = []
ok_calls = []
# Answers returned by Dialog().select, consumed in order; default -1 (cancel).
select_answers = []
select_calls = []
# Answers returned by Dialog().input, consumed in order; default "".
input_answers = []


class InfoTagVideo:
    """Records every setter call: tag.values["Title"] == "..."."""

    def __init__(self):
        self.values = {}

    def __getattr__(self, name):
        if name.startswith("set"):
            return lambda value, *rest: self.values.__setitem__(name[3:], value)
        raise AttributeError(name)


class ListItem:
    def __init__(self, label="", label2="", path="", offscreen=False):
        self.label = label
        self.label2 = label2
        self.path = path
        self.art = {}
        self.properties = {}
        self.tag = InfoTagVideo()
        self.context_menu = []

    def getVideoInfoTag(self):
        return self.tag

    def addContextMenuItems(self, items, replaceItems=False):
        self.context_menu.extend(items)

    def getLabel(self):
        return self.label

    def getLabel2(self):
        return self.label2

    def setLabel2(self, label2):
        self.label2 = label2

    def setArt(self, art):
        self.art.update(art)

    def setProperty(self, key, value):
        self.properties[key] = value


window_properties = {}


class Window:
    def __init__(self, window_id=10000):
        pass

    def setProperty(self, key, value):
        window_properties[key] = value

    def getProperty(self, key):
        return window_properties.get(key, "")

    def clearProperty(self, key):
        window_properties.pop(key, None)


class Dialog:
    def yesno(self, heading, message, nolabel="", yeslabel="", autoclose=0, defaultbutton=None):
        yesno_calls.append((heading, message))
        return yesno_answers.pop(0) if yesno_answers else True

    def ok(self, heading, message):
        ok_calls.append((heading, message))
        return True

    def select(self, heading, options, autoclose=0, preselect=-1, useDetails=False):
        shown = [o if isinstance(o, str) else (o.label, o.label2) for o in options]
        select_calls.append((heading, shown))
        answer = select_answers.pop(0) if select_answers else -1
        return len(shown) - 1 if answer == "last" else answer

    def input(self, heading, defaultt="", type=0, option=0, autoclose=0):
        return input_answers.pop(0) if input_answers else ""

    def notification(self, heading, message, icon=NOTIFICATION_INFO, time=5000, sound=True):
        notifications.append((heading, message, icon))


class DialogProgress:
    cancel_after_checks = None  # tests: report cancel after N iscanceled() calls

    def __init__(self):
        self.checks = 0
        progress_dialogs.append(self)
        self.closed = False

    def create(self, heading, message=""):
        self.heading = heading

    def update(self, percent, message=""):
        self.last_update = (percent, message)

    def iscanceled(self):
        self.checks += 1
        limit = DialogProgress.cancel_after_checks
        return limit is not None and self.checks >= limit

    def close(self):
        self.closed = True


progress_dialogs = []


modal_scripts = []   # callables run by doModal(), in order: lambda window: window.onClick(700)


class Action:
    def __init__(self, action_id):
        self._id = action_id

    def getId(self):
        return self._id


class Control:
    """List/progress/button/label stand-in, created on first getControl(id)."""

    def __init__(self, control_id):
        self.id = control_id
        self.items = []
        self.selected = 0
        self.percent = 0
        self.label = ""
        self.visible = True

    def addItems(self, items):
        # Like Kodi: ControlList.addItems re-binds the whole container (GUI_MSG_LABEL_BIND),
        # which selects the first item again.
        self.items.extend(items)
        self.selected = 0

    def addItem(self, item):
        self.items.append(item)

    def reset(self):
        self.items.clear()
        self.selected = 0

    def size(self):
        return len(self.items)

    def getSelectedPosition(self):
        return self.selected if self.items else -1

    def selectItem(self, index):
        self.selected = index

    def getSelectedItem(self):
        return self.items[self.selected] if self.items else None

    def getListItem(self, index):
        return self.items[index]

    def setPercent(self, percent):
        self.percent = percent

    def getPercent(self):
        return self.percent

    def setLabel(self, label):
        self.label = label

    def setVisible(self, visible):
        self.visible = visible

    def setEnabled(self, enabled):
        pass


class WindowXMLDialog:
    """Records custom windows in `xml_dialogs`. doModal() calls onInit(), then the next
    callable from `modal_scripts` (the simulated user), so tests can drive dialogs."""

    def __init__(self, xml_file, path, skin="Default", resolution="720p", *args, **kwargs):
        self.xml_file = xml_file
        self.properties = {}
        self.controls = {}
        self.focus_id = None
        self.shown = False
        self.closed = False
        xml_dialogs.append(self)

    def setProperty(self, key, value):
        self.properties[key] = value

    def getProperty(self, key):
        return self.properties.get(key, "")

    def clearProperty(self, key):
        self.properties.pop(key, None)

    def getControl(self, control_id):
        return self.controls.setdefault(control_id, Control(control_id))

    def setFocusId(self, control_id):
        self.focus_id = control_id

    def getFocusId(self):
        return self.focus_id

    def show(self):
        self.shown = True
        if hasattr(self, "onInit"):
            self.onInit()

    def doModal(self):
        self.shown = True
        if hasattr(self, "onInit"):
            self.onInit()
        if modal_scripts:
            modal_scripts.pop(0)(self)

    def close(self):
        self.closed = True


class WindowXML(WindowXMLDialog):
    pass


xml_dialogs = []


def reset():
    notifications.clear()
    yesno_answers.clear()
    yesno_calls.clear()
    input_answers.clear()
    ok_calls.clear()
    select_answers.clear()
    select_calls.clear()
    progress_dialogs.clear()
    xml_dialogs.clear()
    modal_scripts.clear()
    window_properties.clear()
    DialogProgress.cancel_after_checks = None
