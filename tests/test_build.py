import os
import zipfile

from tools import build


def test_build_creates_installable_zip(tmp_path):
    zip_path = build.build_zip(out_dir=str(tmp_path))
    version = build.read_version()
    assert os.path.basename(zip_path) == f"plugin.video.novaflix-{version}.zip"

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    # Kodi expects a single top-level folder named after the add-on ID.
    assert {n.split("/")[0] for n in names} == {"plugin.video.novaflix"}
    assert "plugin.video.novaflix/addon.xml" in names
    assert "plugin.video.novaflix/default.py" in names
    assert "plugin.video.novaflix/service.py" in names


def test_build_excludes_caches_and_bytecode(tmp_path):
    cache_dir = os.path.join(build.ADDON_DIR, "resources", "lib", "__pycache__")
    os.makedirs(cache_dir, exist_ok=True)
    marker = os.path.join(cache_dir, "junk.cpython-311.pyc")
    with open(marker, "wb") as f:
        f.write(b"x")
    try:
        zip_path = build.build_zip(out_dir=str(tmp_path))
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
    finally:
        os.remove(marker)


def test_zip_uses_forward_slashes(tmp_path):
    zip_path = build.build_zip(out_dir=str(tmp_path))
    with zipfile.ZipFile(zip_path) as zf:
        assert not any("\\" in n for n in zf.namelist())


# -- release / repository (M10) ------------------------------------------------------------

import hashlib
import xml.etree.ElementTree as ET

import pytest


def _fake_zip(folder, addon_id, version):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{addon_id}-{version}.zip")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"{addon_id}/addon.xml",
                    f'<?xml version="1.0"?>\n<addon id="{addon_id}" version="{version}" name="x"/>')
    return path


def test_secret_scan_flags_keys_and_allows_known_public_values():
    # Built at runtime so this file never holds a key-shaped string for the history scan.
    uuid_key = "-".join(["9e8d7c6b", "5a49", "3827", "1605", "f4e3d2c1b0a9"])
    hex_id = "f0e1d2c3" * 4
    found = build.find_secrets(f'key = "{uuid_key}"\nclient = "{hex_id}"')
    assert [kind for kind, _ in found] == ["UUID-style API key (TorBox format)", "32-hex client ID or key (MAL format)"]
    assert build.find_secrets('CLIENT_ID = "X245A4XAIBGVM"\ntoken = "TEST_TOKEN_000000000000000"') == []
    assert build.find_secrets("info_hash " + "a" * 40) == []  # torrent hashes are not secrets


def test_packages_and_history_have_no_secrets():
    assert build.scan_packages() == []
    assert build.scan_history() == []


def test_release_builds_kodi_repository(tmp_path):
    repo = str(tmp_path)
    report = build.release(repo, tests=False, history=False)
    version = build.read_version()
    assert report[build.ADDON_ID][:2] == (version, "added")
    zip_path = os.path.join(repo, build.ADDON_ID, f"{build.ADDON_ID}-{version}.zip")
    with open(zip_path, "rb") as f:
        assert open(zip_path + ".sha256").read() == hashlib.sha256(f.read()).hexdigest()
    assert os.path.exists(os.path.join(repo, build.ADDON_ID, "novaflix-icon.png"))  # listed in addon.xml <assets>
    index = open(os.path.join(repo, "addons.xml"), "rb").read()
    assert open(os.path.join(repo, "addons.xml.sha256")).read() == hashlib.sha256(index).hexdigest()
    ids = {(a.get("id"), a.get("version")) for a in ET.fromstring(index)}
    assert (build.ADDON_ID, version) in ids and (build.REPO_ID, build.read_version(build.REPO_ID)) in ids


def test_unchanged_rerun_is_allowed_but_changed_content_needs_a_bump(tmp_path):
    repo = str(tmp_path)
    build.release(repo, tests=False, history=False)
    assert build.release(repo, tests=False, history=False)[build.ADDON_ID][1] == "unchanged"
    target = os.path.join(repo, build.ADDON_ID, f"{build.ADDON_ID}-{build.read_version()}.zip")
    with open(target, "ab") as f:
        f.write(b"changed")
    with pytest.raises(build.ReleaseError, match="bump the version"):
        build.release(repo, tests=False, history=False)


def test_older_version_than_published_is_refused(tmp_path):
    _fake_zip(os.path.join(str(tmp_path), build.ADDON_ID), build.ADDON_ID, "99.0.0")
    with pytest.raises(build.ReleaseError, match="older than"):
        build.release(str(tmp_path), tests=False, history=False)


def test_keeps_last_three_versions_and_lists_them_all(tmp_path):
    repo = str(tmp_path)
    folder = os.path.join(repo, build.ADDON_ID)
    for old in ("0.0.1", "0.0.2", "0.0.3"):
        _fake_zip(folder, build.ADDON_ID, old)
    report = build.release(repo, tests=False, history=False)
    assert report[build.ADDON_ID][2] == ["0.0.1"]
    kept = sorted(n for n in os.listdir(folder) if n.endswith(".zip"))
    assert len(kept) == 3 and f"{build.ADDON_ID}-0.0.1.zip" not in kept
    versions = [a.get("version") for a in ET.parse(os.path.join(repo, "addons.xml")).getroot()
                if a.get("id") == build.ADDON_ID]
    assert versions == [build.read_version(), "0.0.3", "0.0.2"]  # newest first; older ones for rollback


def test_repository_addon_points_at_https_pages_url():
    build.check_repo_url()
    xml = open(os.path.join(build.ROOT, build.REPO_ID, "addon.xml"), encoding="utf-8").read()
    assert 'verify="sha256"' in xml and "<hashes>sha256</hashes>" in xml


def test_folders_get_link_pages_for_kodi_file_manager(tmp_path):
    repo = str(tmp_path)
    build.release(repo, tests=False, history=False)
    root_page = open(os.path.join(repo, "index.html"), encoding="utf-8").read()
    assert '<a href="repository.novaflix/">' in root_page and '<a href="addons.xml">' in root_page
    repo_page = open(os.path.join(repo, build.REPO_ID, "index.html"), encoding="utf-8").read()
    assert f'<a href="{build.REPO_ID}-{build.read_version(build.REPO_ID)}.zip">' in repo_page


def test_publish_mirrors_repository_and_drops_pruned_files(tmp_path, monkeypatch):
    import subprocess
    remote = str(tmp_path / "pages.git")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", remote], check=True)
    monkeypatch.setattr(build, "PAGES_GIT", remote)
    repo, pages = str(tmp_path / "repo"), str(tmp_path / "pages")
    build.release(repo, tests=False, history=False)
    git_id = ["-c", "user.name=t", "-c", "user.email=t@t"]
    monkeypatch.setattr(build, "_git", lambda cwd, *args: subprocess.run(
        ["git", *git_id, *args], cwd=cwd, check=True, capture_output=True, text=True).stdout)
    assert build.publish(repo, pages).startswith("published")  # first run clones
    assert os.path.exists(os.path.join(pages, ".nojekyll"))
    stale = os.path.join(pages, build.ADDON_ID, f"{build.ADDON_ID}-0.0.1.zip")
    open(stale, "wb").close()  # a version published earlier that release has since pruned
    build._git(pages, "add", "-A")
    build._git(pages, "commit", "-q", "-m", "old version")
    assert build.publish(repo, pages).startswith("published")
    assert not os.path.exists(stale)
    assert build.publish(repo, pages) == "nothing changed"


def test_release_publishes_static_pages(tmp_path):
    repo = str(tmp_path / "repo")
    build.release(repo, tests=False, history=False)
    with open(os.path.join(build.ROOT, "pages", "mal-login.html"), "rb") as f:
        source = f.read()
    with open(os.path.join(repo, "mal-login.html"), "rb") as f:
        assert f.read() == source
    with open(os.path.join(repo, "index.html"), encoding="utf-8") as f:
        assert 'href="mal-login.html"' in f.read()


def test_release_includes_the_launcher(tmp_path):
    repo = str(tmp_path)
    report = build.release(repo, tests=False, history=False)
    assert build.LAUNCHER_ID == "script.novaflix" and build.LAUNCHER_ID in build.ADDONS
    version = build.read_version(build.LAUNCHER_ID)
    assert report[build.LAUNCHER_ID][:2] == (version, "added")
    assert os.path.exists(os.path.join(repo, build.LAUNCHER_ID, f"{build.LAUNCHER_ID}-{version}.zip"))
    with open(os.path.join(repo, "addons.xml"), encoding="utf-8") as f:
        assert 'id="script.novaflix"' in f.read()


def test_repo_urls_are_novaflix():
    # Publishing to AniVerse's update site would replace AniVerse on every device.
    assert build.REPO_URL == "https://chiefabs6-ops.github.io/novaflix-repo/"
    assert build.PAGES_GIT == "https://github.com/chiefabs6-ops/novaflix-repo.git"
    assert build.ADDONS == ("plugin.video.novaflix", "script.novaflix", "repository.novaflix")


def test_publish_refuses_a_checkout_of_another_repository(tmp_path, monkeypatch):
    # A copied dist/pages of AniVerse's update site must never be mirrored over and pushed.
    import subprocess
    pages = str(tmp_path / "pages")
    subprocess.run(["git", "init", "-q", pages], check=True)
    subprocess.run(["git", "-C", pages, "remote", "add", "origin",
                    "https://github.com/chiefabs6-ops/aniverse-repo.git"], check=True)
    repo = str(tmp_path / "repo")
    build.release(repo, tests=False, history=False)
    pushed = []
    real_git = build._git
    monkeypatch.setattr(build, "_git", lambda cwd, *args: pushed.append(args) if args[:1] == ("push",)
                        else real_git(cwd, *args))
    with pytest.raises(build.ReleaseError, match="aniverse-repo"):
        build.publish(repo, pages)
    assert pushed == []


def test_scanner_finds_jwt_tokens():
    fake = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
    assert [kind for kind, _ in build.find_secrets(f"x = {fake}")] == ["JWT-style token (TMDB read token)"]


def test_recorded_tmdb_fixtures_hold_no_secrets():
    folder = os.path.join(build.ROOT, "tests", "fixtures", "tmdb")
    names = sorted(os.listdir(folder))
    assert len(names) == 20
    for name in names:
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            assert build.find_secrets(f.read()) == [], name
