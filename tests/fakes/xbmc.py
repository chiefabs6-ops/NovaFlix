"""Minimal fake of Kodi's xbmc module for tests."""

LOGDEBUG = 0
LOGINFO = 1
LOGWARNING = 2
LOGERROR = 3
LOGFATAL = 4

log_records = []


def log(msg, level=LOGDEBUG):
    log_records.append((level, msg))


class Monitor:
    # Tests set this to make the service loop exit after N waits.
    waits_before_abort = 0

    def __init__(self):
        self._waits = 0

    def abortRequested(self):
        return self._waits > Monitor.waits_before_abort

    def waitForAbort(self, timeout=0):
        self._waits += 1
        return self.abortRequested()


class Player:
    """Tests drive playback by setting the class-level state below."""
    playing = False
    time = 0.0
    total = 0.0
    seeks = []
    stops = 0
    stop_closes = True     # False: stop() is asked for but the player keeps playing

    def __init__(self):
        pass

    def isPlayingVideo(self):
        return Player.playing

    def isPlaying(self):
        return Player.playing

    def stop(self):
        Player.stops += 1
        if Player.stop_closes:
            Player.playing = False

    def getTime(self):
        if not Player.playing:
            raise RuntimeError("not playing")
        return Player.time

    def getTotalTime(self):
        if not Player.playing:
            raise RuntimeError("not playing")
        return Player.total

    def seekTime(self, seconds):
        Player.seeks.append(seconds)
        Player.time = seconds


# JSON-RPC: tests put method -> result (or callable(params) -> result) here.
jsonrpc_results = {}
jsonrpc_calls = []
info_labels = {}


def executeJSONRPC(payload):
    import json
    request = json.loads(payload)
    jsonrpc_calls.append((request["method"], request.get("params")))
    result = jsonrpc_results.get(request["method"], "OK")
    if callable(result):
        result = result(request.get("params"))
    return json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": result})


def getInfoLabel(name):
    return info_labels.get(name, "")


def executebuiltin(command, wait=False):
    builtins_executed.append(command)


builtins_executed = []
cond_visibility = {}


def getCondVisibility(condition):
    return bool(cond_visibility.get(condition, False))


def reset():
    log_records.clear()
    builtins_executed.clear()
    cond_visibility.clear()
    jsonrpc_results.clear()
    jsonrpc_calls.clear()
    info_labels.clear()
    Player.playing, Player.time, Player.total = False, 0.0, 0.0
    Player.seeks = []
    Player.stops, Player.stop_closes = 0, True
    Monitor.waits_before_abort = 0
