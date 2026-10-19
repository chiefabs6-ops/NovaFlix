"""What the player monitor should do while one NovaFlix episode plays.

Pure timing logic (no Kodi calls) so it can be tested with fake clocks:
- save the position every SAVE_EVERY_S (DEC-028; crash loses <= 30 s),
- offer Skip intro / Skip ending inside AniSkip intervals (DEC-041),
- offer Up next at the ending's start, or UPNEXT_FALLBACK_S before the end (DEC-030);
  when Up next uses the ending's start it replaces the Skip ending button.
"""

SAVE_EVERY_S = 30
UPNEXT_FALLBACK_S = 90
MIN_UPNEXT_DURATION_S = 5 * 60    # no Up next on very short clips
SKIP_LEAD_S = 3                   # don't offer a skip in its last seconds


class Session:
    def __init__(self, anilist_id, episode, mal_id=None, resume_s=0):
        self.anilist_id = int(anilist_id)
        self.episode = int(episode)
        self.mal_id = int(mal_id) if mal_id else None
        self.resume_s = int(resume_s or 0)
        self.mal_queued = False      # MyAnimeList told once per playback (M13)
        self.duration = 0.0
        self.position = 0.0
        self.skips = []              # [{type, start, end}]
        self.next_episode = None     # set when an Up next prompt should be offered
        self.cancelled = False       # End episode pressed: background work for this episode stops
        self.upnext_at = None
        self._saved_at = None
        self._offered = set()

    def prepare(self, duration, skips, has_next):
        """Called once the duration is known (after onAVStarted)."""
        self.duration = float(duration or 0)
        self.skips = list(skips or [])
        if has_next and self.duration >= MIN_UPNEXT_DURATION_S:
            self.next_episode = self.episode + 1
            ending = next((s for s in self.skips if s["type"] == "ed"), None)
            if ending and ending["start"] >= self.duration / 2:
                self.upnext_at = ending["start"]
                # Up next takes the ending's place on screen; one prompt at a time.
                self.skips = [s for s in self.skips if s is not ending]
            else:
                self.upnext_at = self.duration - UPNEXT_FALLBACK_S

    def tick(self, position, now):
        """Events due at this moment: ("save",), ("skip", interval), ("upnext", episode)."""
        self.position = float(position)
        events = []
        if self._saved_at is None:
            self._saved_at = now
        elif now - self._saved_at >= SAVE_EVERY_S:
            self._saved_at = now
            events.append(("save",))
        for interval in self.skips:
            key = ("skip", interval["type"])
            if key not in self._offered and interval["start"] <= position < interval["end"] - SKIP_LEAD_S:
                self._offered.add(key)
                events.append(("skip", interval))
        if self.upnext_at is not None and "upnext" not in self._offered and position >= self.upnext_at:
            self._offered.add("upnext")
            events.append(("upnext", self.next_episode))
        return events

    def skip_over(self, interval, position):
        """True while the skip prompt for this interval is still useful."""
        return interval["start"] <= position < interval["end"] - SKIP_LEAD_S
