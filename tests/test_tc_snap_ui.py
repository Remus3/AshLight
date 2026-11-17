"""TC-SNAP-UI: the snapshot attribution (decision 0009) in GET /api/version.

data_credit is null without snapshot data and the exact attribution once the
sidecar cache holds a manifest plus at least one data file. Token-protected
like every /api/* route. The sidecar root points at tmp_path.
"""

import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al import DISCLAIMER
from server.al.core import Core
from server.al.http import serve
from server.al.theorycraft import datacredit, snapshot

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "s" * 48
CREDIT = ("Game data (c) Grinding Gear Games. Item, mod and stat data comes from the "
          "RePoE fork community export (repoe-fork). Trade search stat ids are "
          "Grinding Gear Games' trade site data, passed on by repoe-fork. Ids it lacks come from "
          "Path of Building Community (PoE2, MIT license) when its optional calc files "
          "are installed. Passive tree data comes from "
          "Grinding Gear Games' public skill tree export. AshLight downloaded all of it to "
          "this computer when it was built.")


def make_cache(directory, names=("mods",), write_files=True):
    directory.mkdir(parents=True, exist_ok=True)
    doc = {"attribution": datacredit.ATTRIBUTION,
           "files": {n: {"url": "https://example.invalid/" + n} for n in names}}
    (directory / "manifest.json").write_text(json.dumps(doc), encoding="ascii")
    if write_files:
        for n in names:
            (directory / f"{n}.json").write_text("{}", encoding="ascii")


@pytest.fixture
def sidecar(tmp_path, monkeypatch):
    root = tmp_path / "sidecar"
    monkeypatch.setenv("AL_SIDECAR_ROOT", str(root))
    return root


@pytest.fixture
def srv(tmp_path, sidecar):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    server = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                   tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True)
    t.start()
    yield server
    server.stop()
    core.close()


def get(server, path, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    h = {"Host": f"127.0.0.1:{server.port}"}
    h.update(headers or {})
    conn.request("GET", path, headers=h)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r, data


def test_attribution_one_source_and_exact_credit():
    assert snapshot.ATTRIBUTION is datacredit.ATTRIBUTION
    assert snapshot.MANIFEST == datacredit.MANIFEST == "manifest.json"
    assert datacredit.CREDIT == CREDIT
    assert datacredit.ATTRIBUTION == CREDIT + " " + DISCLAIMER


def test_snapshot_cache_dir_shared(sidecar):
    assert snapshot.cache_dir() == datacredit.cache_dir() == sidecar / "Cache" / "gamedata"


def test_has_snapshot_needs_manifest_and_a_data_file(tmp_path):
    d = tmp_path / "gamedata"
    assert datacredit.has_snapshot(d) is False          # no directory
    d.mkdir()
    assert datacredit.has_snapshot(d) is False          # empty directory
    (d / "manifest.json").write_text("not json", encoding="ascii")
    assert datacredit.has_snapshot(d) is False          # unreadable manifest
    (d / "manifest.json").write_text('{"files": []}', encoding="ascii")
    assert datacredit.has_snapshot(d) is False          # files not a dict
    make_cache(d, names=("mods",), write_files=False)
    assert datacredit.has_snapshot(d) is False          # listed but not on disk
    (d / "mods.json").write_text("{}", encoding="ascii")
    assert datacredit.has_snapshot(d) is True


def test_credit_doc_exact(tmp_path):
    d = tmp_path / "gamedata"
    assert datacredit.credit_doc(d) is None
    make_cache(d)
    assert datacredit.credit_doc(d) == {"attribution": datacredit.ATTRIBUTION,
                                        "credit": CREDIT}


def test_version_without_cache_has_null_credit(srv):
    r, data = get(srv, "/api/version", {"X-AL-Token": TOKEN})
    assert r.status == 200
    doc = json.loads(data)
    assert doc["disclaimer"] == DISCLAIMER
    assert doc["data_credit"] is None


def test_version_with_cache_has_exact_attribution(srv, sidecar):
    make_cache(sidecar / "Cache" / "gamedata", names=("mods", "skilltree"))
    r, data = get(srv, "/api/version", {"X-AL-Token": TOKEN})
    assert r.status == 200
    doc = json.loads(data)
    assert doc["disclaimer"] == DISCLAIMER
    assert doc["data_credit"] == {"attribution": datacredit.ATTRIBUTION, "credit": CREDIT}


def test_version_credit_is_token_protected(srv, sidecar):
    make_cache(sidecar / "Cache" / "gamedata")
    r, data = get(srv, "/api/version")
    assert r.status == 401 and b"Grinding" not in data
    r, data = get(srv, "/api/version", {"X-AL-Token": "wrong"})
    assert r.status == 401 and b"Grinding" not in data


def test_disclaimer_lines_stay_in_footer_and_overlay():
    page = (ROOT / "web" / "index.html").read_text(encoding="ascii")
    assert f"<p>{DISCLAIMER}</p>" in page
    assert '<p id="data-credit" class="muted" hidden></p>' in page
    ov = (ROOT / "app" / "overlay" / "index.html").read_text(encoding="ascii")
    assert f'<p class="about">{DISCLAIMER}</p>' in ov
    assert '<p id="aboutData" class="about" hidden></p>' in ov


def test_core_still_never_imports_snapshot():
    text = (ROOT / "server" / "al" / "theorycraft" / "datacredit.py").read_text(
        encoding="ascii")
    assert "import snapshot" not in text and "webfetch" not in text
    assert "urllib" not in text
