"""Kodi JSON-RPC calls for the playing video's audio/subtitle streams.

Only changes the current player's streams; Kodi's global audio and subtitle
settings are never touched (DEC-027).
"""

import json

import xbmc

from resources.lib.kodi import log


def _rpc(method, params=None):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    answer = json.loads(xbmc.executeJSONRPC(json.dumps(payload)) or "{}")
    if "error" in answer:
        raise RuntimeError(f"{method}: {answer['error'].get('message')}")
    return answer.get("result")


def _video_player_id():
    for player in _rpc("Player.GetActivePlayers") or []:
        if player.get("type") == "video":
            return player.get("playerid")
    return None


def streams():
    """{"audiostreams": [...], "currentaudiostream": {...}, "subtitles": [...]} or None."""
    player_id = _video_player_id()
    if player_id is None:
        return None
    return _rpc("Player.GetProperties", {"playerid": player_id, "properties": [
        "audiostreams", "currentaudiostream", "subtitles", "currentsubtitle", "subtitleenabled"]})


def set_audio(index):
    _rpc("Player.SetAudioStream", {"playerid": _video_player_id(), "stream": int(index)})
    log.info(f"audio stream {index} selected")


def set_subtitle(index):
    player_id = _video_player_id()
    _rpc("Player.SetSubtitle", {"playerid": player_id, "subtitle": int(index), "enable": True})
    log.info(f"subtitle stream {index} enabled")


def subtitles_off():
    _rpc("Player.SetSubtitle", {"playerid": _video_player_id(), "subtitle": "off"})


def folder_path():
    return xbmc.getInfoLabel("Container.FolderPath")
