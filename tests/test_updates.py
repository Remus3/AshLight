"""DEP-16: the release check client (server/al/updates.py, decision 0065).

Transport and clock are injected: no test touches the network."""

import json

import pytest

from server.al import VERSION, updates, webfetch

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
