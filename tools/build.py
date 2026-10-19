"""Package AniVerse and build its Kodi repository (DEC-038, DEC-039, architecture §13).

Usage:
  .venv\\Scripts\\python tools\\build.py [out_dir]   # plugin zip only (dev installs)
  .venv\\Scripts\\python tools\\build.py release      # checks + repository in dist/repo
  .venv\\Scripts\\python tools\\build.py publish      # mirror dist/repo to the Pages repo and push

`release` runs, in order, stopping at the first failure:
  1. secret scan of both add-ons and of the git history (SEC-01, SEC-02, SEC-14)
  2. the test suite
  3. version check: a version already in the repository may not change content
  4. zips into dist/repo/<id>/<id>-<version>.zip (+ .sha256 for each zip)
  5. keeps the last KEEP_VERSIONS versions of each add-on (DEC-039 rollback)
  6. addons.xml listing every kept version, plus addons.xml.sha256

dist/repo is what gets published to the public Pages repository at REPO_URL.
Publishing itself is a separate, owner-approved step (DEC-006).
"""

import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ADDON_ID = "plugin.video.aniverse"
REPO_ID = "repository.aniverse"
LAUNCHER_ID = "script.aniverse"  # Video add-ons tile that opens AniVerse without Kodi's folder screen
ADDON_DIR = os.path.join(ROOT, ADDON_ID)
ADDONS = (ADDON_ID, LAUNCHER_ID, REPO_ID)
REPO_URL = "https://chiefabs6-ops.github.io/aniverse-repo/"   # must match repository.aniverse/addon.xml
PAGES_GIT = "https://github.com/chiefabs6-ops/aniverse-repo.git"  # public: built zips only (DEC-038)
KEEP_VERSIONS = 3
PAGES_DIR = os.path.join(ROOT, "pages")  # static pages served next to addons.xml (M13 login relay)
EXCLUDED_DIRS = {"__pycache__", ".pytest_cache"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo")

# Things that look like real credentials. Values that are public by design or are
# test placeholders are allowed explicitly.
SECRET_PATTERNS = [
    ("UUID-style API key (TorBox format)", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)),
    ("32-hex client ID or key (MAL format)", re.compile(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])", re.I)),
    ("assigned token/secret/key", re.compile(
        r"(?:api_?key|token|secret|client_id|password)\s*[=:]\s*[\"']([A-Za-z0-9_\-]{20,})[\"']", re.I)),
]
ALLOWED = {
    "X245A4XAIBGVM",                       # Real-Debrid's public open-source client ID (SEC-01)
    "cdce9a1fb95fff27f3b8d337cece75fd",    # md5 of another add-on's addons.xml, quoted in research notes
    "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",  # made-up key in tests/test_build.py (scanner self-test)
    "a1b2c3d4e5f60718293a4b5c6d7e8f90",      # made-up client ID in tests/test_build.py
}
ALLOWED_PREFIXES = ("TEST", "FAKE", "DEVICECODE", "RDACCESSTOKEN", "RDREFRESH", "ACCESSTOKEN", "REFRESHTOKEN",
                    "TORBOXKEY", "OWNER", "SENTINEL")  # placeholders used in tests


class ReleaseError(Exception):
    pass


# -- zips -------------------------------------------------------------------------------

def addon_dir(addon_id):
    return os.path.join(ROOT, addon_id)


def read_version(addon_id=ADDON_ID):
    return ET.parse(os.path.join(addon_dir(addon_id), "addon.xml")).getroot().get("version")


def _package_files(addon_id):
    base = addon_dir(addon_id)
    for folder, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
        for name in sorted(files):
            if not name.endswith(EXCLUDED_SUFFIXES):
                yield os.path.join(folder, name)


def _zip_bytes(addon_id):
    """Deterministic zip (fixed timestamps), so unchanged content gives identical bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for full in _package_files(addon_id):
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            info = zipfile.ZipInfo(rel, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(full, "rb") as f:
                zf.writestr(info, f.read())
    return buffer.getvalue()


def build_zip(out_dir=None, addon_id=ADDON_ID):
    out_dir = out_dir or os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, f"{addon_id}-{read_version(addon_id)}.zip")
    with open(zip_path, "wb") as f:
        f.write(_zip_bytes(addon_id))
    return zip_path


# -- checks -----------------------------------------------------------------------------

def _allowed(value):
    return value in ALLOWED or value.upper().startswith(ALLOWED_PREFIXES)


def find_secrets(text):
    """[(kind, value)] for credential-looking strings that are not allowed."""
    found = []
    for kind, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(match.lastindex or 0)
            if not _allowed(value):
                found.append((kind, value))
    return found


def _mask(value):
    return value[:4] + "…" + value[-2:]


def scan_packages():
    problems = []
    for addon_id in ADDONS:
        for path in _package_files(addon_id):
            if path.endswith((".png", ".jpg")):
                continue
            with open(path, encoding="utf-8", errors="ignore") as f:
                for kind, value in find_secrets(f.read()):
                    problems.append(f"{os.path.relpath(path, ROOT)}: {kind} {_mask(value)}")
    return problems


def scan_history():
    """Added lines across all commits (SEC-02)."""
    log = subprocess.run(["git", "log", "-p", "--all", "--unified=0", "--no-color"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8", errors="ignore", check=True).stdout
    added = "\n".join(line[1:] for line in log.splitlines() if line.startswith("+") and not line.startswith("+++"))
    return [f"git history: {kind} {_mask(value)}" for kind, value in find_secrets(added)]


def check_repo_url():
    xml = open(os.path.join(addon_dir(REPO_ID), "addon.xml"), encoding="utf-8").read()
    urls = set(re.findall(r">(https?://[^<]+)<", xml))
    if not urls or any(not u.startswith(REPO_URL) for u in urls):
        raise ReleaseError(f"repository.aniverse/addon.xml must point at {REPO_URL} (found {sorted(urls)})")
    if not REPO_URL.startswith("https://"):
        raise ReleaseError("repository must be served over HTTPS (SEC-14)")


def run_tests():
    result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)
    if result.returncode:
        raise ReleaseError("tests failed")


# -- repository ---------------------------------------------------------------------------

def _version_key(version):
    return tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[.\-+]", version))


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def _versions_in(folder, addon_id):
    pattern = re.compile(rf"^{re.escape(addon_id)}-(.+)\.zip$")
    names = os.listdir(folder) if os.path.isdir(folder) else []
    return sorted((m.group(1) for m in map(pattern.match, names) if m), key=_version_key)


def _assets(addon_id):
    """Files named in addon.xml <assets> (icon, fanart): Kodi's repository browser loads them
    from next to the zips."""
    root = ET.parse(os.path.join(addon_dir(addon_id), "addon.xml")).getroot()
    return [el.text for el in root.iter() if el.tag in ("icon", "fanart", "banner", "clearlogo") and el.text]


def add_to_repo(repo_dir, addon_id):
    """Put the current version's zip into the repository. Returns "added" or "unchanged"."""
    folder = os.path.join(repo_dir, addon_id)
    version = read_version(addon_id)
    data = _zip_bytes(addon_id)
    target = os.path.join(folder, f"{addon_id}-{version}.zip")
    if os.path.exists(target):
        with open(target, "rb") as f:
            if f.read() == data:
                return "unchanged"
        raise ReleaseError(f"{addon_id} {version} is already published with different content: bump the version")
    newest = (_versions_in(folder, addon_id) or [None])[-1]
    if newest and _version_key(version) < _version_key(newest):
        raise ReleaseError(f"{addon_id} {version} is older than the published {newest}")
    _write(target, data)
    _write(target + ".sha256", _sha256(data).encode())
    for asset in _assets(addon_id):
        source = os.path.join(addon_dir(addon_id), asset)
        if os.path.exists(source):
            shutil.copyfile(source, os.path.join(folder, asset))
    return "added"


def prune(repo_dir, addon_id, keep=KEEP_VERSIONS):
    folder = os.path.join(repo_dir, addon_id)
    removed = []
    for version in _versions_in(folder, addon_id)[:-keep]:
        for suffix in (".zip", ".zip.sha256"):
            path = os.path.join(folder, f"{addon_id}-{version}{suffix}")
            if os.path.exists(path):
                os.remove(path)
        removed.append(version)
    return removed


def write_index(repo_dir):
    """addons.xml with every kept version (Kodi then offers them for rollback) + its sha256."""
    entries = []
    for addon_id in ADDONS:
        folder = os.path.join(repo_dir, addon_id)
        for version in reversed(_versions_in(folder, addon_id)):
            with zipfile.ZipFile(os.path.join(folder, f"{addon_id}-{version}.zip")) as zf:
                xml = zf.read(f"{addon_id}/addon.xml").decode("utf-8")
            entries.append(re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", xml).strip())
    index = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n'
             + "\n".join(entries) + "\n</addons>\n").encode("utf-8")
    ET.fromstring(index)  # must be valid XML
    _write(os.path.join(repo_dir, "addons.xml"), index)
    _write(os.path.join(repo_dir, "addons.xml.sha256"), _sha256(index).encode())
    write_listings(repo_dir)
    return index


def write_listings(repo_dir):
    """index.html link pages: GitHub Pages lists no folders, but Kodi's file manager
    browses an http(s) source by reading the links on its page (first install from zip)."""
    for folder, dirs, files in os.walk(repo_dir):
        dirs.sort()
        names = [d + "/" for d in dirs] + sorted(f for f in files if f != "index.html")
        links = "\n".join(f'<a href="{name}">{name}</a><br>' for name in names)
        title = "AniVerse repository" + ("" if folder == repo_dir else f" / {os.path.basename(folder)}")
        page = (f'<!DOCTYPE html>\n<html><head><meta charset="utf-8"><title>{title}</title></head>\n'
                f"<body>\n{links}\n</body></html>\n")
        _write(os.path.join(folder, "index.html"), page.encode("utf-8"))


def copy_pages(repo_dir):
    """Copy pages/* (no keys or tokens, checked) into the repository root."""
    if not os.path.isdir(PAGES_DIR):
        return []
    copied = []
    for name in sorted(os.listdir(PAGES_DIR)):
        source = os.path.join(PAGES_DIR, name)
        if not os.path.isfile(source):
            continue
        with open(source, "rb") as f:
            data = f.read()
        found = find_secrets(data.decode("utf-8", "replace"))
        if found:
            raise ReleaseError(f"possible secrets in pages/{name}: {[_mask(v) for _, v in found]}")
        _write(os.path.join(repo_dir, name), data)
        copied.append(name)
    return copied


def release(repo_dir=None, tests=True, history=True):
    repo_dir = repo_dir or os.path.join(ROOT, "dist", "repo")
    check_repo_url()
    problems = scan_packages() + (scan_history() if history else [])
    if problems:
        raise ReleaseError("possible secrets found:\n  " + "\n  ".join(problems))
    if tests:
        run_tests()
    report = {}
    for addon_id in ADDONS:
        status = add_to_repo(repo_dir, addon_id)
        report[addon_id] = (read_version(addon_id), status, prune(repo_dir, addon_id))
    copy_pages(repo_dir)
    write_index(repo_dir)
    return report


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def publish(repo_dir=None, pages_dir=None, message=None):
    """Mirror dist/repo into a checkout of the Pages repository, commit and push.
    Run `release` first; this only copies what release produced."""
    repo_dir = repo_dir or os.path.join(ROOT, "dist", "repo")
    pages_dir = pages_dir or os.path.join(ROOT, "dist", "pages")
    if not os.path.exists(os.path.join(repo_dir, "addons.xml")):
        raise ReleaseError("nothing to publish: run `build.py release` first")
    if os.path.isdir(os.path.join(pages_dir, ".git")):
        _git(pages_dir, "pull", "--ff-only", "-q")
    else:
        _git(ROOT, "clone", "-q", PAGES_GIT, pages_dir)
    for folder, dirs, files in os.walk(pages_dir, topdown=True):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            path = os.path.join(folder, name)
            if name != ".nojekyll" and not os.path.exists(os.path.join(repo_dir, os.path.relpath(path, pages_dir))):
                os.remove(path)  # pruned versions disappear from the site too
    shutil.copytree(repo_dir, pages_dir, dirs_exist_ok=True)
    open(os.path.join(pages_dir, ".nojekyll"), "a").close()
    _git(pages_dir, "add", "-A")
    if not _git(pages_dir, "status", "--porcelain").strip():
        return "nothing changed"
    versions = ", ".join(f"{a} {read_version(a)}" for a in ADDONS)
    _git(pages_dir, "commit", "-q", "-m", message or f"Publish {versions}")
    _git(pages_dir, "push", "-q")
    return f"published {versions}"


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "publish":
        try:
            print(publish())
        except (ReleaseError, subprocess.CalledProcessError) as exc:
            sys.exit(f"publish stopped: {exc}")
    elif len(sys.argv) > 1 and sys.argv[1] == "release":
        try:
            for addon_id, (version, status, removed) in release().items():
                print(f"{addon_id} {version}: {status}" + (f" (removed old {', '.join(removed)})" if removed else ""))
        except ReleaseError as exc:
            sys.exit(f"release stopped: {exc}")
        print(os.path.join(ROOT, "dist", "repo"))
    else:
        print(build_zip(sys.argv[1] if len(sys.argv) > 1 else None))
