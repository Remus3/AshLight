"""TC-SNAP: build-time game-data snapshot with a mocked fetcher only.

No real network request is made: every test passes its own fetch function,
and the default fetcher is checked only for its URL guard.
"""

import hashlib
import json
from pathlib import Path

import pytest

from server.al import VERSION
from server.al.theorycraft import snapshot

ROOT = Path(__file__).resolve().parents[1]
SRC = {"mods": "https://repoe-fork.github.io/poe2/mods.json",
       "stats": "https://repoe-fork.github.io/poe2/stats_by_file.json",
       "skilltree": None}
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
                                 "poe2-skilltree-export/main/data.json"])
def test_url_guard_refuses_off_allowlist(url):
    with pytest.raises(snapshot.FetchError):
        snapshot.http_fetch(url, {})


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
    assert set(s) == {"base_items", "stat_translations", "skilltree", "world_areas"}
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
    assert len(man["files"]) == 4
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


def test_a_fresh_snapshot_and_its_manifest_list_four_files(tmp_path):
    # DATA-SNAP-TRIM: a default run fetches four files, never mods or stats.
    bodies = {u: b'{"nodes": {}}' for u in snapshot.SOURCES.values() if u}
    fake = Fake(bodies)
    out = snapshot.run(tmp_path, fetch=fake, now=1_800_000_000, contact="test-contact",
                       probes={})
    assert set(out) == {"base_items", "stat_translations", "skilltree", "world_areas"}
    man = json.loads((tmp_path / "manifest.json").read_text(encoding="ascii"))
    assert set(man["files"]) == set(out)
    assert not (tmp_path / "mods.json").exists() and not (tmp_path / "stats.json").exists()
