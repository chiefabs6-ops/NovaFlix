"""The service's player monitor (DEC-047): history, audio/subtitles, skip
button, Up next and playback errors for movies and episodes started from NovaFlix.

Only playback that the plugin announced through the hand-off window property
(IDs only, SEC-15) is tracked; anything else Kodi plays is ignored.
Slow work (title details, pre-search) runs in background threads so
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
from resources.lib.storage.watching import WatchHistory

HANDOFF_PROPERTY = "novaflix.playing"
OPEN_SHOW_PROPERTY = "novaflix.open_show"  # End episode: "tv:1396" / "movie:438631", the title page to return to
GUI_PROPERTY = "novaflix.gui"              # set while the NovaFlix window is open (gui/app.py)
SKIP_SHOW_S = 10
UPNEXT_SHOW_S = 20
STOP_WAIT_S = 10       # longest wait for Kodi's player to close before a transition gives up
AUDIO_LANGUAGES = ["eng", None]            # settings: English, Kodi default
AUDIO_LABELS = {"eng": 30212}


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


def _chapter():
    """(chapter now playing, chapter count, chapter name) from Kodi, or None when the file has no chapters."""
    try:
        current = int(xbmc.getInfoLabel("Player.Chapter") or 0)
        count = int(xbmc.getInfoLabel("Player.ChapterCount") or 0)
    except ValueError:
        return None
    if not current or not count:
        return None
    return current, count, xbmc.getInfoLabel("Player.ChapterName")


def _saved_episode(tmdb_id, season, episode):
    """The next episode's picture, title and plot from the saved season (the title page saved it); no
    network during playback. {} when the season is not saved."""
    from resources.lib import media
    from resources.lib.metadata.library import Library
    try:
        stub = media.Title(media_type=media.TV, tmdb_id=int(tmdb_id), title="")
        found = next((e for e in Library().cached_season_episodes(stub, season) or [] if e.number == episode), None)
    except Exception as exc:  # noqa: BLE001 - details are decoration; Up next still works
        log.warning(f"up next details: {type(exc).__name__}")
        return {}
    if found is None:
        return {}
    from resources.lib.gui import cards
    return {"art": found.still or "", "title": found.title or "", "plot": cards.cut(found.overview, 140)}


def _title_url(session, season, episode):
    from resources.lib.views import watch
    if session.media_type == "movie":
        return watch.watch_url(session.media_type, session.tmdb_id)
    return watch.watch_url(session.media_type, session.tmdb_id, season, episode)


def retry_url(session):
    """The source list again for what was playing (playback error)."""
    return _title_url(session, session.season, session.episode)


class PlaybackMonitor(xbmc.Player):
    def __init__(self, directory=None):
        super().__init__()
        self._dir = directory or paths.profile_dir()
        self.session = None
        self._prompts = []          # [(Prompt, close_at, skip interval or None)]
        self._threads = []
        self._transition = None     # [kind, title page, url, deadline]: waiting for the player to close

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
            session = Session(data["type"], data["id"], data.get("season"), data.get("episode"), data.get("resume_s"))
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
            xbmc.executebuiltin(f"PlayMedia({retry_url(session)})")

    # -- work --------------------------------------------------------------------

    def _background(self, target, *args):
        thread = threading.Thread(target=target, args=args, daemon=True)
        self._threads.append(thread)
        thread.start()

    def _prepare(self, session, payload):
        cleanup_after_start(self._dir, payload)
        try:
            choice = ui.addon().getSettingInt("audio_language")
            apply_streams(AUDIO_LANGUAGES[choice] if 0 <= choice < len(AUDIO_LANGUAGES) else None)
        except Exception as exc:
            log.warning(f"audio/subtitle choice skipped: {type(exc).__name__}: {exc}")
        try:
            duration = self.getTotalTime()
        except RuntimeError:
            return  # already stopped
        if 0 < session.resume_s < duration - 30:
            self.seekTime(session.resume_s)
            log.info(f"resumed at {session.resume_s} s")
        session.prepare(duration, [], self._next_ref(session))  # no skip-intro data for movies and shows yet
        log.info(f"tracking {session.media_type}:{session.tmdb_id} S{session.season}E{session.episode}: "
                 f"{int(duration)} s, up next {session.next_episode}, "
                 f"chapters {xbmc.getInfoLabel('Player.ChapterCount') or 'none'}")

    def _title(self, session):
        from resources.lib.metadata.library import Library
        return Library(self._dir).title(session.media_type, session.tmdb_id)

    def _next_ref(self, session):
        """(season, episode) after this one that has aired, or None (movies, last aired episode)."""
        if session.media_type == "movie":
            return None
        try:
            from resources.lib.metadata.library import Library
            return Library(self._dir).next_episode(self._title(session), session.season, session.episode)
        except Exception as exc:
            log.warning(f"no Up next: title details unavailable ({type(exc).__name__})")
            return None

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
        chapter = _chapter()
        if chapter:
            session.chapter(*chapter, position)
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
        WatchHistory(self._dir).save_position(session.media_type, session.tmdb_id, session.season, session.episode,
                                              session.position if position is None else position, session.duration)

    def _show(self, text, button, action, close_at, interval=None, button2=None, action2=None, details=None):
        from resources.lib.kodi.prompt import Prompt
        prompt = Prompt(text, button, action, button2, action2, details=details)
        prompt.show()
        self._prompts.append((prompt, close_at, interval))

    def _offer_skip(self, interval, now):
        label = ui.string(30216 if interval["type"] == "op" else 30217)
        self._show("", label, lambda: self.seekTime(interval["end"]), now + SKIP_SHOW_S, interval)

    def _offer_next(self, session, next_ref, now):
        from resources.lib.views import watch
        season, episode = next_ref

        def presearch():
            watch.presearch(self._title(session), season, episode,
                            cancelled=lambda: session.cancelled or xbmc.Monitor().abortRequested())

        self._background(presearch)  # DEC-030: list ready when Choose source is pressed
        url = _title_url(session, season, episode)
        self._show(ui.string(30407) % (ui.string(30404) % (season, episode)), ui.string(30219),
                   lambda: self._begin_transition("choose", session, url), now + UPNEXT_SHOW_S,
                   button2=ui.string(30316), action2=lambda: self._begin_transition("end", session),
                   details=_saved_episode(session.tmdb_id, season, episode))

    # -- transitions (Up next buttons) -------------------------------------------

    def _begin_transition(self, kind, session, url=None):
        """Stop the episode first; tick() runs the next step once the player has closed."""
        if self._transition is not None or session is not self.session:
            log.info(f"{kind}: ignored, a playback transition is already running")
            return
        page = f"{session.media_type}:{session.tmdb_id}"
        if kind == "end":
            session.cancelled = True  # the Up next pre-search stops
            # Set before stopping: the NovaFlix window under the video reads it as soon as the video closes.
            ui.set_window_property(OPEN_SHOW_PROPERTY, page)
        self._transition = [kind, page, url, None]  # deadline set by the next tick
        self._close_prompts()
        log.info(f"{kind}: stopping {page} S{session.season}E{session.episode}")
        self.stop()

    def _continue_transition(self, now):
        kind, page, url, deadline = self._transition
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
            self._return_to_show(page)

    def _playing(self):
        try:
            return self.isPlaying()
        except RuntimeError:
            return False

    def _return_to_show(self, page):
        """page: "tv:1396" / "movie:438631", the title page to open."""
        if ui.get_window_property(GUI_PROPERTY):
            return  # the NovaFlix window under the video opens the title page (gui/app.py, gui/title.py)
        ui.clear_window_property(OPEN_SHOW_PROPERTY)
        xbmc.executebuiltin(f"RunPlugin({router.build_url('launch', title=page)})")

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
