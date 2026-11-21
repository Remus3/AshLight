"""LOOP-WATCH-POBNEXT (W3 of docs/plan/06; AUTO-05, F-030; decision 0069):
the PoB-PoE2 next-release watch source. Hermetic: the source file is copied
into a tmp folder and run through the tools/upstream_watch.py frame with a
fake transport; the tracked config/tc_pins.json is copied into a tmp root
and every state file lives under tmp_path. No socket is ever opened."""

import datetime as dt
import json
import shutil
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import loop_base  # noqa: E402
import tc_pin  # noqa: E402
import upstream_watch as uw  # noqa: E402
import watch_gate  # noqa: E402
import watch_rows  # noqa: E402
from watch_sources import pob_next  # noqa: E402

from server.al import NAME  # noqa: E402

SRC_DIR = ROOT / "tools" / "watch_sources"
NOW = dt.datetime(2026, 11, 20, 12, 0).timestamp()
DAY = 24 * 3600.0
PINS = tc_pin.load_pins(ROOT / "config" / "tc_pins.json")["pob2"]
REPO, PIN = PINS["repo"], PINS["commit"]
COMMITS = (f"https://api.github.com/repos/{REPO}/commits"
           f"?sha={pob_next.BRANCH}&per_page={pob_next.PER_PAGE}")
LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"


def _sha(n):
    return f"{n:040x}"


def _iso_z(epoch):
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Upstream:
    """A fake webfetch transport answering the two metadata URLs."""

    def __init__(self, ahead=3, release_age_d=40, release=True):
        self.calls = []
        self.ahead = ahead
        self.head_no = 100
        self.release_at = NOW - release_age_d * DAY
        self.release = release

    def move(self, by=1):
        self.ahead += by
        self.head_no += by

    def commits(self):
        newer = [{"sha": _sha(self.head_no - i),
                  "commit": {"message": "change", "committer": {"date": _iso_z(NOW)}}}
                 for i in range(self.ahead)]
        return newer + [{"sha": PIN, "commit": {"message": "release",
                                                "committer": {"date": _iso_z(NOW - 60 * DAY)}}}]

    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, dict(headers)))
        if url == COMMITS:
            return 200, {"ETag": '"c%d"' % self.head_no}, json.dumps(self.commits()).encode()
        if url == LATEST:
            if not self.release:
                return 404, {}, b'{"message": "Not Found"}'
            doc = {"tag_name": PINS["tag"], "published_at": _iso_z(self.release_at)}
            return 200, {"ETag": '"r1"'}, json.dumps(doc).encode()
        return 404, {}, b"{}"


def _root(tmp_path, web_data=True):
    root = tmp_path / "root"
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "local.json").write_text(
        json.dumps({"web_data": web_data}), encoding="utf-8")
    shutil.copyfile(ROOT / "config" / "tc_pins.json", root / "config" / "tc_pins.json")
    return root


def _sources(tmp_path):
    d = tmp_path / "sources"
    d.mkdir(exist_ok=True)
    shutil.copyfile(SRC_DIR / "pob_next.py", d / "pob_next.py")
    return d


def _run(root, d, t, now):
    return uw.run_due(root, now, fetch=t, directory=d, ctx={"root": root})


def _mine(lines):
    return [line for line in lines if "pob-next" in line]


def _queued(root, kind):
    return [f for f in uw.pending(root) if f["kind"] == kind]


def _note_text(table, finding):
    text = table[finding["kind"]]["text"]
    for k, v in finding["tokens"].items():
        text = text.replace(f"<{k}>", v)
    return text


def test_head_move_is_one_tick_line(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    t = Upstream(ahead=3, release_age_d=5)                # recent release: no row
    lines = _mine(_run(root, d, t, NOW))
    assert len(lines) == 1 and "failed" not in lines[0], lines
    table = watch_rows.load(ROOT)
    moves = _queued(root, pob_next.KIND_MOVE)
    assert len(moves) == 1 and moves[0]["key"] == f"move-{_sha(100)}"
    assert _note_text(table, moves[0]) == "PoB master moved 3 commits past the pin"
    assert _note_text(table, moves[0]) == pob_next.tick_line(3)
    assert table[pob_next.KIND_MOVE]["act"] == "note"
    assert _queued(root, pob_next.KIND_ROW) == []
    data = uw.load_state(root)["sources"]["pob-next"]["data"]
    assert data["head_sha"] == _sha(100) and data["n"] == 3 and data["n_more"] is False

    # not due again within the week: no request, no line
    calls = len(t.calls)
    assert _mine(_run(root, d, t, NOW + DAY)) == [] and len(t.calls) == calls

    # a week on with the same head: the source runs, no new line
    assert _mine(_run(root, d, t, NOW + 7 * DAY + 60)) == []
    assert len(_queued(root, pob_next.KIND_MOVE)) == 1

    # the head moves two more: exactly one new tick line
    t.move(2)
    lines = _mine(_run(root, d, t, NOW + 14 * DAY + 120))
    assert len(lines) == 1, lines
    moves = _queued(root, pob_next.KIND_MOVE)
    assert len(moves) == 2 and _note_text(table, moves[-1]) == pob_next.tick_line(5)


def test_head_at_the_pin_makes_no_line(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    t = Upstream(ahead=0, release_age_d=90)
    assert _mine(_run(root, d, t, NOW)) == []
    assert uw.pending(root) == []


def test_28_days_without_a_release_files_tc_next_once(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    t = Upstream(ahead=4, release_age_d=30)
    lines = _mine(_run(root, d, t, NOW))
    assert len(lines) == 1 and "failed" not in lines[0], lines
    rows = _queued(root, pob_next.KIND_ROW)
    assert len(rows) == 1
    assert rows[0]["tokens"] == {"sha": _sha(100), "n": "4"}
    table = watch_rows.load(ROOT)
    row_id, text = watch_rows.render(table, rows[0]["kind"], rows[0]["tokens"], "2026-11-20")
    assert row_id == "TC-NEXT-20261120", text
    assert text.startswith("- [ ] TC-NEXT-20261120 (review) PoB-PoE2 master is 4 commits")
    assert f"run the static rehearsal on {_sha(100)}" in text
    assert "BLOCKED: session." in text
    assert text.endswith(f"SOURCE: watch pob-next {_sha(100)}, filed 2026-11-20.")

    # weekly runs inside the 28 days: the head moves, no second row
    for week in (1, 2, 3):
        t.move(1)
        _run(root, d, t, NOW + week * 7 * DAY + 60)
    assert len(_queued(root, pob_next.KIND_ROW)) == 1
    assert len(_queued(root, pob_next.KIND_MOVE)) == 4

    # 28 days after the filing, still no release: filed once more
    t.move(1)
    _run(root, d, t, NOW + 28 * DAY + 3600)
    rows = _queued(root, pob_next.KIND_ROW)
    assert len(rows) == 2 and rows[1]["key"] != rows[0]["key"]
    assert rows[1]["tokens"]["n"] == "8"


def test_release_within_28_days_files_nothing(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    t = Upstream(ahead=4, release_age_d=27)
    _run(root, d, t, NOW)
    assert _queued(root, pob_next.KIND_ROW) == []


def test_no_release_at_all_counts_from_first_move(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    t = Upstream(ahead=2, release=False)
    _run(root, d, t, NOW)
    assert _queued(root, pob_next.KIND_ROW) == []
    for week in (1, 2, 3, 4):
        _run(root, d, t, NOW + week * 7 * DAY + 60)
    assert len(_queued(root, pob_next.KIND_ROW)) == 1


def test_pin_outside_the_page_reads_at_least(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    t = Upstream(ahead=pob_next.PER_PAGE, release_age_d=5)
    t.commits = lambda: [{"sha": _sha(500 - i), "commit": {"committer": {"date": _iso_z(NOW)}}}
                         for i in range(pob_next.PER_PAGE)]
    _run(root, d, t, NOW)
    data = uw.load_state(root)["sources"]["pob-next"]["data"]
    assert data["n"] == pob_next.PER_PAGE and data["n_more"] is True
    assert pob_next.tick_line(100, True) == "PoB master moved at least 100 commits past the pin"


def test_web_data_off_makes_zero_requests(tmp_path):
    root, d = _root(tmp_path, web_data=False), _sources(tmp_path)
    t = Upstream()
    lines = _mine(_run(root, d, t, NOW))
    assert t.calls == []
    assert lines == [f"watch pob-next: {uw.IDLE_OFF}"]
    assert uw.pending(root) == []
    # a direct gated fetch refuses before any request too
    try:
        watch_gate.fetch(root, pob_next.SOURCE, COMMITS, transport=t)
    except watch_gate.WebDataOff:
        pass
    else:
        raise AssertionError("fetch went through with web data off")
    assert t.calls == []


def test_no_source_file_is_requested(tmp_path):
    root, d = _root(tmp_path), _sources(tmp_path)
    t = Upstream(ahead=4, release_age_d=30)
    _run(root, d, t, NOW)
    assert [u for _m, u, _h in t.calls] == [COMMITS, LATEST]
    assert pob_next.SOURCE["urls"] == [] and pob_next.SOURCE["hosts"] == ["api.github.com"]
    for method, url, headers in t.calls:
        assert method == "GET"
        parts = urllib.parse.urlsplit(url)
        assert parts.hostname == "api.github.com"
        assert watch_gate._github_metadata(parts), url
        watch_gate.check_url(pob_next.SOURCE, url)
        words = set(parts.path.lower().split("/"))
        assert not words & set(watch_gate.FILE_PATH_WORDS), url
        assert headers["User-Agent"].startswith(NAME)
        assert "Cookie" not in headers and "cookie" not in headers
    # the repository comes from the pin file, never a constant of its own
    assert REPO not in (SRC_DIR / "pob_next.py").read_text(encoding="ascii")


def test_source_registers_in_the_real_folder():
    errors = []
    names = {s["name"]: s for s in uw.discover(errors=errors)}
    assert "pob-next" in names, errors
    src = names["pob-next"]
    assert src["needs_web_data"] is True and uw.is_network(src)
    assert src["cadence_s"] == 7 * DAY
    assert loop_base.ascii_text(pob_next.tick_line(3), 200) == pob_next.tick_line(3)
