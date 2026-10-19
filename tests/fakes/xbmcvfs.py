"""Minimal fake of Kodi's xbmcvfs module for tests."""

import os

# conftest points this at a per-test temporary directory.
special_roots = {}


def translatePath(path):
    for prefix, real in special_roots.items():
        if path.startswith(prefix):
            return os.path.join(real, path[len(prefix):].replace("/", os.sep))
    return path


def mkdirs(path):
    os.makedirs(path, exist_ok=True)
    return True


def exists(path):
    return os.path.exists(path)


def reset():
    special_roots.clear()
