"""The service's player monitor (DEC-047): history, audio/subtitles, skip
button, Up next and playback errors for episodes started from NovaFlix.

Only playback that the plugin announced through the hand-off window property
(IDs only, SEC-15) is tracked; anything else Kodi plays is ignored.
Slow work (AniSkip, show details, pre-search) runs in background threads so
Kodi's player callbacks never wait on the network.

Up next buttons (Choose source, End episode) never start anything while the episode
still plays: they stop it, and tick() runs the next step once Kodi's player has closed.
One transition at a time; further presses are ignored until it has run.
"""

import json
import threading
import time

import xbmc

from resources.lib import router
from resources.lib.kodi import log, paths, player, ui
from resources.lib.playback import streams
from resources.lib.playback.session import Session
from resources.lib.storage.history import History

HANDOFF_PROPERTY = "novaflix.playing"
OPEN_SHOW_PROPERTY = "novaflix.open_show"  # End episode: anilist_id of the show page to return to
GUI_PROPERTY = "novaflix.gui"              # set while the NovaFlix window is open (gui/app.py)
SKIP_SHOW_S = 10
UPNEXT_SHOW_S = 20
STOP_WAIT_S = 10       # longest wait for Kodi's player to close before a transition gives up
AUDIO_LANGUAGES = ["eng", "jpn", None]     # settings: English, Japanese, Kodi default
AUDIO_LABELS = {"eng": 30212, "jpn": 30213}


def cleanup_after_start(directory, payload_json):
    """Playback started: remove the torrent NovaFlix added for it, unless kept (DEC-019)."""
    from resources.lib.debrid import service
    from resources.lib.storage.added import AddedTorrents

    try:
        payload = json.loads(payload_json or "{}")
    except ValueError:
        return
    torrent_id = payload.get("cleanup_torrent")
    added = AddedTorrents(directory)
    if not torrent_id or not added.is_ours(torrent_id) or added.is_kept(torrent_id):
        return
    try:
        client = service.client(directory)
        if client is None:
            return
        client.delete_torrent(torrent_id)
        added.forget(torrent_id)
        log.info("removed torrent added for this playback")
    except Exception as exc:
        # Logged only: a cleanup failure is never a playback error (DEC-019).
        log.warning(f"torrent cleanup failed: {type(exc).__name__}: {exc}")


def apply_streams(language):
    """DEC-027 preferred audio, then DEC-026 Signs & Songs subtitles with English audio."""
    if not language:
        return
    data = player.streams() or {}
    audio = data.get("audiostreams") or []
    current = (data.get("currentaudiostream") or {}).get("index")
    log.info(f"audio tracks: {[(s.get('index'), s.get('language'), s.get('name')) for s in audio]}, "
             f"playing {current}")
    chosen = streams.pick_audio(audio, language, current)
    if chosen is not None:
        player.set_audio(chosen)
        current = chosen
    elif not streams.audio_is(audio, current, language):
        # DEC-027 keeps Kodi's track; say so, so another source can be chosen at once.
        ui.notify("NovaFlix", ui.string(30228) % ui.string(AUDIO_LABELS[language]))
    if not streams.audio_is(audio, current, "eng"):
        return  # not English audio: Kodi's subtitle choice stays
    mode, index = streams.pick_subtitle(data.get("subtitles") or [])
    if mode == "on":
        player.set_subtitle(index)
    else:
        player.subtitles_off()


def play_url(anilist_id, episode):
    return router.build_url("play", id=anilist_id, ep=episode)


class PlaybackMonitor(xbmc.Player):
    def __init__(self, directory=None):
        super().__init__()
        self._dir = directory or paths.profile_dir()
        self.session = None
        self._prompts = []          # [(Prompt, close_at, skip interval or None)]
        self._threads = []
        self._transition = None     # [kind, anilist_id, url, deadline]: waiting for the player to close

    # -- Kodi callbacks ----------------------------------------------------------

    def onAVStarted(self):
        payload = ui.get_window_property(HANDOFF_PROPERTY)
        if self.session is not None:
            self._finish(ended=False)  # switched without a stop event
        if not payload:
            return
        ui.clear_window_property(HANDOFF_PROPERTY)
        try:
            data = json.loads(payload)
            session = Session(data["anilist_id"], data["episode"], data.get("mal_id"), data.get("resume_s"))
        except (ValueError, KeyError, TypeError):
            log.warning("ignoring unreadable playback hand-off")
            return
        self.session = session
        self._background(self._prepare, session, payload)

    def onPlayBackStopped(self):
        self._finish(ended=False)

    def onPlayBackEnded(self):
        self._finish(ended=True)

    def onPlayBackError(self):
        session = self._finish(ended=False)
        if session and ui.confirm("NovaFlix", ui.string(30220)):
            xbmc.executebuiltin(f"PlayMedia({play_url(session.anilist_id, session.episode)})")

    # -- work --------------------------------------------------------------------

    def _background(self, target, *args):
        thread = threading.Thread(target=target, args=args, daemon=True)
        self._threads.append(thread)
        thread.start()

    def _prepare(self, session, payload):
        cleanup_after_start(self._dir, payload)
        try:
            apply_streams(AUDIO_LANGUAGES[ui.addon().getSettingInt("audio_language")])
        except Exception as exc:
            log.warning(f"audio/subtitle choice skipped: {type(exc).__name__}: {exc}")
        try:
            duration = self.getTotalTime()
        except RuntimeError:
            return  # already stopped
        if 0 < session.resume_s < duration - 30:
            self.seekTime(session.resume_s)
            log.info(f"resumed at {session.resume_s} s")
        from resources.lib.metadata import aniskip
        skips = aniskip.skip_times(self._dir, session.mal_id, session.episode, duration)
        session.prepare(duration, skips, self._has_next(session))
        log.info(f"tracking {session.anilist_id} ep {session.episode}: {int(duration)} s, "
                 f"skips {[s['type'] for s in skips]}, up next {session.next_episode}")

    def _has_next(self, session):
        try:
            from resources.lib.metadata.catalog import Catalog
            show = Catalog(self._dir).show(session.anilist_id)
        except Exception as exc:
            log.warning(f"no Up next: show details unavailable ({type(exc).__name__})")
            return False
        if show.is_movie:
            return False
        aired = show.aired_episodes
        return aired is None or session.episode + 1 <= aired

    def tick(self, now=None):
        """Called about once a second by the service loop."""
        now = time.monotonic() if now is None else now
        if self._transition is not None:
            self._continue_transition(now)
            return
        session = self.session
        if session is None:
            return
        try:
            if not self.isPlayingVideo():
                return
            position = self.getTime()
        except RuntimeError:
            return
        for event in session.tick(position, now):
            if event[0] == "save":
                self._save(session)
            elif event[0] == "skip":
                self._offer_skip(event[1], now)
            elif event[0] == "upnext":
                self._offer_next(session, event[1], now)
        self._expire_prompts(session, position, now)

    def _save(self, session, position=None):
        if not session.duration:
            return
        watched = History(self._dir).save_position(session.anilist_id, session.episode, session.mal_id,
                                                   session.position if position is None else position,
                                                   session.duration)
        if watched and session.mal_id and not session.mal_queued:
            from resources.lib.myanimelist import sync
            session.mal_queued = True
            sync.queue(self._dir, session.mal_id, "watched", session.episode)

    def _show(self, text, button, action, close_at, interval=None, button2=None, action2=None):
        from resources.lib.kodi.prompt import Prompt
        prompt = Prompt(text, button, action, button2, action2)
        prompt.show()
        self._prompts.append((prompt, close_at, interval))

    def _offer_skip(self, interval, now):
        label = ui.string(30216 if interval["type"] == "op" else 30217)
        self._show("", label, lambda: self.seekTime(interval["end"]), now + SKIP_SHOW_S, interval)

    def _offer_next(self, session, episode, now):
        from resources.lib.metadata.catalog import Catalog
        from resources.lib.views import sources

        def presearch():
            sources.presearch(Catalog(self._dir).show(session.anilist_id), episode,
                              cancelled=lambda: session.cancelled or xbmc.Monitor().abortRequested())

        self._background(presearch)  # DEC-030: list ready when OK is pressed
        url = play_url(session.anilist_id, episode)
        self._show(ui.string(30218) % episode, ui.string(30219),
                   lambda: self._begin_transition("choose", session, url), now + UPNEXT_SHOW_S,
                   button2=ui.string(30316), action2=lambda: self._begin_transition("end", session))

    # -- transitions (Up next buttons) -------------------------------------------

    def _begin_transition(self, kind, session, url=None):
        """Stop the episode first; tick() runs the next step once the player has closed."""
        if self._transition is not None or session is not self.session:
            log.info(f"{kind}: ignored, a playback transition is already running")
            return
        if kind == "end":
            session.cancelled = True  # the Up next pre-search stops
            # Set before stopping: the NovaFlix window under the video reads it as soon as the video closes.
            ui.set_window_property(OPEN_SHOW_PROPERTY, str(session.anilist_id))
        self._transition = [kind, session.anilist_id, url, None]  # deadline set by the next tick
        self._close_prompts()
        log.info(f"{kind}: stopping {session.anilist_id} ep {session.episode}")
        self.stop()

    def _continue_transition(self, now):
        kind, anilist_id, url, deadline = self._transition
        if deadline is None:
            deadline = self._transition[3] = now + STOP_WAIT_S
        if self._playing():
            if now < deadline:
                return
            log.warning(f"{kind}: playback did not stop within {STOP_WAIT_S} s; nothing started")
            self._transition = None
            ui.clear_window_property(OPEN_SHOW_PROPERTY)
            ui.notify("NovaFlix", ui.string(30317), error=True)
            return
        self._transition = None
        if self.session is not None:
            self._finish(ended=False)  # stopped without a stop event: save and clean up now
        if kind == "choose":
            xbmc.executebuiltin(f"PlayMedia({url})")
        else:
            self._return_to_show(anilist_id)

    def _playing(self):
        try:
            return self.isPlaying()
        except RuntimeError:
            return False

    def _return_to_show(self, anilist_id):
        if ui.get_window_property(GUI_PROPERTY):
            return  # the NovaFlix window under the video opens the show page (gui/app.py, gui/show.py)
        ui.clear_window_property(OPEN_SHOW_PROPERTY)
        if ui.styled():
            xbmc.executebuiltin(f"RunPlugin({router.build_url('launch', show=anilist_id)})")
        else:
            xbmc.executebuiltin(f"ActivateWindow(Videos,{router.build_url('show', id=anilist_id)},return)")

    def _expire_prompts(self, session, position, now):
        keep = []
        for prompt, close_at, interval in self._prompts:
            if not prompt.is_open:
                continue
            if now >= close_at or (interval and not session.skip_over(interval, position)):
                prompt.close()
                continue
            keep.append((prompt, close_at, interval))
        self._prompts = keep

    def _close_prompts(self):
        for prompt, _, _ in self._prompts:
            prompt.close()
        self._prompts = []

    def _finish(self, ended):
        session, self.session = self.session, None
        self._close_prompts()
        if session is None:
            return None
        self._save(session, session.duration if ended else None)
        if player.folder_path().startswith(router.BASE_URL):
            ui.refresh()  # watched marks / resume points in the open list
        return session
