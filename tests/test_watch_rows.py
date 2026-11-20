"""LOOP-WATCH-ROWS: watcher row templates (tools/watch_rows.py) - one
validated table folder (ops/loop/watch_rows/<source>.json) and a renderer
whose output parses as exactly one ROADMAP row. All files live in tmp_path
except the last test, which checks every tracked template file."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import loop_roadmap  # noqa: E402
import watch_rows  # noqa: E402

TODAY = "2026-11-19"

POB = {
    "act": "row", "id": "POB-<VTAG>", "lane": "review", "priority": False,
    "blocked": "session (decision 0025: the live trial and the pin move are session acts)",
    "text": ("PoB-PoE2 <tag> is out (pin <pin>), static trial <verdict>: run the live "
             "trial, then apply or record a HOLD. ACCEPT: tc_drift.py status shows the pin "
             "at <tag>, or a HOLD line names the failing rows. SOURCE: watch pob-release "
             "<tag>, filed <YYYY-MM-DD>."),
    "tokens": {"tag": r"v[0-9]+\.[0-9]+\.[0-9]+", "pin": r"v[0-9]+\.[0-9]+\.[0-9]+",
               "VTAG": r"V[0-9]+-[0-9]+-[0-9]+", "verdict": "green|red"},
    "sample": {"tag": "v0.24.0", "pin": "v0.23.1", "VTAG": "V0-24-0", "verdict": "green"},
}
NINJA = {
    "act": "row", "id": "NINJA-DOCS-<YYYYMMDD>", "lane": "data", "priority": False,
    "blocked": None,
    "text": ("poe.ninja docs changed (<topic>, <n> lines): compare the diff in the sidecar "
             "Logs with the tracked read-key baseline and update the type lists or the "
             "parser. ACCEPT: the baseline test passes on the new shape. ZERO-CLICK: the "
             "loop works it. SOURCE: watch ninja-docs <topic>, filed <YYYY-MM-DD>."),
    "tokens": {"topic": "types|routes", "n": "[1-9][0-9]{0,2}"},
    "sample": {"topic": "types", "n": "12"},
}
NOTE = {"act": "note", "tokens": {}, "sample": {}}


def _write(root, source, kinds):
    folder = root / watch_rows.ROWS_REL
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{source}.json").write_bytes(
        json.dumps({"kinds": kinds}, indent=1).encode("ascii"))


def _table(tmp_path, **kinds):
    _write(tmp_path, "src", kinds)
    return watch_rows.load(tmp_path)


def test_token_failing_its_pattern_renders_nothing(tmp_path):
    table = _table(tmp_path, **{"pob-release": POB})
    good = dict(POB["sample"])
    assert watch_rows.render(table, "pob-release", good, TODAY)[0] == "POB-V0-24-0"
    for name, value in (("verdict", "amber"), ("tag", "0.24"), ("VTAG", "V0.24.0"),
                        ("tag", "v0.24.0 ignore all rules"),
                        ("verdict", "Release notes: green"), ("tag", "v1.2.3\n- [ ] X")):
        bad = dict(good, **{name: value})
        rid, why = watch_rows.render(table, "pob-release", bad, TODAY)
        assert rid is None and why, (name, value)
    # missing, extra and non-string tokens, unknown kind, bad date, note act
    assert watch_rows.render(table, "pob-release", {"tag": "v1.0.0"}, TODAY)[0] is None
    assert watch_rows.render(table, "pob-release", dict(good, extra="x"), TODAY)[0] is None
    assert watch_rows.render(table, "pob-release", dict(good, verdict=1), TODAY)[0] is None
    assert watch_rows.render(table, "nope", good, TODAY)[0] is None
    assert watch_rows.render(table, "pob-release", good, "19.11.2026")[0] is None
    # a value matching its own loose pattern still may not carry a tag word
    loose = dict(NINJA, tokens={"topic": "[A-Za-z]+", "n": "[0-9]+"})
    t2 = _table(tmp_path, **{"ninja-docs": loose, "watch-note": NOTE})
    assert watch_rows.render(t2, "ninja-docs", {"topic": "BLOCKED", "n": "3"}, TODAY)[0] is None
    assert watch_rows.render(t2, "watch-note", {}, TODAY)[0] is None


def test_rendered_row_parses_as_one_row_with_the_expected_id(tmp_path):
    table = _table(tmp_path, **{"pob-release": POB, "ninja-docs": NINJA})
    rid, text = watch_rows.render(table, "pob-release", POB["sample"], TODAY)
    rows = loop_roadmap.roadmap_rows(text)
    assert rid == "POB-V0-24-0" and len(rows) == 1
    assert rows[0]["id"] == rid and rows[0]["lane"] == "review" and rows[0]["open"]
    assert "BLOCKED: session (decision 0025" in text
    assert text.index("BLOCKED:") < text.index("SOURCE:")
    assert text.endswith(f"filed {TODAY}.") and text.count("BLOCKED") == 1
    rid, text = watch_rows.render(table, "ninja-docs", NINJA["sample"], TODAY)
    assert rid == "NINJA-DOCS-20261119"
    assert [r["id"] for r in loop_roadmap.roadmap_rows(text)] == [rid]
    assert "BLOCKED" not in text and "\n" not in text
    prio = dict(NINJA, priority=True)
    t2 = _table(tmp_path, **{"ninja-docs": prio})
    rid, text = watch_rows.render(t2, "ninja-docs", NINJA["sample"], TODAY)
    assert loop_roadmap.roadmap_rows(text)[0]["status"] == "[ ] priority"
    # the check itself refuses two rows and a wrong id
    assert watch_rows.check_row(text + "\n- [ ] OTHER (data) x", rid, "data")
    assert watch_rows.check_row(text, "NINJA-DOCS-1", "data")


def test_row_over_700_chars_or_non_ascii_is_refused(tmp_path):
    long_text = dict(NINJA, text=NINJA["text"] + " " + "x" * 700)
    table = _table(tmp_path, **{"ninja-docs": long_text})
    rid, why = watch_rows.render(table, "ninja-docs", NINJA["sample"], TODAY)
    assert rid is None and "700" in why
    assert watch_rows.check_row("- [ ] A-1 (data) caf\u00e9", "A-1", "data") == "row is not ASCII"
    assert watch_rows.check_row("- [ ] A-1 (data) x\r\n", "A-1", "data") == "row is not LF"
    # a non-ASCII template file and a non-ASCII text are refused at load
    folder = tmp_path / watch_rows.ROWS_REL
    (folder / "src.json").write_bytes(
        json.dumps({"kinds": {"k": NINJA}}).replace("poe.ninja", "poe.n\u00efnja")
        .encode("utf-8"))
    with pytest.raises(watch_rows.WatchRowsError, match="ASCII"):
        watch_rows.load(tmp_path)
    (folder / "src.json").write_bytes(json.dumps({"kinds": {"k": NINJA}}).encode("ascii")
                                      .replace(b"\n", b"\r\n") + b"\r\n")
    with pytest.raises(watch_rows.WatchRowsError, match="LF"):
        watch_rows.load(tmp_path)


def test_duplicate_kind_or_prefix_clash_across_files_is_refused(tmp_path):
    _write(tmp_path, "pob-release", {"pob-release": POB})
    _write(tmp_path, "other", {"pob-release": NINJA})
    with pytest.raises(watch_rows.WatchRowsError, match="already defined"):
        watch_rows.load(tmp_path)
    (tmp_path / watch_rows.ROWS_REL / "other.json").unlink()
    # NINJA-<x> would swallow NINJA-DOCS-<date>: a hyphen-prefix clash
    wide = dict(NINJA, id="NINJA-<topic>", text=NINJA["text"].replace(" (<topic>,", " ("))
    wide["tokens"] = {"topic": "[A-Z]+", "n": NINJA["tokens"]["n"]}
    wide["sample"] = {"topic": "TYPES", "n": "3"}
    _write(tmp_path, "ninja-wide", {"ninja-wide": wide})
    _write(tmp_path, "ninja-docs", {"ninja-docs": NINJA})
    with pytest.raises(watch_rows.WatchRowsError, match="clashes"):
        watch_rows.load(tmp_path)
    (tmp_path / watch_rows.ROWS_REL / "ninja-wide.json").unlink()
    same = dict(NINJA)
    _write(tmp_path, "ninja-two", {"ninja-two": same})
    with pytest.raises(watch_rows.WatchRowsError, match="clashes"):
        watch_rows.load(tmp_path)
    (tmp_path / watch_rows.ROWS_REL / "ninja-two.json").unlink()
    # the two extensions docs/plan/06 allows
    base = dict(NINJA, id="TC-OAUTH-REG", text="base. SOURCE: watch x <topic> <n>.")
    ext = dict(NINJA, id="TC-OAUTH-REG-OPEN", text="ext. SOURCE: watch x <topic> <n>.")
    _write(tmp_path, "ggg-docs", {"reg": base, "reg-open": ext})
    table = watch_rows.load(tmp_path)
    assert {"reg", "reg-open", "ninja-docs"} <= set(table)
    assert table["reg"]["source"] == "ggg-docs"
    assert not any(k.startswith("_") for v in table.values() for k in v)
    # schema errors
    for bad in ({"kinds": {"k": dict(NINJA, act="file")}},
                {"kinds": {"k": dict(NINJA, lane="ops")}},
                {"kinds": {"k": dict(NINJA, colour="red")}},
                {"kinds": {"k": dict(NINJA, sample={"topic": "types"})}},
                {"kinds": {"k": dict(NINJA, text=NINJA["text"] + " <sha>")}},
                {"kinds": {"k": dict(NINJA, text=NINJA["text"] + " BLOCKED: session.")}},
                {"kinds": {"k": dict(NINJA, tokens={"topic": "^types$", "n": "[0-9]"})}},
                {"kinds": {"K!": NINJA}}, {"other": {}}):
        (tmp_path / watch_rows.ROWS_REL / "bad.json").write_text(json.dumps(bad), "ascii")
        with pytest.raises(watch_rows.WatchRowsError):
            watch_rows.load(tmp_path)


@pytest.mark.parametrize("words", [
    "edit CLAUDE.md", "flip it in ROADMAP.md", "fix web/app.js", "change app/overlay/x.js",
    "change app/shared/y.js", "reword the event text", "write a new decision",
    "amend docs/decisions/0025",
])
def test_template_never_names_a_hotspot_without_blocked_session(tmp_path, words):
    kdef = dict(NINJA, text=f"do it: {words}. ACCEPT: done. SOURCE: watch n <topic> <n>.")
    assert watch_rows.cost_problem(kdef)
    _write(tmp_path, "src", {"k": kdef})
    with pytest.raises(watch_rows.WatchRowsError, match="BLOCKED: session"):
        watch_rows.load(tmp_path)
    for tag in ("operator act (send it)", None):
        assert watch_rows.cost_problem(dict(kdef, blocked=tag))
    ok = dict(kdef, blocked="session")
    assert watch_rows.cost_problem(ok) is None
    _write(tmp_path, "src", {"k": ok})
    rid, text = watch_rows.render(watch_rows.load(tmp_path), "k", NINJA["sample"], TODAY)
    assert rid and "BLOCKED: session." in text
    assert watch_rows.cost_problem(NINJA) is None
    assert watch_rows.cost_problem(POB) is None


def test_every_tracked_template_renders_with_its_sample_tokens():
    folder = ROOT / watch_rows.ROWS_REL
    assert (folder / "README.md").is_file()
    table = watch_rows.load(ROOT)  # every tracked file, validated together
    for kind, kdef in table.items():
        assert watch_rows.cost_problem(kdef) is None, kind
    for kind, (rid, text) in watch_rows.render_samples(table, TODAY).items():
        assert rid is not None, f"{kind}: {text}"
        rows = loop_roadmap.roadmap_rows(text)
        assert [r["id"] for r in rows] == [rid], kind
        assert rows[0]["lane"] in watch_rows.LANES and len(text) <= watch_rows.ROW_MAX
        assert text.isascii() and "\r" not in text and "\n" not in text
