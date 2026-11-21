"""RUN-LEDGER-REPORT (F-061, OPEN-01, OPEN-02, LIVE-1, TEST-LIVE-CLICKS;
decision 0071): tools/live1_report.py reads the parse ledger file and
prints one verdict per LIVE-1 item, the five read-back fields and the
waystone shape. Fixture ledgers are built through the real ledger code
(logshapes.Ledger, plug/ledger.Wire) into tmp_path; the live runtime dir
and Client.txt are never read.
"""

import json
import subprocess
import sys
from pathlib import Path

from server.al import logshapes
from server.al.plug import ledger as ledger_mod

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import live1_report  # noqa: E402

P = "2026/11/17 10:00:00 1 abc [INFO Client 1] "
T0 = 1795000000.0

WAYSTONE = """Item Class: Waystones
Rarity: Rare
Doom Trail
Waystone (Tier 15)
--------
Waystone Tier: 15
Revives Available: 0
Monster Pack Size: +12% (augmented)
--------
Item Level: 79
--------
Monsters deal 28(20-30)% of Damage as Extra Fire
"""


class _Tailer:
    tailer = {"ledger": True}


class _Core:
    state = _Tailer()


def _wire():
    return ledger_mod.Wire(_Core())


def _write(tmp_path, wire, name="logshapes.json"):
    path = tmp_path / name
    path.write_text(wire.dumps() + "\n", encoding="ascii")
    return path


def _ev(type_, **kw):
    ev = {"type": type_}
    ev.update(kw)
    return ev


def _report(path):
    return live1_report.build(path)


def _row(doc, item):
    return next(it for it in doc["items"] if it["item"] == item)


def test_each_live1_item_gets_one_verdict_line(tmp_path, capsys):
    wire = _wire()
    led = wire.ledger
    led.observe(P + ": Emberwright has been slain.", _ev("death"), now=T0)
    led.observe(P + "@From Someone: hi", _ev("whisper_in", text="hi"), now=T0)
    # A plain line naming a party, seen twice a minute apart: NEW SHAPE.
    line = P + "Your party is full now"
    led.observe(line, None, now=T0)
    led.observe(line, None, now=T0 + 120)
    path = _write(tmp_path, wire)

    assert live1_report.main(["--file", str(path)]) == 0
    out = capsys.readouterr().out
    items = list(logshapes.LIVE1_ITEMS) + [live1_report.WAYSTONE]
    for item in items:
        row = live1_report.ROW_PREFIX.get(item, "LIVE-1-" + item)
        hits = [ln for ln in out.splitlines() if ln.strip().startswith(row + ":")]
        assert len(hits) == 1, (row, out)
        assert any(v in hits[0] for v in (live1_report.VERIFIED,
                                          live1_report.NEW_SHAPE,
                                          live1_report.NOT_SEEN))
    doc = _report(path)
    assert [it["item"] for it in doc["items"]] == items
    assert _row(doc, "DEATH")["verdict"] == live1_report.VERIFIED
    assert _row(doc, "WHISPER")["verdict"] == live1_report.VERIFIED
    assert _row(doc, "PARTY")["verdict"] == live1_report.NEW_SHAPE
    assert _row(doc, "GUILD")["verdict"] == live1_report.NOT_SEEN
    assert _row(doc, "DEATH")["hits"] == {"death": 1}
    assert "LIVE-1-DEATH: VERIFIED live (death 1;" in out


def test_area_id_hint_is_a_new_shape(tmp_path):
    wire = _wire()
    for t in (T0, T0 + 3600):
        wire.ledger.observe(P + "Generating level 70 area \"MapNewThing\"",
                            _ev("area_generated", area_id="MapNewThing"), now=t)
    doc = _report(_write(tmp_path, wire))
    if logshapes.area_class("MapNewThing") == "other":
        assert _row(doc, "MAP")["verdict"] == live1_report.NEW_SHAPE
        assert _row(doc, "MAP")["area_ids"] == ["MapNewThing"]
    else:
        assert _row(doc, "MAP")["verdict"] == live1_report.VERIFIED


def test_five_readback_fields_are_listed(tmp_path, capsys):
    wire = _wire()
    wire.readback["zone"] = True
    wire.readback["level"] = True
    path = _write(tmp_path, wire)
    assert live1_report.main(["--file", str(path)]) == 0
    out = capsys.readouterr().out
    assert ledger_mod.READBACK == ("zone", "character", "level", "act", "session_timer")
    for k in ledger_mod.READBACK:
        want = "seen" if k in ("zone", "level") else "not seen"
        assert f"  {k}: {want}\n" in out
    doc = _report(path)
    assert doc["readback"] == {"zone": True, "character": False, "level": True,
                               "act": False, "session_timer": False}


def test_new_shape_needs_two_sightings(tmp_path):
    line = P + "Your guild has a new thing"
    wire = _wire()
    wire.ledger.observe(line, None, now=T0)
    once = _report(_write(tmp_path, wire, "once.json"))
    assert _row(once, "GUILD")["verdict"] == live1_report.NOT_SEEN
    assert once["new_shapes"] == []
    assert once["pending_shapes"] == 1

    wire.ledger.observe(line, None, now=T0 + 10)   # too soon
    soon = _report(_write(tmp_path, wire, "soon.json"))
    assert _row(soon, "GUILD")["verdict"] == live1_report.NOT_SEEN

    wire.ledger.observe(line, None, now=T0 + logshapes.CONFIRM_S + 1)
    twice = _report(_write(tmp_path, wire, "twice.json"))
    assert _row(twice, "GUILD")["verdict"] == live1_report.NEW_SHAPE
    assert len(twice["new_shapes"]) == 1
    assert twice["new_shapes"][0]["items"] == ["GUILD"]
    assert twice["pending_shapes"] == 0


def test_json_output_holds_masked_shapes_only(tmp_path):
    secret = "Zyxqorvath"
    wire = _wire()
    line = P + f"Your guild {secret} met /Users/{secret} at 10.1.2.3"
    wire.ledger.observe(line, None, now=T0)
    wire.ledger.observe(line, None, now=T0 + 120)
    assert wire.press(WAYSTONE) is not None
    doc = json.loads(wire.dumps())
    # A tampered file: raw text in a shape, a waystone line and an extra key.
    doc["shapes"].append(["sys", f"{secret} has been slain", 2, "2026-11-17T10",
                          "2026-11-17T11", True])
    doc["waystone"].append([[f"Waystone Tier: {secret}"], 1, "2026-11-17T10",
                            "2026-11-17T10"])
    doc["raw"] = secret
    path = tmp_path / "logshapes.json"
    path.write_text(json.dumps(doc), encoding="ascii")

    proc = subprocess.run([sys.executable, str(ROOT / "tools" / "live1_report.py"),
                           "--json", "--file", str(path)],
                          capture_output=True, text=True, cwd=str(tmp_path), timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert secret not in proc.stdout
    assert "Users" not in proc.stdout and "10.1.2.3" not in proc.stdout
    out = json.loads(proc.stdout)
    assert out["ledger"] == "found"
    assert out["new_shapes"], out
    for s in out["new_shapes"]:
        assert logshapes.is_safe_shape(s["shape"])
    assert out["waystone"]
    for w in out["waystone"]:
        assert w["lines"]
        assert all(ledger_mod.is_safe_line(x) for x in w["lines"])
    assert "waystone tier: <n>" in out["waystone"][0]["lines"]
    assert _row(out, live1_report.WAYSTONE)["verdict"] == live1_report.VERIFIED
    assert proc.stdout.isascii()


def test_missing_ledger_file_prints_not_seen_and_exits_0(tmp_path):
    path = tmp_path / "nope" / "logshapes.json"
    proc = subprocess.run([sys.executable, str(ROOT / "tools" / "live1_report.py"),
                           "--file", str(path)],
                          capture_output=True, text=True, cwd=str(tmp_path), timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "ledger: missing" in proc.stdout
    rows = [ln for ln in proc.stdout.splitlines() if ln.startswith("  LIVE-")]
    assert len(rows) == len(logshapes.LIVE1_ITEMS) + 1
    assert all(ln.endswith(": " + live1_report.NOT_SEEN) for ln in rows)
    for k in ledger_mod.READBACK:
        assert f"  {k}: not seen" in proc.stdout

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="ascii")
    doc = _report(bad)
    assert doc["ledger"] == "unreadable"
    assert all(it["verdict"] == live1_report.NOT_SEEN for it in doc["items"])

    proc = subprocess.run([sys.executable, str(ROOT / "tools" / "live1_report.py"),
                           "--json", "--file", str(path)],
                          capture_output=True, text=True, cwd=str(tmp_path), timeout=60)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["ledger"] == "missing"


def test_default_path_follows_runtime_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AL_RUNTIME_DIR", str(tmp_path))
    assert live1_report.default_path() == tmp_path.resolve() / "logshapes.json"
