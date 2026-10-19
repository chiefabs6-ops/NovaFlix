# plugin.video.novaflix/resources/lib/gui/loader.py
"""Background loading for the NovaFlix windows (M12): jobs run in threads so Kodi's GUI
never waits on the network; results of a cancelled generation are dropped."""

import threading

import xbmc

from resources.lib.kodi import log


def _thread(fn):
    threading.Thread(target=fn, daemon=True).start()


def inline(fn):
    fn()


class Loader:
    def __init__(self, spawn=None):
        self._spawn = spawn or _thread
        self._generation = 0
        self._lock = threading.RLock()  # deliver() may start new loads (e.g. error -> back -> Home)

    def start(self, jobs, deliver):
        generation = self._generation
        for name, job in jobs.items():
            self._spawn(lambda name=name, job=job: self._run(generation, name, job, deliver))

    def _run(self, generation, name, job, deliver):
        try:
            result, error = job(), None
        except Exception as exc:  # delivered to the screen, which reports it
            result, error = None, exc
        with self._lock:
            if generation == self._generation:
                deliver(name, result, error)

    def cancel(self):
        with self._lock:
            self._generation += 1


class Ticker:
    """Calls fn about once per interval until stopped or Kodi closes."""

    def __init__(self, fn, interval=1.0):
        self._fn = fn
        self._interval = interval
        self._stopped = False

    def start(self):
        _thread(self._loop)

    def _loop(self):
        monitor = xbmc.Monitor()
        while not self._stopped and not monitor.waitForAbort(self._interval):
            try:
                self._fn()
            except Exception:
                log.exception("screen ticker failed")

    def stop(self):
        self._stopped = True


class PlaybackWatch:
    """ended() is True once, right after video playback stops."""

    def __init__(self):
        self._was_playing = False

    def ended(self):
        playing = xbmc.getCondVisibility("Player.HasVideo")
        ended = self._was_playing and not playing
        self._was_playing = playing
        return ended


def report(error, where):
    from resources.lib import router
    try:
        raise error
    except Exception as exc:  # report_error needs an active exception for tracebacks
        router.report_error(exc, where)
