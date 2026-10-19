"""Turns the owner's chosen source into a playable URL (DEC-019, DEC-020).

Hash sources: reuse a matching torrent already in the account, else
addMagnet -> wait for the file list -> select only the episode file -> info.
  downloaded                        -> unrestrict -> URL
  queued/downloading/...            -> NotReady (the view asks to download)
  magnet_error/error/virus/dead     -> delete our torrent -> BadSource
Account sources: the file is already downloaded -> unrestrict.

Never switches to another source on its own (DEC-004).
"""

import re
import time

from resources.lib import errors
from resources.lib.kodi import log
from resources.lib.sources import matcher

READY = "downloaded"
IN_PROGRESS = {"queued", "downloading", "compressing", "uploading"}
BROKEN = {"magnet_error", "error", "virus", "dead"}
_BROKEN_TEXT = {"magnet_error": "could not read this torrent", "error": "could not download this torrent",
                "virus": "flagged this torrent as unsafe", "dead": "found nobody sharing this torrent"}


def _broken(rd, status):
    return BadSource(f"{_svc(rd)} {_BROKEN_TEXT.get(status, 'cannot use this torrent')}")
CONVERSION_TIMEOUT_S = 30
CONVERSION_POLL_S = 2

_sleep = time.sleep
_clock = time.monotonic


class BadSource(errors.NovaFlixError):
    """This source cannot be played; the owner picks another."""


BLOCKED_CODES = {35}  # infringing_file


def _blocked(exc):
    """RD refuses some torrents with HTTP 451 / error_code 35 (seen live 2026-10-11 on addMagnet)."""
    code = (exc.payload or {}).get("error_code") if isinstance(exc.payload, dict) else None
    return exc.status == 451 or code in BLOCKED_CODES


class NotReady(errors.NovaFlixError):
    def __init__(self, torrent_id, info):
        super().__init__("not downloaded on Real-Debrid yet")
        self.torrent_id = torrent_id
        self.info = info


class AmbiguousFile(errors.NovaFlixError):
    """More than one file could be the episode: the owner chooses (files = [(id, path)])."""

    def __init__(self, torrent_id, files):
        super().__init__("episode file is ambiguous")
        self.torrent_id = torrent_id
        self.files = files


def _basename(path):
    return re.split(r"[\\/]", path or "")[-1].lower()


def pick_file(files, candidate, wanted):
    """RD file id for the episode, or raise AmbiguousFile/BadSource."""
    titles = getattr(wanted, "titles", None) if wanted is not None else None
    videos = [f for f in files if matcher.is_video(f.get("path", "")) and not matcher.parse(f["path"], titles).is_extra]
    if not videos:
        raise BadSource("no video files in this torrent")
    if candidate.file_name:
        target = _basename(candidate.file_name)
        exact = [f for f in videos if _basename(f["path"]) == target]
        if len(exact) == 1:
            return exact[0]["id"]
    if len(videos) == 1:
        return videos[0]["id"]
    if wanted.is_movie:
        return max(videos, key=lambda f: f.get("bytes") or 0)["id"]
    hits = [f for f in videos
            if matcher.matches(matcher.parse(f["path"], titles), wanted.number, wanted.absolute, wanted.tvdb)]
    if len(hits) == 1:
        return hits[0]["id"]
    if candidate.file_idx is not None:
        # Torrentio's fileIdx is the 0-based torrent order; RD ids are 1-based in the same order (unverified).
        guess = [f for f in videos if f["id"] == candidate.file_idx + 1]
        if len(guess) == 1 and not hits:
            return guess[0]["id"]
    raise AmbiguousFile(None, [(f["id"], f["path"].lstrip("/")) for f in (hits or videos)])


def _svc(rd):
    """Name of the playback service for messages ("TorBox" / "Real-Debrid")."""
    return getattr(rd, "name", "Real-Debrid")


def link_for_file(info, file_id):
    """links[] follow the selected files in id order."""
    selected = sorted(f["id"] for f in info.get("files") or [] if f.get("selected"))
    links = info.get("links") or []
    if file_id not in selected or selected.index(file_id) >= len(links):
        raise BadSource("no stream link for this file")
    return links[selected.index(file_id)]


def unrestrict(rd, link):
    try:
        data = rd.unrestrict(link)
    except errors.AccountError as exc:
        if exc.code == 35:
            raise BadSource(f"{_svc(rd)} blocked this file") from None
        raise
    except errors.HttpError as exc:
        code = (exc.payload or {}).get("error_code") if isinstance(exc.payload, dict) else None
        if _blocked(exc):
            raise BadSource(f"{_svc(rd)} has blocked this file") from None
        if code in (16, 17, 18, 19, 24):
            raise BadSource(f"{_svc(rd)} cannot stream this file (code {code})") from None
        raise
    url = data.get("download")
    if not url:
        raise BadSource(f"{_svc(rd)} returned no stream URL")
    return url, data.get("filename")


def _wait_for_files(rd, torrent_id):
    deadline = _clock() + CONVERSION_TIMEOUT_S
    while True:
        info = rd.torrent_info(torrent_id)
        status = info.get("status")
        if status in BROKEN:
            raise _broken(rd, status)
        if status != "magnet_conversion":
            return info
        if _clock() > deadline:
            raise BadSource(f"{_svc(rd)} could not read this torrent (no peers)")
        _sleep(CONVERSION_POLL_S)


def _existing(rd, info_hash):
    for t in rd.torrents():
        if (t.get("hash") or "").lower() == info_hash and t.get("status") not in BROKEN:
            return t["id"]
    return None


class Resolver:
    def __init__(self, rd, added_store):
        """added_store: records torrents this add-on added (only those may be auto-removed, DEC-019)."""
        self.rd = rd
        self.added = added_store
        self.torrent_id = None  # the torrent used by the last resolve (hash sources)

    def _discard(self, torrent_id):
        if torrent_id and self.added.is_ours(torrent_id):
            try:
                self.rd.delete_torrent(torrent_id)
            except errors.NovaFlixError as exc:
                log.warning(f"could not remove torrent: {exc}")
            self.added.forget(torrent_id)

    def resolve(self, candidate, wanted, chosen_file_id=None, torrent_id=None):
        """Stream URL for the candidate. May raise NotReady, AmbiguousFile, BadSource."""
        if candidate.origin == "rdcloud":
            info = self.rd.torrent_info(candidate.rd_torrent_id)
            return unrestrict(self.rd, link_for_file(info, candidate.rd_file_id))

        if not torrent_id:
            torrent_id = _existing(self.rd, candidate.info_hash)
        if not torrent_id:
            try:
                torrent_id = self.rd.add_magnet(f"magnet:?xt=urn:btih:{candidate.info_hash}")
            except errors.HttpError as exc:
                if _blocked(exc):
                    raise BadSource(f"{_svc(self.rd)} has blocked this torrent") from None
                raise
            if not torrent_id:
                raise BadSource(f"{_svc(self.rd)} did not accept the torrent")
            self.added.remember(torrent_id, candidate.info_hash)
        self.torrent_id = torrent_id
        try:
            info = _wait_for_files(self.rd, torrent_id)
            if info.get("status") == "waiting_files_selection":
                try:
                    file_id = chosen_file_id or pick_file(info.get("files") or [], candidate, wanted)
                except AmbiguousFile as exc:
                    exc.torrent_id = torrent_id
                    raise
                try:
                    self.rd.select_files(torrent_id, [file_id])
                except errors.HttpError as exc:
                    if _blocked(exc):
                        raise BadSource(f"{_svc(self.rd)} has blocked this torrent") from None
                    raise
                info = self.rd.torrent_info(torrent_id)
            else:
                file_id = chosen_file_id or self._file_in_existing(info, candidate, wanted)
            status = info.get("status")
            if status in BROKEN:
                raise _broken(self.rd, status)
            if status != READY:
                raise NotReady(torrent_id, info)
            return unrestrict(self.rd, link_for_file(info, file_id))
        except BadSource:
            self._discard(torrent_id)
            raise

    def _file_in_existing(self, info, candidate, wanted):
        selected = [f for f in info.get("files") or [] if f.get("selected")]
        try:
            return pick_file(selected, candidate, wanted)
        except AmbiguousFile as exc:
            exc.torrent_id = info.get("id")
            raise

    def progress(self, torrent_id):
        """(status, percent, speed_bytes, seeders) for the download dialog."""
        info = self.rd.torrent_info(torrent_id)
        status = info.get("status")
        if status in BROKEN:
            self._discard(torrent_id)
            raise _broken(self.rd, status)
        return status, info.get("progress") or 0, info.get("speed"), info.get("seeders"), info

    def finish(self, torrent_id, candidate, wanted, info):
        file_id = self._file_in_existing(info, candidate, wanted)
        return unrestrict(self.rd, link_for_file(info, file_id))

    def remove(self, torrent_id):
        self._discard(torrent_id)

    def keep(self, torrent_id):
        self.added.keep(torrent_id)


