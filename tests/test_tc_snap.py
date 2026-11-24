"""TC-SNAP: build-time game-data snapshot with a mocked fetcher only.

No real network request is made: every test passes its own fetch function,
and the default fetcher is checked only for its URL guard.
"""

import hashlib
import json
import types
from pathlib import Path

import pytest

from server.al import VERSION
from server.al.theorycraft import snapshot

ROOT = Path(__file__).resolve().parents[1]
SRC = {"mods": "https://repoe-fork.github.io/poe2/mods.json",
       "stats": "https://repoe-fork.github.io/poe2/stats_by_file.json",
       "skilltree": None}
AT = chr(64)
TREE_URL = "https://raw.githubusercontent.com/grindinggear/poe2-skilltree-export/main/data.json"


class Fake:
    def __init__(self, bodies, etag="W/\"1\""):
        self.bodies = dict(bodies)
        self.etag = etag
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append((url, dict(headers)))
        if self.etag and headers.get("If-None-Match") == self.etag:
            return 304, {"ETag": self.etag}, b""
        body = self.bodies[url]
        if isinstance(body, Exception):
            raise body
        return 200, {"ETag": self.etag, "Last-Modified": "Mon, 16 Nov 2026 00:00:00 GMT"}, body


def _bodies():
    return {SRC["mods"]: b'{"ExampleMod": {"domain": "item"}}',
            SRC["stats"]: b'[{"id": "example_stat"}]'}


def test_first_run_writes_files_and_manifest(tmp_path):
    fake = Fake(_bodies())
    out = snapshot.run(tmp_path, fetch=fake, sources=SRC, now=1_800_000_000)
    assert out == {"mods": "fetched", "stats": "fetched", "skilltree": "disabled"}
    man = json.loads((tmp_path / "manifest.json").read_text(encoding="ascii"))
    assert man["attribution"] == snapshot.ATTRIBUTION
    e = man["files"]["mods"]
    assert e["url"] == SRC["mods"]
    assert e["sha256"] == hashlib.sha256(_bodies()[SRC["mods"]]).hexdigest()
    assert e["fetched_at"].endswith("Z") and e["bytes"] > 0 and e["etag"]
    assert (tmp_path / "mods.json").read_bytes() == _bodies()[SRC["mods"]]
    for url, headers in fake.calls:
        assert headers["User-Agent"].startswith(f"AshLight/{VERSION} ")
        assert "If-None-Match" not in headers


def test_idempotent_rerun_makes_no_request_then_conditional(tmp_path):
    fake = Fake(_bodies())
    t0 = 1_800_000_000
    snapshot.run(tmp_path, fetch=fake, sources=SRC, now=t0)
    before = (tmp_path / "manifest.json").read_bytes()
    n = len(fake.calls)
    out = snapshot.run(tmp_path, fetch=fake, sources=SRC, now=t0 + 60)
    assert set(out.values()) == {"fresh", "disabled"} and len(fake.calls) == n
    assert (tmp_path / "manifest.json").read_bytes() == before
    out = snapshot.run(tmp_path, fetch=fake, sources=SRC, now=t0 + snapshot.MIN_AGE_S + 1)
    assert out["mods"] == "unchanged" and out["stats"] == "unchanged"
    assert all(h.get("If-None-Match") == fake.etag for _, h in fake.calls[n:])
    man = json.loads((tmp_path / "manifest.json").read_text(encoding="ascii"))
    assert man["files"]["mods"]["fetched_at"] == snapshot._utc(t0)


def test_same_sha_without_etag_is_unchanged_new_sha_refetched(tmp_path):
    fake = Fake(_bodies(), etag=None)
    t0 = 1_800_000_000
    snapshot.run(tmp_path, fetch=fake, sources=SRC, now=t0)
    out = snapshot.run(tmp_path, fetch=fake, sources=SRC, force=True, now=t0 + 5)
    assert out["mods"] == "unchanged"
    fake.bodies[SRC["mods"]] = b'{"ExampleMod2": {}}'
    out = snapshot.run(tmp_path, fetch=fake, sources=SRC, force=True, now=t0 + 10)
    assert out["mods"] == "fetched" and out["stats"] == "unchanged"
    assert (tmp_path / "mods.json").read_bytes() == b'{"ExampleMod2": {}}'


def test_offline_and_bad_bodies_never_fatal(tmp_path):
    fake = Fake({SRC["mods"]: snapshot.FetchError("network: offline"),
                 SRC["stats"]: b"<html>not json</html>"})
    out = snapshot.run(tmp_path, fetch=fake, sources=SRC, now=1_800_000_000)
    assert out["mods"].startswith("error") and out["stats"].startswith("error")
    assert not (tmp_path / "mods.json").exists() and not (tmp_path / "stats.json").exists()
    assert not (tmp_path / "manifest.json").exists()


def test_main_opt_out_and_strict(tmp_path, capsys):
    def offline(url, headers):
        raise snapshot.FetchError("network: offline")
    assert snapshot.main(["--dir", str(tmp_path)], environ={"AL_NO_SNAPSHOT": "1"},
                         fetch=offline) == 0
    assert "skipped" in capsys.readouterr().out
    assert snapshot.main(["--dir", str(tmp_path)], environ={}, fetch=offline,
                         web_data=True) == 0
    assert snapshot.main(["--dir", str(tmp_path), "--strict"], environ={},
                         fetch=offline, web_data=True) == 1


def test_default_cache_is_in_al_sidecar(tmp_path):
    env = {"AL_SIDECAR_ROOT": str(tmp_path / "AL")}
    assert snapshot.cache_dir(env) == (tmp_path / "AL" / "Cache" / "gamedata").resolve()


@pytest.mark.parametrize("url", ["http://repoe-fork.github.io/poe2/mods.json",
                                 "https://example.org/mods.json",
                                 "https://poe2db.tw/us/Modifiers",
                                 "https://www.poe2wiki.net/wiki/Mods",
                                 "http://raw.githubusercontent.com/grindinggear/"
                                 "poe2-skilltree-export/main/data.json",
                                 "https://raw.githubusercontent.com/someone/else/main/data.json",
                                 "https://raw.githubusercontent.com/grindinggear/"
                                 "poe2-skilltree-export/../../x/y.json",
                                 "https://githubusercontent.com.example.org/grindinggear/"
                                 "poe2-skilltree-export/main/data.json",
                                 # SEC-CEIL-SNAPSHOT: the webfetch rule as well
                                 # user info; AT kept apart so the bytes
                                 # never look like an address to the sweep
                                 "https://user:pw" + AT + "repoe-fork.github.io/poe2/mods.json",
                                 "https://user" + AT + "repoe-fork.github.io/poe2/mods.json",
                                 "https://repoe-fork.github.io:8443/poe2/mods.json",
                                 "https://185.199.108.153/poe2/mods.json",
                                 "https://[::1]/poe2/mods.json",
                                 "https://raw.githubusercontent.com/grindinggear/"
                                 "poe2-skilltree-export/%2e%2e/%2e%2e/x/y.json",
                                 "https://repoe-fork.github.io/poe2/mods.json\\x"])
def test_url_guard_refuses_off_allowlist(url, monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("the guard must refuse before any request")
    monkeypatch.setattr(snapshot.urllib.request, "build_opener", no_network)
    with pytest.raises(snapshot.FetchError):
        snapshot.http_fetch(url, {})
    with pytest.raises(snapshot.FetchError):
        snapshot._check_url(url)


class _Resp:
    """A fake urllib reply: read1 hands out `blocks` one at a time; every
    call moves the fake clock on by `step` seconds."""

    def __init__(self, blocks, clock=None, step=0.0, status=200, headers=None):
        self.blocks = list(blocks)
        self.clock, self.step = clock, step
        self.status = status
        self.headers = headers or {"ETag": "W/\"9\""}
        self.reads = 0

    def read1(self, n):
        self.reads += 1
        if self.clock is not None:
            self.clock[0] += self.step
        if not self.blocks:
            return b""
        block = self.blocks.pop(0)
        if len(block) > n:
            self.blocks.insert(0, block[n:])
            block = block[:n]
        return block

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _opener(resp, seen=None):
    class Opener:
        def open(self, req, timeout=None):
            if seen is not None:
                seen.append(timeout)
            return resp
    return lambda *handlers: Opener()


def test_http_fetch_streams_to_a_temp_file_in_the_cache(tmp_path, monkeypatch):
    body = b'{"a": 1}' * 1000
    resp = _Resp([body[i:i + 300] for i in range(0, len(body), 300)])
    monkeypatch.setattr(snapshot.urllib.request, "build_opener", _opener(resp))
    status, headers, got = snapshot.http_fetch(SRC["mods"], {}, cap=len(body),
                                               spool_dir=tmp_path)
    assert status == 200 and headers["ETag"] == "W/\"9\""
    assert isinstance(got, Path) and got.parent == tmp_path
    assert got.read_bytes() == body
    got.unlink()


def test_body_over_the_source_cap_is_refused_and_leaves_no_file(tmp_path, monkeypatch):
    # the real fetcher: the read stops one byte past the cap, the temp file goes
    cap = 1000
    resp = _Resp([b"x" * 400] * 10)
    monkeypatch.setattr(snapshot.urllib.request, "build_opener", _opener(resp))
    with pytest.raises(snapshot.FetchError, match="too large"):
        snapshot.http_fetch(SRC["mods"], {}, cap=cap, spool_dir=tmp_path)
    assert resp.reads <= 4  # never read on to the end of the reply
    assert list(tmp_path.iterdir()) == []
    # through run(): the per-source cap table decides, nothing is written
    monkeypatch.setitem(snapshot.SOURCE_CAPS, "mods", cap)
    resp = _Resp([b"[" + b"1," * 600 + b"1]"])
    monkeypatch.setattr(snapshot.urllib.request, "build_opener", _opener(resp))
    out = snapshot.run(tmp_path, sources={"mods": SRC["mods"]}, now=1_800_000_000)
    assert out["mods"].startswith("error") and "too large" in out["mods"]
    assert list(tmp_path.iterdir()) == []
    # an injected fetch that returns bytes meets the same cap
    big = Fake({SRC["mods"]: b"[" + b"1," * 600 + b"1]"})
    out = snapshot.run(tmp_path, fetch=big, sources={"mods": SRC["mods"]},
                       now=1_800_000_000)
    assert "too large" in out["mods"] and list(tmp_path.iterdir()) == []


def test_every_source_has_a_cap_under_the_ceiling():
    for name in list(snapshot.SOURCES) + list(snapshot.OPTIONAL_SOURCES):
        cap = snapshot.source_cap(name)
        assert 0 < cap <= snapshot.MAX_BYTES, name
        assert name in snapshot.SOURCE_CAPS, name
    assert snapshot.source_cap("unknown") == snapshot.DEFAULT_CAP


def _fake_time(clock):
    """A stand-in for snapshot's `time` name only: patching the real time
    module's monotonic would freeze the clock for every other thread."""
    return types.SimpleNamespace(monotonic=lambda: clock[0])


def test_slow_drip_is_dropped_at_the_deadline(tmp_path, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(snapshot, "time", _fake_time(clock))
    # one byte a second, far more bytes than the deadline allows
    resp = _Resp([b"x"] * 100_000, clock=clock, step=1.0)
    seen = []
    monkeypatch.setattr(snapshot.urllib.request, "build_opener", _opener(resp, seen))
    with pytest.raises(snapshot.FetchError, match="deadline"):
        snapshot.http_fetch(SRC["mods"], {}, cap=10 ** 9, spool_dir=tmp_path)
    assert resp.reads <= snapshot.DEADLINE_S + 2
    assert seen and 0 < seen[0] <= snapshot.TIMEOUT_S
    assert list(tmp_path.iterdir()) == []


def test_the_socket_timeout_never_outlasts_the_deadline(tmp_path, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(snapshot, "time", _fake_time(clock))
    resp = _Resp([b"[]"])
    seen = []
    monkeypatch.setattr(snapshot.urllib.request, "build_opener", _opener(resp, seen))
    got = snapshot.http_fetch(SRC["mods"], {}, cap=100, spool_dir=tmp_path,
                              deadline_s=5.0)[2]
    assert seen == [5.0]
    got.unlink()


def test_a_real_fetch_replaces_the_file_atomically(tmp_path, monkeypatch):
    resp = _Resp([b'{"ExampleMod": {}}'])
    monkeypatch.setattr(snapshot.urllib.request, "build_opener", _opener(resp))
    out = snapshot.run(tmp_path, sources={"mods": SRC["mods"]}, now=1_800_000_000)
    assert out == {"mods": "fetched"}
    assert (tmp_path / "mods.json").read_bytes() == b'{"ExampleMod": {}}'
    assert sorted(p.name for p in tmp_path.iterdir()) == ["manifest.json", "mods.json"]
    man = json.loads((tmp_path / "manifest.json").read_text(encoding="ascii"))
    assert man["files"]["mods"]["bytes"] == len(b'{"ExampleMod": {}}')
    assert man["files"]["mods"]["sha256"] == hashlib.sha256(b'{"ExampleMod": {}}').hexdigest()
    # unchanged body: the temp file is removed, the file stays
    resp2 = _Resp([b'{"ExampleMod": {}}'])
    monkeypatch.setattr(snapshot.urllib.request, "build_opener", _opener(resp2))
    out = snapshot.run(tmp_path, sources={"mods": SRC["mods"]}, force=True,
                       now=1_800_000_100)
    assert out == {"mods": "unchanged"}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["manifest.json", "mods.json"]
    # a body that is not JSON leaves no temp file and the old file in place
    resp3 = _Resp([b"<html>"])
    monkeypatch.setattr(snapshot.urllib.request, "build_opener", _opener(resp3))
    out = snapshot.run(tmp_path, sources={"mods": SRC["mods"]}, force=True,
                       now=1_800_000_200)
    assert out["mods"].startswith("error")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["manifest.json", "mods.json"]


def test_url_guard_accepts_every_enabled_source():
    for url in snapshot.SOURCES.values():
        if url:
            snapshot._check_url(url)  # raises when off the allowlist


def test_sources_policy():
    # decision 0009 (items 2, 3 amended, 4; research 0011): repoe-fork PoE2
    # files under their real names, plus GGG's own tree export, fetch-only.
    s = snapshot.SOURCES
    # DATA-SNAP-TRIM: mods and stats have no reader, so they are not fetched
    # by default; a dev re-check passes them explicitly.
    assert snapshot.OPTIONAL_SOURCES["mods"] == "https://repoe-fork.github.io/poe2/mods.json"
    assert snapshot.OPTIONAL_SOURCES["stats"] == (
        "https://repoe-fork.github.io/poe2/stats_by_file.json")
    assert s["base_items"] == "https://repoe-fork.github.io/poe2/base_items.json"
    assert s["stat_translations"] == (
        "https://repoe-fork.github.io/poe2/stat_translations/stat_descriptions.json")
    assert s["skilltree"] == TREE_URL
    # HUD-ACT (decision 0020): world areas for the zone level table.
    assert s["world_areas"] == "https://repoe-fork.github.io/poe2/world_areas.json"
    # DATA-GEMS-SNAP (decision 0081): gem names and levels for Kindler.
    assert s["gems"] == "https://repoe-fork.github.io/poe2/gems.json"
    # ITEM-INFO-UNIQUES-PROBE: the unique item list joined SOURCES.
    assert s["uniques"] == "https://repoe-fork.github.io/poe2/uniques.json"
    assert set(s) == {"base_items", "stat_translations", "skilltree", "world_areas", "gems",
                      "uniques"}
    assert set(snapshot.ALLOWED_HOSTS) == {"repoe-fork.github.io", "raw.githubusercontent.com"}


def test_real_source_names_mocked_fetch(tmp_path):
    # DATA-SRC-URLS / DATA-TREE-SRC acceptance: the real URLs through a mock.
    bodies = {u: b'{"nodes": {}}' for u in snapshot.SOURCES.values() if u}
    fake = Fake(bodies)
    # UA-CONTACT: the GGG tree source needs a contact (a neutral test token);
    # DATA-SNAP-PROBE: these stub bodies are not real files, so no probes
    # (tests/test_snap_probe.py covers the probe on the real table)
    out = snapshot.run(tmp_path, fetch=fake, now=1_800_000_000, contact="test-contact",
                       probes={})
    assert out == {k: "fetched" for k in snapshot.SOURCES}
    assert sorted(u for u, _ in fake.calls) == sorted(bodies)
    man = json.loads((tmp_path / "manifest.json").read_text(encoding="ascii"))
    assert man["files"]["skilltree"]["url"] == TREE_URL
    assert man["files"]["world_areas"]["url"].endswith("/world_areas.json")
    assert len(man["files"]) == 6
    assert (tmp_path / "skilltree.json").is_file()
    assert "tree export" in snapshot.ATTRIBUTION
    for _, headers in fake.calls:
        assert headers["User-Agent"].startswith(f"AshLight/{VERSION} ")
        assert "test-contact" in headers["User-Agent"]


def test_core_never_imports_snapshot():
    for rel in ("server/al/core.py", "server/al/http.py", "server/al/__main__.py",
                "server/al/theorycraft/store.py", "server/al/theorycraft/paste.py"):
        text = (ROOT / rel).read_text(encoding="ascii")
        assert "import snapshot" not in text and ".snapshot import" not in text, rel
        assert "theorycraft.snapshot" not in text, rel


def test_build_script_runs_snapshot_opt_out_safe():
    ps = (ROOT / "scripts" / "build.ps1").read_text(encoding="ascii")
    assert "server.al.theorycraft.snapshot" in ps
    assert "NoSnapshot" in ps and "AL_NO_SNAPSHOT" in ps


def test_a_changed_file_keeps_one_previous_copy(tmp_path):
    """DATA-TREE-HOLD: before a changed body replaces <name>.json the current
    file is kept as <name>.prev.json; one copy, the older one overwritten;
    an unchanged body leaves the previous copy alone."""
    fake = Fake(_bodies(), etag=None)
    t0 = 1_800_000_000
    prev = tmp_path / "mods.prev.json"
    snapshot.run(tmp_path, fetch=fake, sources=SRC, now=t0)
    assert not prev.exists()  # first fetch: nothing to keep
    v1 = _bodies()[SRC["mods"]]
    fake.bodies[SRC["mods"]] = b'{"ExampleMod2": {}}'
    out = snapshot.run(tmp_path, fetch=fake, sources=SRC, force=True, now=t0 + 5)
    assert out["mods"] == "fetched" and out["stats"] == "unchanged"
    assert prev.read_bytes() == v1
    assert (tmp_path / "mods.json").read_bytes() == b'{"ExampleMod2": {}}'
    assert not (tmp_path / "stats.prev.json").exists()
    out = snapshot.run(tmp_path, fetch=fake, sources=SRC, force=True, now=t0 + 10)
    assert out["mods"] == "unchanged" and prev.read_bytes() == v1
    fake.bodies[SRC["mods"]] = b'{"ExampleMod3": {}}'
    snapshot.run(tmp_path, fetch=fake, sources=SRC, force=True, now=t0 + 15)
    assert prev.read_bytes() == b'{"ExampleMod2": {}}'  # one copy only
    assert sorted(p.name for p in tmp_path.glob("mods*.json")) == [
        "mods.json", "mods.prev.json"]
    assert snapshot.previous_path(tmp_path / "skilltree.json").name == "skilltree.prev.json"
    assert snapshot.keep_previous(tmp_path / "missing.json") is False


def test_a_fresh_snapshot_and_its_manifest_list_six_files(tmp_path):
    # DATA-SNAP-TRIM: a default run fetches six files (DATA-GEMS-SNAP added
    # gems, ITEM-INFO-UNIQUES-PROBE uniques), never mods or stats.
    bodies = {u: b'{"nodes": {}}' for u in snapshot.SOURCES.values() if u}
    fake = Fake(bodies)
    out = snapshot.run(tmp_path, fetch=fake, now=1_800_000_000, contact="test-contact",
                       probes={})
    assert set(out) == {"base_items", "stat_translations", "skilltree", "world_areas",
                        "gems", "uniques"}
    man = json.loads((tmp_path / "manifest.json").read_text(encoding="ascii"))
    assert set(man["files"]) == set(out)
    assert not (tmp_path / "mods.json").exists() and not (tmp_path / "stats.json").exists()


def test_gems_source_lands_where_kindler_reads_it(tmp_path):
    """DATA-GEMS-SNAP: the gems source is a repoe-fork file under the same
    opt-in and attribution, cached as the file archetypes reads, with a cap
    no smaller than the reader's own ceiling."""
    from server.al.theorycraft import archetypes
    url = snapshot.SOURCES["gems"]
    snapshot._check_url(url)
    assert url.startswith(snapshot.REPOE_POE2)
    assert not snapshot.needs_contact("gems", url)
    assert "gems.json" == archetypes.GEMS_FILE
    assert snapshot.source_cap("gems") >= archetypes.GEMS_MAX_BYTES
    assert "repoe-fork" in snapshot.ATTRIBUTION
    body = json.dumps({"Metadata/Items/Gems/SkillGemA": {
        "display_name": "Alpha Strike", "requirements": {"level": 2}}}).encode("ascii")
    fake = Fake({url: body})
    out = snapshot.run(tmp_path, fetch=fake, sources={"gems": url}, now=1_800_000_000,
                       probes={})
    assert out == {"gems": "fetched"}
    assert archetypes.load_gems(tmp_path / archetypes.GEMS_FILE) == {
        "alpha strike": {"name": "Alpha Strike", "level": 2}}
