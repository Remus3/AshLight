"""REL-UPDATE-CHECKS (finding F-077, DEP-11): the Checks rows and report
lines of an installed copy.

A checkout has no install row. In an installed scratch home (AL_HOME, a
tmp folder, never the live install) the version row shows mode, version,
previous and the last update result; a staged version gives one line; a
rolled-back version gives one line with the fix; the copied report
carries all of it right under the header fields, with no path or
identifier. The files are written by the installer's own writers (marker,
staged document, last-update report, skip list) so a format drift breaks
this test, not the player's Checks. No socket, no process, no network.
"""

import json
from datetime import datetime, timezone

import pytest

from server.al import diag
from server.al import report as rep
from server.al.core import Core
from server.al.install import home as homemod
from server.al.install import switch, update
from server.al.plug import report as route

NOW = 1795200000.0
HOUR = 3600.0


def stamp(at):
    return datetime.fromtimestamp(at, timezone.utc)


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "Scratch Home"
    h.mkdir()
    monkeypatch.setenv("AL_HOME", str(h))
    return h


@pytest.fixture
def core(tmp_path, monkeypatch):
    monkeypatch.setattr(route, "_now", lambda: NOW)
    c = Core(runtime=tmp_path / "rt", tail=False)
    yield c
    c.close()


def marker(home, version, previous=None, pending=False):
    doc = homemod.new_marker(version, "3.12.7", "39.2.7", now=stamp(NOW - 30 * 86400))
    doc.update(previous=previous, pending_confirm=pending)
    homemod.write_marker(home, doc)


def stage(home, version, apply_after):
    folder = homemod.layout(home)["staged"]
    folder.mkdir(parents=True, exist_ok=True)
    doc = {"schema": update.STAGED_SCHEMA, "version": version, "from": "0.4.0",
           "apply_after": homemod.now_text(stamp(apply_after)),
           "staged_at": homemod.now_text(stamp(NOW - HOUR))}
    (folder / f"{version}.json").write_text(json.dumps(doc), encoding="ascii")


def rows_of(core, now=NOW):
    v = diag.view(core.diag_facts(now), "1.0.0", now=now)
    return v, {r["id"]: r for r in v["checks"]}


# -- checkout ----------------------------------------------------------------

def test_checkout_has_no_install_row(core, monkeypatch):
    monkeypatch.delenv("AL_HOME", raising=False)
    facts = core.diag_facts(NOW)
    assert facts["install"] == {"mode": "checkout"}
    v, rows = rows_of(core)
    assert diag.INSTALL_ID not in rows and diag.UPDATE_ID not in rows
    assert diag.INSTALL_LABEL not in v["report"]
    assert diag.check_install({}, NOW) == []
    assert diag.check_install({"install": None}, NOW) == []


# -- the version row ---------------------------------------------------------

def test_installed_row_shows_version_and_previous(home, core):
    marker(home, "0.4.0", previous="0.3.9")
    v, rows = rows_of(core)
    r = rows[diag.INSTALL_ID]
    assert r["label"] == "Installed copy" and r["status"] == diag.PASS
    assert r["detail"] == "Version 0.4.0, previous 0.3.9 kept."
    assert r["fix"] is None and diag.UPDATE_ID not in rows
    # the row sits after the hotkey rows, before the dashboard address
    ids = [x["id"] for x in v["checks"]]
    assert ids.index(diag.INSTALL_ID) == ids.index("port") - 1


def test_first_install_keeps_no_earlier_version(home, core):
    marker(home, "0.4.0")
    _, rows = rows_of(core)
    assert rows[diag.INSTALL_ID]["detail"] == "Version 0.4.0, no earlier version kept."


def test_unreadable_marker_reads_unknown(home, core):
    (home / "install.json").write_text("{not json", encoding="ascii")
    _, rows = rows_of(core)
    r = rows[diag.INSTALL_ID]
    assert r["status"] == diag.UNKNOWN and r["detail"] == "Its version file can't be read."


def test_last_update_result_with_its_age(home, core):
    marker(home, "0.4.0", previous="0.3.9")
    switch.add_line(home, "switched from 0.3.9 to 0.4.0; waiting", "apply",
                    switch.SWITCHED, "0.4.0", "0.3.9", now=stamp(NOW - 2 * HOUR))
    v, rows = rows_of(core)
    r = rows[diag.INSTALL_ID]
    # RUN-QUIET-FEED: the view holds the age mark and the absolute time
    assert r["detail"] == ("Version 0.4.0, previous 0.3.9 kept. Last update: "
                           "switched from 0.3.9 to 0.4.0, {ago}.")
    assert r["at"] == NOW - 2 * HOUR
    assert diag.render_detail(r, NOW).endswith("0.4.0, 2 h ago.")


# -- the staged line ---------------------------------------------------------

def test_staged_version_gives_one_line(home, core):
    marker(home, "0.4.0", previous="0.3.9")
    stage(home, "0.5.0", NOW + 20 * HOUR)
    _, rows = rows_of(core)
    r = rows[diag.UPDATE_ID]
    assert r["status"] == diag.NOTE and r["fix"] is None and r["label"] == "Update"
    due = homemod.now_text(stamp(NOW + 20 * HOUR))
    assert r["detail"] == ("Version 0.5.0 is ready. It starts the first time you "
                           f"open AshLight after {due[:10]} {due[11:16]} UTC.")
    # once due: the next start
    _, rows = rows_of(core, now=NOW + 21 * HOUR)
    assert rows[diag.UPDATE_ID]["detail"] == ("Version 0.5.0 is ready. It starts the "
                                             "next time you open AshLight.")


def test_only_the_newest_usable_staged_version_counts(home, core):
    marker(home, "0.4.0", previous="0.3.9")
    stage(home, "0.3.9", NOW)        # older: never offered
    stage(home, "0.4.0", NOW)        # the running one
    _, rows = rows_of(core)
    assert diag.UPDATE_ID not in rows
    stage(home, "0.5.0", NOW)
    stage(home, "0.6.0-rc.1", NOW)
    stage(home, "0.6.0", NOW)
    switch.record_skip(home, "0.6.0", "test", now=stamp(NOW))
    facts = core.diag_facts(NOW)
    assert facts["install"]["staged"]["version"] == "0.6.0-rc.1"
    # a staged document that names another version is not used
    folder = homemod.layout(home)["staged"]
    (folder / "0.7.0.json").write_text(json.dumps({"version": "0.8.0"}), encoding="ascii")
    assert core.diag_facts(NOW)["install"]["staged"]["version"] == "0.6.0-rc.1"
    # exactly one update line
    v, _ = rows_of(core)
    assert [x["id"] for x in v["checks"]].count(diag.UPDATE_ID) == 1


# -- the rollback line -------------------------------------------------------

def test_rolled_back_version_gives_one_line_with_the_fix(home, core):
    marker(home, "0.4.0")
    switch.add_line(home, "rolled back from 0.5.0 to 0.4.0 (no health answer)",
                    "rollback", switch.ROLLED_BACK, "0.4.0", "0.5.0",
                    now=stamp(NOW - HOUR))
    stage(home, "0.5.0", NOW)  # a leftover: the rollback line wins
    switch.record_skip(home, "0.5.0", "no health answer", now=stamp(NOW - HOUR))
    v, rows = rows_of(core)
    r = rows[diag.UPDATE_ID]
    assert r["status"] == diag.FAIL and r["fix"] == diag.FIX_ROLLBACK
    assert r["detail"] == ("Version 0.5.0 did not work, so AshLight went back to "
                           "0.4.0. It won't offer 0.5.0 again.")
    assert [x["id"] for x in v["checks"]].count(diag.UPDATE_ID) == 1
    assert "Last update: went back from 0.5.0 to 0.4.0" in rows[diag.INSTALL_ID]["detail"]
    assert "Fix: " + diag.FIX_ROLLBACK in v["report"]
    # it clears by itself after ROLLBACK_SHOWN_S
    later = NOW + diag.ROLLBACK_SHOWN_S
    _, rows = rows_of(core, now=later)
    assert diag.UPDATE_ID not in rows


def test_a_rollback_to_another_version_is_stale(home, core):
    marker(home, "0.6.0", previous="0.4.0")
    switch.add_line(home, "rolled back", "rollback", switch.ROLLED_BACK, "0.4.0",
                    "0.5.0", now=stamp(NOW - HOUR))
    _, rows = rows_of(core)
    assert diag.UPDATE_ID not in rows


def test_update_report_words():
    words = {
        ("update", "staged", "0.5.0", "0.4.0"): "0.5.0 downloaded and checked",
        ("update", "failed", "0.5.0", "0.4.0"): "a new version failed its checks, nothing changed",
        ("update", "deferred", None, "0.4.0"): "waiting until the game is idle",
        ("update", "refused", None, None): "refused, nothing changed",
        ("apply", "switched", "0.5.0", "0.4.0"): "switched from 0.4.0 to 0.5.0",
        ("apply", "failed", "0.5.0", "0.4.0"): "switching failed, nothing changed",
        ("rollback", "rolled back", "0.4.0", "0.5.0"): "went back from 0.5.0 to 0.4.0",
        ("rollback", "failed", None, "0.5.0"): "going back failed",
        ("confirm", "confirmed", "0.5.0", "0.4.0"): "0.5.0 started fine",
    }
    for (action, status, new, old), text in words.items():
        last = {"action": action, "status": status, "version": new, "from": old}
        assert diag._last_text(last) == text, (action, status)
    assert diag._last_text({"action": "apply", "status": "busy"}) is None
    assert diag._last_text({"action": "other", "status": "staged"}) is None
    assert diag._last_text(None) is None


def test_update_run_report_is_the_last_result(home, core):
    marker(home, "0.4.0", previous="0.3.9")
    update.write_report(home, {"schema": update.REPORT_SCHEMA, "kind": "update",
                               "from": "0.4.0", "version": "0.5.0",
                               "status": update.STAGED, "stage": "stage",
                               "reason": ""}, now=stamp(NOW - HOUR))
    last = core.diag_facts(NOW)["install"]["last"]
    assert last == {"action": "update", "status": "staged", "version": "0.5.0",
                    "from": "0.4.0", "at": NOW - HOUR}


# -- the copied report -------------------------------------------------------

def test_report_carries_mode_version_previous_and_last_result(home, core, tmp_path):
    marker(home, "0.4.0", previous="0.3.9")
    stage(home, "0.5.0", NOW + 20 * HOUR)
    # a free-text reason with a path never reaches a row or the report
    leak = str(home / "app" / "0.5.0")
    update.write_report(home, {"schema": update.REPORT_SCHEMA, "kind": "update",
                               "from": "0.4.0", "version": "0.5.0",
                               "status": update.STAGED, "stage": "stage",
                               "reason": leak, "steps": {"gate": leak}},
                        now=stamp(NOW - 3 * HOUR))
    text = route.build(core, now=NOW)
    lines = text.splitlines()
    # right under the header fields (OS, Python, Electron, counters)
    assert [ln.split(":")[0] for ln in lines[1:5]] == [
        rep.FIELD_OS, rep.FIELD_PYTHON, rep.FIELD_ELECTRON, rep.FIELD_COUNTERS]
    assert lines[5] == ("[ok] Installed copy: Version 0.4.0, previous 0.3.9 kept. "
                        "Last update: 0.5.0 downloaded and checked, 3 h ago.")
    assert lines[6].startswith("[note] Update: Version 0.5.0 is ready. It starts the "
                               "first time you open AshLight after ")
    # no path, user, home name or identifier
    for bad in (str(tmp_path), str(home), "Scratch Home", leak, "3.12.7", "39.2.7"):
        assert bad not in text, bad
    for ln in lines[5:7]:
        assert "\\" not in ln and "/" not in ln, ln
    assert text.isascii()


def test_values_with_path_text_never_reach_a_row(home, core):
    marker(home, "0.4.0")
    path = homemod.layout(home)["reports"]
    path.mkdir(parents=True, exist_ok=True)
    doc = {"switch": {"action": "apply", "status": "switched",
                      "version": "..\\..\\x", "from": "0.3.9", "at": "nonsense"}}
    (path / "last-update.json").write_text(json.dumps(doc), encoding="ascii")
    last = core.diag_facts(NOW)["install"]["last"]
    assert last == {"action": "apply", "status": "switched", "version": None,
                    "from": "0.3.9", "at": None}
    _, rows = rows_of(core)
    assert rows[diag.INSTALL_ID]["detail"] == "Version 0.4.0, no earlier version kept."
    doc["switch"]["status"] = "Q" + ":" + "\\" + "temp"  # built from parts
    (path / "last-update.json").write_text(json.dumps(doc), encoding="ascii")
    assert core.diag_facts(NOW)["install"]["last"] is None


def test_the_core_only_reads_the_home(home, core):
    marker(home, "0.4.0", previous="0.3.9")
    stage(home, "0.5.0", NOW)
    switch.add_line(home, "x", "rollback", switch.ROLLED_BACK, "0.4.0", "0.5.0",
                    now=stamp(NOW - HOUR))

    def snap():
        return {str(p.relative_to(home)): p.read_bytes()
                for p in sorted(home.rglob("*")) if p.is_file()}
    before = snap()
    for _ in range(3):
        rows_of(core)
    assert snap() == before
