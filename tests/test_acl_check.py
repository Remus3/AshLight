"""SEC-ACL-CHECK (finding F-011): at core start AshLight reads the ACLs of
the runtime dir, the AshLight folder and the sidecar root (read only, no
icacls) and the Checks card shows one row with a one-line fix while
anyone else can write to one of them. The row names the folder, never a
path.

Every ACL change here is on a pytest tmp dir; the repo, the live
ops/runtime and the live sidecar are never touched.
"""

import os
import subprocess
import threading

import pytest

from server.al import acl, diag, exepin
from server.al.core import Core

WINDOWS = pytest.mark.skipif(os.name != "nt", reason="Windows ACLs only")
USERS_SID = "S-1-5-32-545"  # the local users group: one more writer
READ_ONLY = "RX"


def _grant(path, rights, sid=USERS_SID):
    subprocess.run([str(exepin.system_tool("icacls.exe")), str(path), "/grant",
                    f"*{sid}:(OI)(CI){rights}", "/q"], check=True, capture_output=True,
                   stdin=subprocess.DEVNULL)


def _three(tmp_path):
    dirs = []
    for name in acl.AUDIT_NAMES:
        d = tmp_path / ("dir_" + name)
        d.mkdir()
        assert acl.make_private(d) is True
        dirs.append(d)
    return dirs


@WINDOWS
def test_extra_writer_yields_the_checks_note(tmp_path):
    runtime, app, sidecar = _three(tmp_path)
    _grant(app, "M")
    assert acl.others_can_write(app) is True
    assert acl.others_can_write(runtime) is False
    found = acl.audit(runtime, app, sidecar)
    assert found == ["app"]
    row = diag.check_private({"acl_open": found})
    assert row["status"] == diag.FAIL and row["fix"] == diag.FIX_PRIVATE_APP
    assert "the AshLight folder" in row["detail"]
    # a read-only grant to someone else is not a writer
    _grant(sidecar, READ_ONLY)
    assert acl.audit(runtime, app, sidecar) == ["app"]
    _grant(runtime, "W")
    assert acl.audit(runtime, app, sidecar) == ["runtime", "app"]
    # the row and the report name folders, never a path
    view = diag.view({"acl_open": acl.audit(runtime, app, sidecar)}, "1.0", now=0.0)
    r = {x["id"]: x for x in view["checks"]}["private"]
    assert r["fix"] == diag.FIX_PRIVATE_BOTH
    for text in (r["detail"], r["fix"], view["report"]):
        assert str(tmp_path) not in text and "<path>" not in text
        assert str(tmp_path).replace("\\", "/") not in text
    assert "[FIX] Private files:" in view["report"]


@WINDOWS
def test_private_dirs_add_no_row(tmp_path):
    dirs = _three(tmp_path)
    assert acl.audit(*dirs) == []
    assert diag.check_private({"acl_open": []}) is None
    ids = [r["id"] for r in diag.checks({"acl_open": acl.audit(*dirs)}, 0.0)]
    assert "private" not in ids
    # a missing or unset folder is left out, never reported open
    assert acl.audit(tmp_path / "gone", None, dirs[2]) == []


def test_audit_reads_names_in_order_and_skips_unknown(tmp_path):
    a, b, c = (tmp_path / n for n in "abc")
    for d in (a, b, c):
        d.mkdir()
    answers = {str(a): True, str(b): None, str(c): True}
    assert acl.audit(a, b, c, check=lambda p: answers[str(p)]) == ["runtime", "sidecar"]

    def boom(p):
        raise OSError("unreadable")
    assert acl.audit(a, b, c, check=boom) == []


def test_audit_runs_once_off_the_main_thread(tmp_path):
    core = Core(runtime=tmp_path, tail=False)
    # a test core starts no audit and shows no row until it injects one
    assert core.acl_open is None and core._acl_thread is None
    assert core.diag_facts()["acl_open"] is None
    calls = []

    def fake():
        calls.append(threading.current_thread())
        return ["sidecar"]
    t = core.start_acl_audit(audit=fake, delay=0)
    assert core.start_acl_audit(audit=fake, delay=0) is t
    t.join(5)
    assert not t.is_alive()
    assert len(calls) == 1 and calls[0] is not threading.main_thread()
    assert core.acl_open == ["sidecar"]
    assert core.diag_facts()["acl_open"] == ["sidecar"]
    core.tick_diag(force=True)
    rows = {r["id"]: r for r in core.state.snapshot()["diag"]["checks"]}
    assert rows["private"]["fix"] == diag.FIX_PRIVATE_SETUP
    assert str(tmp_path) not in rows["private"]["detail"]
    core.close()


def test_close_cancels_a_pending_audit(tmp_path):
    core = Core(runtime=tmp_path, tail=False)
    calls = []
    t = core.start_acl_audit(audit=lambda: calls.append(1) or ["app"], delay=30)
    core.close()
    t.join(5)
    assert not t.is_alive() and calls == [] and core.acl_open is None


def test_a_failing_audit_leaves_no_row(tmp_path):
    core = Core(runtime=tmp_path, tail=False)

    def boom():
        raise OSError("no")
    core.start_acl_audit(audit=boom, delay=0).join(5)
    assert core.acl_open is None
    core.tick_diag(force=True)
    assert "private" not in [r["id"] for r in core.state.snapshot()["diag"]["checks"]]
    core.close()
