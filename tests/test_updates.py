"""DEP-16: the release check client (server/al/updates.py, decision 0065).
REL-UPDATE-WIRE: the core tick, the acknowledgement POST, the settings
import rule and the snapshot 'update' block.
REL-UPDATE-TRIGGER: the installer start by itself while the game is idle,
'Update now' and the click-only switch (injected spawner only: no test
starts a process).

Transport and clock are injected: no test touches the network."""

import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al import VERSION, settingsio, updates, webfetch
from server.al import core as core_mod
from server.al.http import serve

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "u" * 48

REPO = "example-owner/example-app"
T0 = 1_800_000_000.0
DAY = updates.DAY_S


def release(tag="v9.0.0", prerelease=False, **extra):
    doc = {"tag_name": tag, "prerelease": prerelease, "draft": False,
           "published_at": "2026-11-19T00:00:00Z",
           "html_url": f"https://github.com/{REPO}/releases/tag/{tag}",
           "assets": [{"name": "SHA256SUMS.txt", "size": 300,
                       "digest": "sha256:" + "a" * 64,
                       "browser_download_url": f"https://github.com/{REPO}/releases/download/{tag}/SHA256SUMS.txt"}]}
    doc.update(extra)
    return json.dumps(doc).encode()


class Fake:
    """fetch(method, url, headers, body) recording every call."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        if not self.answers:
            return 200, {"ETag": '"e1"'}, release()
        return self.answers.pop(0)


def client(fake, enabled=True, acked=updates.WORDING_VERSION, repo=REPO, cache=None,
           changelog=None, installed="1.0.0"):
    return updates.UpdateClient(lambda: enabled, lambda: acked, repo=repo, fetch=fake,
                                clock=lambda: T0, cache_dir=cache, changelog=changelog,
                                installed=installed)


def test_disabled_never_calls_the_transport(tmp_path):
    fake = Fake()
    c = client(fake, enabled=False, cache=tmp_path)
    for i in range(5):
        assert c.tick(T0 + i * DAY) is False
    assert fake.calls == []
    assert not (tmp_path / updates.STATE_NAME).exists()
    assert c.view()["ack_needed"] is False


def test_enabled_and_acked_makes_one_call_per_24_h():
    fake = Fake()
    c = client(fake)
    assert c.tick(T0) is True
    for dt in (1, 3600, DAY - 1):
        assert c.tick(T0 + dt) is False
    assert len(fake.calls) == 1
    assert c.tick(T0 + DAY) is True
    assert len(fake.calls) == 2


def test_clock_is_used_when_tick_gets_no_time():
    fake = Fake()
    c = client(fake)
    assert c.tick() is True
    assert c.view()["checked_at"] == T0


def test_earlier_opt_in_without_the_acknowledgement_makes_no_request():
    for acked in (None, 0, False, True, "1", updates.WORDING_VERSION - 1):
        fake = Fake()
        c = client(fake, acked=acked)
        assert c.tick(T0) is False
        assert fake.calls == []
        assert c.view()["ack_needed"] is True


def test_empty_or_missing_repository_constant_is_off(tmp_path):
    for repo in ("", "   ", "no-slash", "a/b/c", "-x/y", "a/..", "a/b c", 42):
        fake = Fake()
        c = client(fake, repo=repo)
        assert c.tick(T0) is False
        assert fake.calls == []
        v = c.view()
        assert v["releases_url"] is None and v["ack_needed"] is False
    assert updates.load_repo(tmp_path / "missing.json") == ""
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="ascii")
    assert updates.load_repo(bad) == ""
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"repo": REPO}), encoding="ascii")
    assert updates.load_repo(good) == REPO
    good.write_text(json.dumps({"repo": ""}), encoding="ascii")
    assert updates.load_repo(good) == ""


def test_request_goes_only_to_api_github_with_the_user_agent_and_no_cookie():
    fake = Fake()
    client(fake).tick(T0)
    (method, url, headers), = fake.calls
    assert method == "GET"
    assert url == f"https://api.github.com/repos/{REPO}/releases/latest"
    assert headers["User-Agent"] == webfetch.user_agent(updates.UA_PURPOSE)
    assert headers["User-Agent"].startswith(f"AshLight/{VERSION} ")
    assert "contact" not in headers["User-Agent"]
    assert not any(k.lower() in ("cookie", "authorization") for k in headers)
    assert updates.ALLOWED_HOSTS == ("api.github.com",)


def test_a_redirect_off_the_allow_list_is_never_followed():
    fake = Fake((302, {"Location": "https://evil.example/latest"}, b""))
    c = client(fake)
    assert c.tick(T0) is True
    assert len(fake.calls) == 1
    assert c.view()["error"]
    assert c.tick(T0 + 60) is False  # the failed attempt used the day's read


def test_304_keeps_the_cached_answer_and_parses_nothing(tmp_path, monkeypatch):
    fake = Fake((200, {"ETag": '"abc"'}, release("v2.0.0")),
                (304, {"ETag": '"abc"'}, b"not json at all"))
    c = client(fake, cache=tmp_path)
    c.tick(T0)
    assert c.view()["latest"] == "2.0.0"

    def boom(body):
        raise AssertionError("a 304 must not be parsed")
    monkeypatch.setattr(updates, "_parse_release", boom)
    assert c.tick(T0 + DAY) is True
    assert fake.calls[1][2]["If-None-Match"] == '"abc"'
    v = c.view()
    assert v["latest"] == "2.0.0" and v["newer"] is True and v["error"] is None
    assert v["checked_at"] == T0 + DAY


def test_403_with_a_rate_limit_reset_is_honoured():
    reset = int(T0 + 30 * 3600)
    fake = Fake((403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)}, b"{}"))
    c = client(fake)
    assert c.tick(T0) is True
    assert c.tick(T0 + DAY + 3600) is False  # past the daily slot, before the reset
    assert len(fake.calls) == 1
    assert c.tick(reset) is True
    assert len(fake.calls) == 2


def test_retry_after_is_honoured():
    fake = Fake((429, {"Retry-After": str(3 * DAY)}, b""))
    c = client(fake)
    c.tick(T0)
    assert c.tick(T0 + 2 * DAY) is False
    assert c.tick(T0 + 3 * DAY) is True
    assert len(fake.calls) == 2


def test_a_wait_past_seven_days_is_capped():
    fake = Fake((403, {"Retry-After": str(400 * DAY)}, b""))
    c = client(fake)
    c.tick(T0)
    assert c.tick(T0 + updates.WAIT_MAX_S) is True


def test_network_failure_uses_the_day_and_never_raises():
    def broken(method, url, headers, body=None):
        broken.n += 1
        raise webfetch.FetchError("network: down")
    broken.n = 0
    c = updates.UpdateClient(lambda: True, lambda: 1, repo=REPO, fetch=broken, clock=lambda: T0)
    assert c.tick(T0) is True
    assert c.tick(T0 + 3600) is False
    assert broken.n == 1
    assert c.view()["error"].startswith("request failed")


def test_state_survives_a_restart_and_a_new_repo_starts_fresh(tmp_path):
    fake = Fake((200, {"ETag": '"x"'}, release("v3.1.0")))
    client(fake, cache=tmp_path).tick(T0)
    again = Fake()
    c2 = client(again, cache=tmp_path)
    assert c2.tick(T0 + 60) is False
    assert again.calls == []
    assert c2.view()["latest"] == "3.1.0"
    other = client(again, cache=tmp_path, repo="other-owner/other-app")
    assert other.view()["latest"] is None
    assert other.tick(T0 + 60) is True


def test_cached_answer_keeps_assets_for_the_installer(tmp_path):
    client(Fake(), cache=tmp_path).tick(T0)
    doc = json.loads((tmp_path / updates.STATE_NAME).read_text(encoding="ascii"))
    a, = doc["latest"]["assets"]
    assert a["name"] == "SHA256SUMS.txt" and a["size"] == 300
    assert a["digest"] == "sha256:" + "a" * 64


def test_404_draft_and_garbage_give_no_latest():
    for answer in ((404, {}, b'{"message": "Not Found"}'),
                   (200, {}, release(draft=True)),
                   (200, {}, b"[1, 2]"),
                   (200, {}, b"\xff\xfe")):
        c = client(Fake(answer))
        c.tick(T0)
        v = c.view()
        assert v["latest"] is None and v["newer"] is False


def test_prerelease_never_counts_as_newer_than_a_release():
    assert updates.is_newer("v1.1.0", "1.0.0") is True
    assert updates.is_newer("v1.1.0-rc.1", "1.0.0") is False
    assert updates.is_newer("v1.1.0", "1.0.0", latest_prerelease=True) is False
    assert updates.is_newer("v1.0.0", "1.0.0-rc.2") is True
    assert updates.is_newer("v1.0.0", "1.0.0") is False
    assert updates.is_newer("v0.9.9", "1.0.0") is False
    assert updates.is_newer("junk", "1.0.0") is False
    c = client(Fake((200, {}, release("v5.0.0-rc.1"))))
    c.tick(T0)
    v = c.view()
    assert v["latest"] == "5.0.0-rc.1" and v["newer"] is False and v["prerelease"] is True
    c = client(Fake((200, {}, release("v5.0.0", prerelease=True))))
    c.tick(T0)
    assert c.view()["newer"] is False


def test_semver_precedence():
    order = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta",
             "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0"]
    keys = [updates.version_key(updates.parse_version(v)) for v in order]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)
    assert updates.parse_version("1.0.0-01") is None
    assert updates.parse_version("v1.2.3+build.5")[:3] == (1, 2, 3)


CHANGELOG = """# Changelog

Intro line.

## [0.4.0] - 2026-12-03
<!-- lead: hand-written -->
Lead of four.
Second line.
<!-- /lead -->

### Added
- not shown while a lead exists

## [0.3.0] - 2026-12-02

### Added
- Thing A
- Thing B

## [0.2.0] - 2026-12-01
- Two

## [0.1.0] - 2026-11-19
- One
"""


def test_view_carries_installed_latest_notes_url_checked_at_and_ack(tmp_path):
    log = tmp_path / "CHANGELOG.md"
    log.write_text(CHANGELOG, encoding="ascii")
    c = client(Fake((200, {}, release("v0.4.0"))), changelog=log, installed="0.3.0")
    before = c.view()
    assert before["checked_at"] is None and before["latest"] is None
    c.tick(T0)
    v = c.view()
    assert v["installed"] == "0.3.0"
    assert v["latest"] == "0.4.0" and v["newer"] is True
    assert v["releases_url"] == f"https://github.com/{REPO}/releases"
    assert v["checked_at"] == T0
    assert v["ack_needed"] is False
    assert [n["version"] for n in v["notes"]] == ["0.4.0", "0.3.0", "0.2.0"]
    assert v["notes"][0] == {"version": "0.4.0", "date": "2026-12-03",
                             "text": "Lead of four. Second line."}
    assert v["notes"][1]["text"] == "Thing A; Thing B"
    assert set(v) >= {"installed", "latest", "notes", "releases_url", "checked_at", "ack_needed"}


def test_notes_from_the_shipped_changelog_and_a_missing_file(tmp_path):
    notes = updates.changelog_notes()
    assert notes and notes[0]["version"] == VERSION
    assert updates.changelog_notes(tmp_path / "none.md") == []


def test_view_is_json_and_ascii(tmp_path):
    c = client(Fake(), cache=tmp_path)
    c.tick(T0)
    json.dumps(c.view()).encode("ascii")


@pytest.mark.parametrize("value", ["a/b", "Owner-1/repo.name_x"])
def test_clean_repo_accepts_github_names(value):
    assert updates.clean_repo(value) == value


# ------------------------------------------------- REL-UPDATE-WIRE: the core

class GitHubOnly(Fake):
    """Answers the release read; any other host fails the test."""

    def __call__(self, method, url, headers, body=None):
        assert url.startswith("https://api.github.com/"), url
        return super().__call__(method, url, headers, body)


def _core(tmp_path, monkeypatch, fake, cfg=None, repo=REPO):
    def no_read(path=None):
        raise AssertionError("a test core never reads config/public_repo.json")
    monkeypatch.setattr(updates, "load_repo", no_read)
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    path = tmp_path / "local.json"
    path.write_text(json.dumps(cfg or {"web_data": False}), encoding="ascii")
    core = core_mod.Core(runtime=tmp_path / "rt", log_path=str(log), tail=False,
                         config_path=path, web_fetch=fake, update_repo=repo)
    clock = [T0]
    core.updates.clock = lambda: clock[0]
    return core, path, clock


def _run(core, now=None):
    thread = core.tick_update(now)
    if thread is not None:
        thread.join(10)
        assert not thread.is_alive()
    return thread


def test_core_tick_drives_the_client_once_a_day_only_when_on_and_acked(tmp_path, monkeypatch):
    fake = GitHubOnly()
    core, cfg, clock = _core(tmp_path, monkeypatch, fake)
    assert core.updates.state_file().parent == tmp_path / "rt" / "cache" / "updates"
    assert core.updates.changelog == tmp_path / "rt" / "CHANGELOG.md"
    for _ in range(3):  # web data off: never a request, whatever the day
        assert _run(core) is None
        clock[0] += DAY
    assert fake.calls == []
    core.set_web_data(True)  # an opt-in with no acknowledgement
    assert core.web_data_acked() is None
    for _ in range(3):
        assert _run(core) is None
        clock[0] += DAY
    assert fake.calls == []
    assert core.state.snapshot()["update"]["ack_needed"] is True
    core.set_web_data(None, ack=updates.WORDING_VERSION)
    assert core.web_data_acked() == updates.WORDING_VERSION
    assert core.web_data_enabled() is True
    assert _run(core) is not None
    assert len(fake.calls) == 1
    for dt in (1, 3600, DAY - 1):  # at most once per 24 h
        assert _run(core, clock[0] + dt) is None
    assert len(fake.calls) == 1
    clock[0] += DAY
    assert _run(core) is not None
    assert len(fake.calls) == 2
    core.set_web_data(False)  # off again: due, but no request
    clock[0] += DAY
    assert _run(core) is None
    assert len(fake.calls) == 2
    saved = json.loads(cfg.read_text(encoding="ascii"))
    assert saved["web_data_ack"] == updates.WORDING_VERSION and saved["web_data"] is False


@pytest.mark.parametrize("old", [0, True, "1", updates.WORDING_VERSION - 1])
def test_an_old_wording_version_in_the_config_makes_no_request(tmp_path, monkeypatch, old):
    fake = GitHubOnly()
    core, _, _ = _core(tmp_path, monkeypatch, fake, cfg={"web_data": True, "web_data_ack": old})
    assert _run(core) is None
    assert fake.calls == []
    assert core.state.snapshot()["update"]["ack_needed"] is True


def test_set_web_data_refuses_another_wording_version(tmp_path, monkeypatch):
    core, cfg, _ = _core(tmp_path, monkeypatch, GitHubOnly())
    before = cfg.read_text(encoding="ascii")
    for bad in (0, True, "1", 1.0, updates.WORDING_VERSION + 1):
        with pytest.raises(ValueError):
            core.set_web_data(True, ack=bad)
    assert cfg.read_text(encoding="ascii") == before


def test_tick_sources_starts_the_read_and_never_waits_for_it(tmp_path, monkeypatch):
    gate, seen = threading.Event(), []

    def slow(method, url, headers, body=None):
        seen.append(url)
        assert gate.wait(10)
        return 200, {}, release("v9.0.0")
    core, _, _ = _core(tmp_path, monkeypatch, slow,
                       cfg={"web_data": True, "web_data_ack": updates.WORDING_VERSION})
    core.tick_sources()  # returns while the request is still open
    thread = core._update_thread
    assert thread is not None and thread.is_alive()
    assert core.tick_update() is None  # a read in flight is never doubled
    gate.set()
    thread.join(10)
    assert seen == [f"https://api.github.com/repos/{REPO}/releases/latest"]
    assert core.state.snapshot()["update"]["latest"] == "9.0.0"


def test_snapshot_update_block_carries_the_view_and_no_event_text(tmp_path, monkeypatch):
    fake = GitHubOnly((200, {"ETag": '"e"'}, release("v9.0.0")))
    core, _, _ = _core(tmp_path, monkeypatch, fake,
                       cfg={"web_data": True, "web_data_ack": updates.WORDING_VERSION})
    before = core.state.snapshot()
    assert before["update"] is None
    _run(core)
    snap = core.state.snapshot()
    block = snap["update"]
    assert set(block) >= {"installed", "latest", "notes", "releases_url", "checked_at",
                          "ack_needed"}
    assert block["installed"] == VERSION and block["latest"] == "9.0.0"
    assert block["releases_url"] == f"https://github.com/{REPO}/releases"
    assert block["checked_at"] == T0 and block["ack_needed"] is False
    assert block["notes"] == []  # a test core never reads the shipped CHANGELOG.md
    assert "text" not in block  # no card or event text, only the view
    assert snap["recent_events"] == before["recent_events"]
    assert snap["events_seen"] == before["events_seen"]
    view = core.updates.view()
    assert {k: block[k] for k in view} == view
    # REL-UPDATE-TRIGGER: the two added keys (a checkout: nothing staged)
    assert set(block) - set(view) == {"staged", "click_only"}
    assert block["staged"] is None and block["click_only"] is False
    # an unchanged view bumps no version, so SSE pushes nothing new
    version = core.state.version
    assert core.publish_update() is False and core.state.version == version
    json.dumps(block).encode("ascii")


def test_a_test_core_without_a_repository_stays_off(tmp_path, monkeypatch):
    fake = GitHubOnly()
    core, _, _ = _core(tmp_path, monkeypatch, fake, repo=None,
                       cfg={"web_data": True, "web_data_ack": updates.WORDING_VERSION})
    assert core.updates.repo == ""
    assert _run(core) is None and fake.calls == []
    block = core.state.snapshot()["update"]
    assert block["releases_url"] is None and block["ack_needed"] is False


def test_settings_import_never_sets_web_data_ack(tmp_path, monkeypatch):
    assert "web_data_ack" in settingsio.NEVER and "web_data_ack" not in settingsio.ALLOWED
    doc = {"kind": settingsio.KIND, "schema": settingsio.SCHEMA,
           "settings": {"web_data_ack": updates.WORDING_VERSION, "league": "L"}}
    update, report = settingsio.parse_import(doc, {"web_data": True})
    assert update == {"league": "L"} and "web_data_ack" in report["ignored"]
    assert "web_data_ack" not in settingsio.export_doc(
        {"web_data_ack": updates.WORDING_VERSION}, "v")["settings"]
    core, cfg, _ = _core(tmp_path, monkeypatch, GitHubOnly(), cfg={"web_data": True})
    core.import_settings(doc)
    saved = json.loads(cfg.read_text(encoding="ascii"))
    assert "web_data_ack" not in saved and saved["league"] == "L"
    assert core.web_data_acked() is None


def _req(port, method, path, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    raw = json.dumps(body).encode("ascii") if body is not None else None
    headers = {"Host": f"127.0.0.1:{port}", "X-AL-Token": TOKEN}
    if raw is not None:
        headers.update({"Content-Type": "application/json", "Content-Length": str(len(raw))})
    conn.request(method, path, body=raw, headers=headers)
    r = conn.getresponse()
    out = (r.status, json.loads(r.read().decode("ascii")))
    conn.close()
    return out


def test_post_web_data_with_ack_stores_the_wording_version(tmp_path, monkeypatch):
    core, cfg, _ = _core(tmp_path, monkeypatch, GitHubOnly())
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    try:
        status, doc = _req(server.port, "GET", "/api/web-data")
        assert status == 200
        assert doc["wording_version"] == updates.WORDING_VERSION
        assert doc["ack_needed"] is False and doc["acked"] is False
        assert any("update check" in u for u in doc["uses"])
        # an opt-in from a page without the new sentence: no acknowledgement
        status, doc = _req(server.port, "POST", "/api/web-data", {"enabled": True})
        assert status == 200 and doc["web_data"] is True and doc["ack_needed"] is True
        assert "web_data_ack" not in json.loads(cfg.read_text(encoding="ascii"))
        before = cfg.read_text(encoding="ascii")
        for bad in (0, True, "1", None, 1.5, updates.WORDING_VERSION + 1):
            status, _ = _req(server.port, "POST", "/api/web-data",
                             {"enabled": False, "ack": bad})
            assert status == 400, bad
        assert cfg.read_text(encoding="ascii") == before  # nothing written
        status, doc = _req(server.port, "POST", "/api/web-data",
                           {"enabled": True, "ack": updates.WORDING_VERSION})
        assert status == 200 and doc["acked"] is True and doc["ack_needed"] is False
        saved = json.loads(cfg.read_text(encoding="ascii"))
        assert saved["web_data_ack"] == updates.WORDING_VERSION and saved["web_data"] is True
        # the acknowledgement alone is accepted too and keeps the switch
        status, doc = _req(server.port, "POST", "/api/web-data", {"enabled": False})
        assert status == 200
        status, doc = _req(server.port, "POST", "/api/web-data",
                           {"ack": updates.WORDING_VERSION})
        assert status == 200 and doc["web_data"] is False and doc["acked"] is True
    finally:
        server.shutdown()
        server.server_close()


# -- REL-UPDATE-TRIGGER (F-077, DEP-17) ---------------------------------------

ON = {"web_data": True, "web_data_ack": updates.WORDING_VERSION}


class Child:
    """A started process stand-in: poll() is None while it runs."""

    def __init__(self):
        self.code = None

    def poll(self):
        return self.code


class Spawner:
    """The injected spawner: records every start, never runs anything."""

    def __init__(self, fail=False):
        self.calls = []
        self.children = []
        self.fail = fail

    def __call__(self, argv, creationflags=0):
        self.calls.append((list(argv), creationflags))
        if self.fail:
            raise OSError("no such file")
        child = Child()
        self.children.append(child)
        return child

    def finish(self):
        for child in self.children:
            child.code = 0


def _installed(tmp_path, monkeypatch):
    """An installed copy by its home (AL_HOME); no marker, nothing staged."""
    home = tmp_path / "home"
    (home / "staged").mkdir(parents=True)
    monkeypatch.setenv("AL_HOME", str(home))
    return home


def _trigger_core(tmp_path, monkeypatch, cfg=ON, installed=True, idle=True, spawn=None):
    """A test core whose cached answer names v9.0.0 (newer than VERSION)."""
    if not installed:
        monkeypatch.delenv("AL_HOME", raising=False)
    fake = GitHubOnly((200, {"ETag": '"e"'}, release("v9.0.0")))
    core, path, clock = _core(tmp_path, monkeypatch, fake, cfg=dict(ON))
    core.update_spawn = spawn if spawn is not None else Spawner()
    _run(core)  # the day's read (web data on, acknowledged): latest 9.0.0
    assert core.updates.newer_version() == "9.0.0"
    assert core.update_spawn.calls == []  # the read pass starts nothing
    home = _installed(tmp_path, monkeypatch) if installed else None
    path.write_text(json.dumps(cfg), encoding="ascii")
    core.state.set_tailer(consented=True, idle=idle)
    return core, path, clock, home


def test_idle_installed_copy_starts_the_installer_once_hidden_below_normal(tmp_path, monkeypatch):
    core, _, clock, home = _trigger_core(tmp_path, monkeypatch)
    assert core.game_idle() is True
    spawn = core.update_spawn
    _run(core)
    assert len(spawn.calls) == 1
    argv, flags = spawn.calls[0]
    assert Path(argv[1]).name == "boot.py"
    assert argv[2:] == ["server.al.install", "update", "--yes", "--home", str(home)]
    assert Path(argv[0]).name.lower() in ("pythonw.exe", "python.exe", "pythonw", "python")
    assert flags == updates.creation_flags()
    if updates.os.name == "nt":
        for bit in (updates.BELOW_NORMAL, updates.NO_WINDOW, updates.DETACHED):
            assert flags & bit
    for _ in range(3):  # never beside a run still going
        _run(core)
    assert len(spawn.calls) == 1
    spawn.finish()
    _run(core, clock[0] + 3600)  # ended, same day: once a day per version
    assert len(spawn.calls) == 1
    clock[0] += DAY
    _run(core)
    assert len(spawn.calls) == 2
    spawn.finish()
    # staged now: never started for that version again
    (home / "staged" / "9.0.0.json").write_text(json.dumps({"version": "9.0.0"}),
                                                encoding="ascii")
    clock[0] += DAY
    _run(core)
    assert len(spawn.calls) == 2
    assert core.state.snapshot()["update"]["staged"] == "9.0.0"


def test_game_not_idle_never_starts(tmp_path, monkeypatch):
    core, _, clock, _ = _trigger_core(tmp_path, monkeypatch, idle=False)
    for _ in range(3):
        _run(core)
        clock[0] += DAY
    assert core.update_spawn.calls == []
    core.state.set_tailer(consented=False, idle=True)  # no consent: not idle
    _run(core)
    assert core.update_spawn.calls == []


def test_click_only_waits_for_update_now(tmp_path, monkeypatch):
    core, _, clock, home = _trigger_core(tmp_path, monkeypatch,
                                         cfg=dict(ON, update_click_only=True))
    assert core.update_click_only() is True
    for _ in range(3):
        _run(core)
        clock[0] += DAY
    assert core.update_spawn.calls == []
    assert core.state.snapshot()["update"]["click_only"] is True
    core.state.set_tailer(idle=False)  # a click needs no idle game
    assert core.update_now() == updates.STARTED
    assert len(core.update_spawn.calls) == 1
    assert core.update_spawn.calls[0][0][2:5] == ["server.al.install", "update", "--yes"]
    assert core.update_now() == updates.RUNNING  # never doubled
    assert len(core.update_spawn.calls) == 1


def test_web_data_off_or_unacknowledged_never_starts(tmp_path, monkeypatch):
    for cfg in ({"web_data": False, "web_data_ack": updates.WORDING_VERSION},
                {"web_data": True}):
        sub = tmp_path / str(len(cfg))
        sub.mkdir()
        core, _, clock, _ = _trigger_core(sub, monkeypatch, cfg=cfg)
        for _ in range(3):
            _run(core)
            clock[0] += DAY
        assert core.update_now() == updates.OFF
        assert core.update_spawn.calls == []


def test_checkout_never_starts(tmp_path, monkeypatch):
    core, _, clock, _ = _trigger_core(tmp_path, monkeypatch, installed=False)
    assert updates.update_command() is None
    for _ in range(3):
        _run(core)
        clock[0] += DAY
    assert core.update_now() == updates.CHECKOUT
    assert core.update_spawn.calls == []
    assert core.state.snapshot()["update"]["staged"] is None


def test_client_start_rules_without_a_core(tmp_path):
    spawn = Spawner()
    fake = Fake((200, {}, release("v9.0.0")))
    c = client(fake)
    c.command = lambda: ["py", "boot.py", "server.al.install", "update", "--yes"]
    assert c.maybe_start(T0, True, spawn) is False  # nothing cached yet
    c.tick(T0)
    for idle in (False, None, 1, "yes"):  # only an exact True is idle
        assert c.maybe_start(T0, idle, spawn) is False
    c.click_only = lambda: True
    assert c.maybe_start(T0, True, spawn) is False
    c.click_only = False
    assert c.maybe_start(T0, True, spawn, staged=lambda: "9.0.0") is False
    assert spawn.calls == []
    assert c.maybe_start(T0, True, spawn, staged=lambda: "8.0.0") is True
    assert len(spawn.calls) == 1
    # a pre-release is never started; a failed start never raises
    pre = client(Fake((200, {}, release("v9.1.0", prerelease=True))))
    pre.command = c.command
    pre.tick(T0)
    assert pre.update_now(spawn) == updates.CURRENT
    bad = client(Fake((200, {}, release("v9.0.0"))))
    bad.command = c.command
    bad.tick(T0)
    assert bad.update_now(Spawner(fail=True)) == updates.FAILED
    assert len(spawn.calls) == 1


def _post(port, path, body=b"{}", headers=None, ctype="application/json"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    h = {"Host": f"127.0.0.1:{port}", "X-AL-Token": TOKEN, "Content-Type": ctype,
         "Content-Length": str(len(body))}
    h.update(headers or {})
    h = {k: v for k, v in h.items() if v is not None}
    conn.request("POST", path, body=body, headers=h)
    r = conn.getresponse()
    out = (r.status, r.read())
    conn.close()
    return out


def test_post_update_now_needs_the_token_the_host_checks_and_no_fields(tmp_path, monkeypatch):
    core, _, _, _ = _trigger_core(tmp_path, monkeypatch, cfg=dict(ON, update_click_only=True))
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    port, path = server.port, "/api/update-now"
    try:
        assert _post(port, path, headers={"X-AL-Token": None})[0] == 401
        assert _post(port, path, headers={"X-AL-Token": "x" * 48})[0] == 401
        assert _post(port, path + f"?token={TOKEN}", headers={"X-AL-Token": None})[0] == 401
        assert _post(port, path, headers={"Host": "evil.example"})[0] in (400, 403)
        assert _post(port, path, headers={"Origin": "http://evil.example"})[0] == 403
        assert _post(port, path, headers={"Sec-Fetch-Site": "cross-site"})[0] == 403
        assert _post(port, path, body=b'{"version": "9.0.0"}')[0] == 400
        assert _post(port, path, body=b"[]")[0] == 400
        assert _post(port, path, body=b"x", ctype="text/plain")[0] == 415
        assert core.update_spawn.calls == []  # nothing refused started anything
        status, raw = _post(port, path)
        assert status == 200
        assert json.loads(raw.decode("ascii")) == {"started": True, "state": "started"}
        assert len(core.update_spawn.calls) == 1
        status, raw = _post(port, path, body=b"")  # no body at all: the same click
        assert status == 200 and json.loads(raw.decode("ascii"))["state"] == "running"
        assert len(core.update_spawn.calls) == 1
    finally:
        server.shutdown()
        server.server_close()


def test_update_click_only_is_on_the_settings_allow_list(tmp_path, monkeypatch):
    assert settingsio.ALLOWED["update_click_only"] is settingsio._bool
    assert settingsio.LABELS["update_click_only"]
    assert "update_click_only" not in settingsio.NEVER
    doc = settingsio.export_doc({"update_click_only": True}, "v")
    assert doc["settings"] == {"update_click_only": True}
    update, report = settingsio.parse_import(doc, {})
    assert update == {"update_click_only": True} and report["applied"] == ["update_click_only"]
    bad = dict(doc, settings={"update_click_only": "yes"})
    with pytest.raises(settingsio.SettingsError):
        settingsio.parse_import(bad, {})
    core, cfg, _ = _core(tmp_path, monkeypatch, GitHubOnly())
    assert core.update_click_only() is False
    core.import_settings(doc)
    assert json.loads(cfg.read_text(encoding="ascii"))["update_click_only"] is True
    assert core.update_click_only() is True


# REL-UPDATE-APPLY-NOW: an 'Update now' run that staged asks the client to apply

def _apply_request(core):
    return core.runtime / updates.APPLY_REQUEST


def _stage(home, version="9.0.0"):
    doc = json.dumps({"version": version})
    (home / "staged" / (version + ".json")).write_text(doc, encoding="ascii")


def test_update_now_run_that_stages_writes_the_apply_request(tmp_path, monkeypatch):
    core, _, _, home = _trigger_core(tmp_path, monkeypatch, cfg=dict(ON, update_click_only=True))
    assert core.update_now() == updates.STARTED
    _run(core)  # still running: nothing asked yet
    assert not _apply_request(core).exists()
    _stage(home)
    core.update_spawn.finish()
    _run(core)  # the run ended with 9.0.0 staged
    doc = json.loads(_apply_request(core).read_text(encoding="ascii"))
    assert doc == {"version": "9.0.0"}
    _apply_request(core).unlink()  # the client takes it once
    _run(core)
    assert not _apply_request(core).exists()  # one ask per click


def test_update_now_run_that_stages_nothing_asks_nothing(tmp_path, monkeypatch):
    core, _, _, _ = _trigger_core(tmp_path, monkeypatch, cfg=dict(ON, update_click_only=True))
    assert core.update_now() == updates.STARTED
    core.update_spawn.finish()
    _run(core)
    assert not _apply_request(core).exists()


def test_update_now_with_the_release_staged_already_asks_at_once(tmp_path, monkeypatch):
    core, _, _, home = _trigger_core(tmp_path, monkeypatch, cfg=dict(ON, update_click_only=True))
    _stage(home)
    assert core.update_now() == updates.STAGED
    assert core.update_spawn.calls == []
    doc = json.loads(_apply_request(core).read_text(encoding="ascii"))
    assert doc == {"version": "9.0.0"}


def test_an_automatic_run_never_asks_for_an_apply(tmp_path, monkeypatch):
    core, _, clock, home = _trigger_core(tmp_path, monkeypatch)
    _run(core)  # the idle start (no click)
    assert len(core.update_spawn.calls) == 1
    _stage(home)
    core.update_spawn.finish()
    _run(core, clock[0] + 60)
    assert not _apply_request(core).exists()  # it applies at the next client start


def test_refused_update_now_asks_nothing(tmp_path, monkeypatch):
    core, _, _, _ = _trigger_core(tmp_path, monkeypatch, installed=False)
    assert core.update_now() == updates.CHECKOUT
    assert not _apply_request(core).exists()
