"""AUTO-17 (W12 of docs/plan/06, REFRESH-SOURCE): the refresh watch source
tools/watch_sources/refresh.py and its templates
ops/loop/watch_rows/refresh.json.

Hermetic: the source file is copied into a tmp folder and run through the
tools/upstream_watch.py frame with a fake clock on a scratch root. The three
tools (docs_fresh stale, shots check, release notes --count) answer through
an injected runner (ctx["refresh_runner"]); no 'live' in ctx, so no
subprocess starts. The frame's transport refuses every request."""

import datetime as dt
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import upstream_watch as uw  # noqa: E402
import watch_rows  # noqa: E402

SRC = ROOT / "tools" / "watch_sources" / "refresh.py"
TEMPLATE = ROOT / "ops" / "loop" / "watch_rows" / "refresh.json"
DOCS, SHOTS, NOTES = "tools/docs_fresh.py", "tools/shots.py", "tools/release.py"

ROWS = """# Roadmap

- [ ] SOME-ROW (build) An unrelated open row. ACCEPT: it passes.
"""
REL_PREP_ROW = """- [ ] REL-PREP-3 (review) Prepare release 3. ACCEPT: the notes pass.
"""


def _at(y, m, d, h=12):
    return dt.datetime(y, m, d, h, 0).timestamp()


DAY = 86400.0
T0 = _at(2026, 11, 21, 9)


class Runner:
    """The three tools' answers by tool path; None means the tool idles."""

    def __init__(self, docs=(0, ""), shots=(0, "shots: fresh"), notes=(0, "0\n")):
        self.answers = {DOCS: docs, SHOTS: shots, NOTES: notes}
        self.calls = []

    def __call__(self, root, argv):
        self.calls.append(list(argv))
        return self.answers.get(argv[0])


def _root(tmp_path, roadmap=ROWS, tools=(DOCS, SHOTS, NOTES)):
    root = tmp_path / "repo"
    files = {
        "ROADMAP.md": roadmap,
        "ops/loop/watch_rows/refresh.json": TEMPLATE.read_text(encoding="ascii"),
        "config/local.json": json.dumps({"web_data": False}) + "\n",
    }
    for rel in tools:
        files[rel] = "# placeholder\n"
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("ascii"))
    return root


def _sources(tmp_path):
    d = tmp_path / "sources"
    d.mkdir(exist_ok=True)
    shutil.copyfile(SRC, d / "refresh.py")
    return d


def _tick(root, d, now, runner, requests=None):
    def refuse(method, url, headers, body=None):
        if requests is not None:
            requests.append(url)
        raise AssertionError(f"the refresh source made a request: {url}")
    return uw.run_due(root, now, fetch=refuse, directory=d,
                      ctx={"root": root, "refresh_runner": runner})


def _kinds(root):
    return [(f["kind"], f["key"], f["tokens"]) for f in uw.pending(root)]


def _render(root, kind, tokens, today):
    table = watch_rows.load(root)
    row_id, text = watch_rows.render(table, kind, tokens, today)
    assert row_id, text
    return row_id, text


def _hold(root, prefixes, age_s=60.0, now=T0):
    p = root / "ops/loop/control/wave_owned.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"wave": 21, "prefixes": prefixes, "time": now - age_s}),
                 encoding="ascii")


# ---------------------------------------------------------------- tests

def test_manifest_stale_for_3_days_files_one_shots_row(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    run = Runner(shots=(1, "shots: stale (UI sources or fixture changed)"))
    for day in range(3):
        _tick(root, d, T0 + day * DAY, run)
        assert uw.pending(root) == [], day
    _tick(root, d, T0 + 3 * DAY, run)
    assert _kinds(root) == [("shots", "shots:20261124", {"SINCE": "2026-11-21"})]
    row_id, text = _render(root, "shots", {"SINCE": "2026-11-21"}, "2026-11-24")
    assert row_id == "SHOTS-20261124"
    assert text.startswith("- [ ] SHOTS-20261124 (data) The screenshot manifest is stale "
                           "since 2026-11-21: run tools/shots.py render")
    assert text.endswith("SOURCE: watch refresh shots, filed 2026-11-24.")
    # the same tick day again and the next days add nothing
    _tick(root, d, T0 + 3 * DAY + 600, run)
    _tick(root, d, T0 + 4 * DAY, run)
    assert len(uw.pending(root)) == 1

    # a fresh answer resets the stale clock
    root2 = _root(tmp_path / "b")
    run2 = Runner(shots=(1, "stale"))
    _tick(root2, d, T0, run2)
    _tick(root2, d, T0 + DAY, run2)
    run2.answers[SHOTS] = (0, "fresh")
    _tick(root2, d, T0 + 2 * DAY, run2)
    run2.answers[SHOTS] = (1, "stale")
    for day in range(3, 6):
        _tick(root2, d, T0 + day * DAY, run2)
    assert uw.pending(root2) == []
    _tick(root2, d, T0 + 6 * DAY, run2)
    assert _kinds(root2) == [("shots", "shots:20261127", {"SINCE": "2026-11-24"})]


def test_no_shots_row_while_a_wave_holds_web(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    run = Runner(shots=(1, "stale"))
    for day in range(6):
        now = T0 + day * DAY
        _hold(root, ["web", "tools/x"], now=now)
        _tick(root, d, now, run)
    assert uw.pending(root) == []
    # a hold below web/ holds it too
    _hold(root, ["./web/parts/"], now=T0 + 6 * DAY)
    _tick(root, d, T0 + 6 * DAY, run)
    assert uw.pending(root) == []
    # a hold on other folders does not, and the stale clock kept running
    _hold(root, ["webby", "app/test"], now=T0 + 7 * DAY)
    _tick(root, d, T0 + 7 * DAY, run)
    assert _kinds(root) == [("shots", "shots:20261128", {"SINCE": "2026-11-21"})]

    # a stale hold file (over 48 h) is reported elsewhere, never obeyed
    root2 = _root(tmp_path / "b")
    run2 = Runner(shots=(1, "stale"))
    for day in range(4):
        now = T0 + day * DAY
        _hold(root2, ["web"], age_s=49 * 3600, now=now)
        _tick(root2, d, now, run2)
    assert [k for k, _, _ in _kinds(root2)] == ["shots"]


def test_10_rows_and_30_days_file_one_rel_due_row(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    run = Runner(notes=(0, "10 2026-10-22\n"))
    _tick(root, d, T0, run)
    assert _kinds(root) == [("reldue", "notes:20261121", {"N": "10", "D": "30"})]
    assert [NOTES, "notes", "--count"] in run.calls
    row_id, text = _render(root, "reldue", {"N": "10", "D": "30"}, "2026-11-21")
    assert row_id == "REL-DUE-20261121"
    assert text.startswith("- [ ] REL-DUE-20261121 (review) 10 rows merged in 30 days "
                           "since the last tag with no release row open")
    assert "BLOCKED: session. SOURCE: watch refresh notes, filed 2026-11-21." in text
    for word in ("bump", "push", "git tag"):
        assert word not in text.lower().replace("last tag", "")
    _tick(root, d, T0 + DAY, run)
    assert len(uw.pending(root)) == 1

    # large values are capped at the token bounds
    root2 = _root(tmp_path / "b")
    _tick(root2, d, T0, Runner(notes=(0, "123456 2020-01-01")))
    assert _kinds(root2) == [("reldue", "notes:20261121", {"N": "9999", "D": "999"})]
    _render(root2, "reldue", {"N": "9999", "D": "999"}, "2026-11-21")


def test_9_rows_or_29_days_or_an_open_rel_prep_file_none(tmp_path):
    d = _sources(tmp_path)
    cases = {
        "nine": (ROWS, "9 2026-01-01"),
        "days29": (ROWS, "40 2026-10-23"),
        "prep": (ROWS + REL_PREP_ROW, "40 2026-01-01"),
        "notag": (ROWS, "0"),
        "badshape": (ROWS, "forty rows"),
    }
    for name, (roadmap, out) in cases.items():
        root = _root(tmp_path / name, roadmap=roadmap)
        _tick(root, d, T0, Runner(notes=(0, out)))
        assert uw.pending(root) == [], name
    # a tool that refuses the option (exit 2) or is absent idles the kind
    root = _root(tmp_path / "rc2")
    _tick(root, d, T0, Runner(notes=(2, "usage: release.py\n")))
    assert uw.pending(root) == []
    root = _root(tmp_path / "absent", tools=(DOCS, SHOTS))
    run = Runner(notes=(0, "40 2026-01-01"))
    lines = _tick(root, d, T0, run)
    assert uw.pending(root) == []
    assert not any(c[0] == NOTES for c in run.calls)
    assert not any("failed" in ln for ln in lines), lines
    assert uw.load_state(root)["sources"]["refresh"]["fails"] == 0


def test_31_day_old_marker_files_one_docs_fresh_row(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    out = "docs/research/0001-x.md:12: 2026-10-21 (31 days): UNVERIFIED as of 2026-10-21\n"
    run = Runner(docs=(1, out))
    _tick(root, d, T0, run)
    assert _kinds(root) == [("docsfresh", "docs:20261121", {"N": "1"})]
    assert [DOCS, "stale", "--today", "2026-11-21"] in run.calls
    row_id, text = _render(root, "docsfresh", {"N": "1"}, "2026-11-21")
    assert row_id == "DOCS-FRESH-20261121"
    assert text == ("- [ ] DOCS-FRESH-20261121 (data) 1 dated markers in docs are older "
                    "than 30 days: resolve or re-date each with a source. ACCEPT: "
                    "docs_fresh.py stale prints 0. ZERO-CLICK: the loop works it. "
                    "SOURCE: watch refresh docs, filed 2026-11-21.")
    # no marker (exit 0, no line) files nothing
    root2 = _root(tmp_path / "b")
    _tick(root2, d, T0, Runner(docs=(0, "")))
    assert uw.pending(root2) == []


def test_each_kind_files_at_most_one_row_per_7_days(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    run = Runner(docs=(1, "a\nb\n"), shots=(1, "stale"), notes=(0, "12 2026-01-01"))
    for day in range(15):
        _tick(root, d, T0 + day * DAY, run)
    found = _kinds(root)
    by_kind = {}
    for kind, key, _ in found:
        by_kind.setdefault(kind, []).append(key)
    assert by_kind["docsfresh"] == ["docs:20261121", "docs:20261128", "docs:20261205"]
    assert by_kind["reldue"] == ["notes:20261121", "notes:20261128", "notes:20261205"]
    # shots waits 3 stale days first, then once per 7 days
    assert by_kind["shots"] == ["shots:20261124", "shots:20261201"]
    # one tick day runs once: a second tick the same day calls no tool
    calls = len(run.calls)
    _tick(root, d, T0 + 14 * DAY + 3600, run)
    assert len(run.calls) == calls
    # every queued finding renders as one row through its template
    for kind, key, tokens in found:
        day = key.split(":")[1]
        _render(root, kind, tokens, f"{day[:4]}-{day[4:6]}-{day[6:]}")


def test_source_makes_no_request(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    requests = []
    run = Runner(docs=(1, "a\n"), shots=(1, "stale"), notes=(0, "12 2026-01-01"))
    # web data on or off, the local source runs and asks for nothing
    for day, web in enumerate((False, True, False, True)):
        (root / "config/local.json").write_text(json.dumps({"web_data": web}) + "\n",
                                                encoding="ascii")
        lines = _tick(root, d, T0 + day * DAY, run, requests)
        assert not any("failed" in ln for ln in lines), lines
    assert requests == []
    src = uw.normalize(uw.watch_sources.load(d)[0])
    assert src["local"] and src["hosts"] == [] and src["urls"] == []
    assert not uw.is_network(src)

    # the fetch the frame hands a local source refuses every URL
    import importlib.util
    spec = importlib.util.spec_from_file_location("refresh_probe", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    asked = []

    def fetch(url, etag=None):
        asked.append(url)
        raise AssertionError(url)
    mod.check({}, T0, fetch, {"root": _root(tmp_path / "c"), "refresh_runner": run})
    assert asked == []

    # no root and no 'live': nothing read, no runner, no subprocess
    blind = Runner()
    assert mod.check({}, T0, fetch, {"refresh_runner": blind}) == []
    assert blind.calls == []
    assert mod._runner({}) is None
    assert mod._runner({"live": True}) is mod.default_runner
