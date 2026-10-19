"""Developer helper: drive the local Windows Kodi for manual-test automation.

Talks to Kodi's JSON-RPC TCP port (this PC unless KODI_HOST is set).
Not packaged with the add-on.

Usage (from project root, Kodi installed):
  .venv\\Scripts\\python tools\\dev_kodi.py install      # copy add-on, restart Kodi, enable it
  .venv\\Scripts\\python tools\\dev_kodi.py open [path]  # open plugin://plugin.video.novaflix/<path>
  .venv\\Scripts\\python tools\\dev_kodi.py shot NAME    # screenshot into dist/screens/
  .venv\\Scripts\\python tools\\dev_kodi.py log          # NovaFlix + error lines from kodi.log
  .venv\\Scripts\\python tools\\dev_kodi.py measure [rounds] [path ...]  # menu open times

KODI_HOST=192.168.1.86 drives the Fire TV stick instead (needs "Allow remote control
from applications on other systems" in Kodi; install/shot/log are PC-only).
"""

import glob
import json
import os
import shutil
import socket
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ADDON_ID = "plugin.video.novaflix"
LAUNCHER_ID = "script.novaflix"
KODI_EXE = r"C:\Program Files\Kodi\kodi.exe"
KODI_DATA = os.path.join(os.environ.get("APPDATA", ""), "Kodi")
SCREEN_DIR = os.path.join(ROOT, "dist", "screens")
KODI_HOST = os.environ.get("KODI_HOST", "127.0.0.1")
MEASURE_PATHS = ["", "continue", "airing", "trending", "popular", "genres", "favourites", "show?id=154587"]


def rpc(method, params=None, timeout=10):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    with socket.create_connection((KODI_HOST, 9090), timeout=timeout) as sock:
        sock.sendall(json.dumps(payload).encode())
        buf = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
            try:
                # Kodi also pushes notifications on this socket; keep our reply only.
                for line in _split_json(buf.decode("utf-8", "replace")):
                    msg = json.loads(line)
                    if msg.get("id") == 1:
                        return msg
            except ValueError:
                continue
    raise RuntimeError("no JSON-RPC reply")


def _split_json(text):
    depth, start, out = 0, 0, []
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                out.append(text[start:i + 1])
    if depth:
        raise ValueError("incomplete")
    return out


def wait_for_kodi(seconds=60):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            if rpc("JSONRPC.Ping").get("result") == "pong":
                return True
        except OSError:
            pass
        time.sleep(1)
    return False


def kodi_running():
    try:
        return rpc("JSONRPC.Ping", timeout=2).get("result") == "pong"
    except OSError:
        return False


def stop_kodi():
    if kodi_running():
        rpc("Application.Quit")
        for _ in range(30):
            time.sleep(1)
            if not kodi_running():
                break
        time.sleep(2)


def install():
    stop_kodi()
    for addon_id in (LAUNCHER_ID, ADDON_ID):
        dest = os.path.join(KODI_DATA, "addons", addon_id)
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        shutil.copytree(os.path.join(ROOT, addon_id), dest,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    subprocess.Popen([KODI_EXE])
    if not wait_for_kodi():
        sys.exit("Kodi did not start")
    time.sleep(5)
    for addon_id in (LAUNCHER_ID, ADDON_ID):
        print(rpc("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": True}))
        print(rpc("Addons.GetAddonDetails", {"addonid": addon_id, "properties": ["version", "enabled"]}))


def open_path(path=""):
    url = f"plugin://{ADDON_ID}/{path}"
    print(rpc("GUI.ActivateWindow", {"window": "videos", "parameters": [url, "return"]}))


def shot(name):
    os.makedirs(SCREEN_DIR, exist_ok=True)
    before = set(glob.glob(os.path.join(SCREEN_DIR, "*.png")))
    rpc("Settings.SetSettingValue", {"setting": "debug.screenshotpath", "value": SCREEN_DIR + os.sep})
    rpc("Input.ExecuteAction", {"action": "screenshot"})
    for _ in range(20):
        time.sleep(0.5)
        new = set(glob.glob(os.path.join(SCREEN_DIR, "*.png"))) - before
        if new:
            target = os.path.join(SCREEN_DIR, f"{name}.png")
            if os.path.exists(target):
                os.remove(target)
            os.replace(new.pop(), target)
            print(target)
            return
    sys.exit("screenshot not written")


def _loaded(url):
    labels = rpc("XBMC.GetInfoLabels", {"labels": ["Container.FolderPath"]})["result"]
    busy = rpc("XBMC.GetInfoBooleans", {"booleans": ["Container.IsUpdating"]})["result"]
    return labels["Container.FolderPath"].rstrip("/") == url.rstrip("/") and not busy["Container.IsUpdating"]


def time_open(path, limit=60):
    """Seconds from asking Kodi to open a plugin path until its list is shown."""
    rpc("GUI.ActivateWindow", {"window": "home"})
    time.sleep(1.5)
    url = f"plugin://{ADDON_ID}/{path}"
    started = time.monotonic()
    rpc("GUI.ActivateWindow", {"window": "videos", "parameters": [url, "return"]})
    while time.monotonic() - started < limit:
        if _loaded(url):
            return time.monotonic() - started
        # Each poll is a new JSON-RPC connection; fast polling overloaded the Fire TV stick.
        time.sleep(0.05 if KODI_HOST == "127.0.0.1" else 0.5)
    return None


def measure(rounds=3, paths=None):
    for path in paths or MEASURE_PATHS:
        times = [time_open(path) for _ in range(rounds)]
        shown = ["timeout" if t is None else f"{t:.2f}s" for t in times]
        print(f"/{path:<18} first {shown[0]:>8}   then {' '.join(shown[1:])}")
    rpc("GUI.ActivateWindow", {"window": "home"})


def log():
    with open(os.path.join(KODI_DATA, "kodi.log"), encoding="utf-8", errors="replace") as f:
        for line in f:
            if ADDON_ID in line or " error <" in line.lower():
                print(line.rstrip())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "install":
        install()
    elif cmd == "open":
        open_path(sys.argv[2] if len(sys.argv) > 2 else "")
    elif cmd == "shot":
        shot(sys.argv[2])
    elif cmd == "log":
        log()
    elif cmd == "measure":
        measure(int(sys.argv[2]) if len(sys.argv) > 2 else 3, sys.argv[3:] or None)
    elif cmd == "rpc":
        print(json.dumps(rpc(sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else None), indent=1))
    else:
        sys.exit(__doc__)
