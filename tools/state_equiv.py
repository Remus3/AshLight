"""TEST-STATE-EQUIV: an equivalence check for state refactors.

    python tools/state_equiv.py --ref <rev> [--tree DIR]

Replays one fixed corpus through server.al.parser / SessionState twice: once
from the working tree (or DIR) and once from `git archive <rev>` unpacked
under the AL sidecar Temp dir (server.al.paths.sidecar_dir('Temp')), each
side in its own subprocess, and compares every snapshot() as key-sorted JSON.
The clock is fixed (it follows the synthetic line times), so a run is
deterministic. Prints 'state_equiv: identical' and exits 0, or names each
differing key path and exits 1; exit 2 is a setup error (bad rev, a side
that crashed).

The corpus: tools/synth_client.py sessions (standard_session for two seeds
and a short Session with a cancelled trade) plus a fixed card corpus (item
check, price, waystone, build alert, upgrade notice, trade lines and
tailer reset events). It starts no core, binds no port, reads no Client.txt
(the lines are synthetic) and makes no request. The reference export is
removed after the run. Developer-side only; stdlib only.
"""

import argparse
import calendar
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
EPOCH0 = calendar.timegm((2026, 11, 16, 21, 0, 0))
MAX_SHOWN = 20
TIMEOUT_S = 300


# -- the corpus (built by the parent; both sides get the same bytes) --------

def _synth():
    sys.path.insert(0, str(TOOLS))
    try:
        import synth_client as sc
    finally:
        sys.path.remove(str(TOOLS))
    return sc


def _session_lines():
    sc = _synth()
    runs = []
    for seed in (1, 7):
        s = sc.standard_session(seed=seed)
        runs.append({"name": f"standard_session-{seed}", "lines": list(s.lines)})
    s = sc.Session(seed=3, character="Emberlin", klass="Mercenary")
    s.marker()
    s.zone_change("G1_1", 1, "The Riverbank")
    s.level_up()
    s.whisper("Quietfox", "wtb your bow")
    s.trade_whisper("Bargainer", "Dusk Fang", 2, "divine")
    s.trade_cancelled()
    s.whisper_out("Quietfox", "sold, sorry")
    s.noise(2)
    s.zone_change("G1_town", 15, "Clearfell Encampment")
    s.death()
    runs.append({"name": "session-3", "lines": list(s.lines)})
    return runs


def _ring(name, base="Example Ring"):
    return {"name": name, "base": base}


LIFE = {"key": "+# to maximum Life", "delta": 35, "score_delta": 35, "weighted": True}
RES = {"key": "+#% to Lightning Resistance", "delta": -10, "score_delta": -6,
       "weighted": True}
ODD = {"key": "Some odd stat #", "delta": 4, "score_delta": 0, "weighted": False}


def _cards():
    """Ordered steps: (kind, payload). Kinds map to SessionState calls in
    _replay; every card text path (eval, price, waystone, build alert,
    upgrades) and the trade lines / reset events are covered."""
    eval_card = {"ok": True, "error": None, "verdict": "upgrade", "slot": "Ring 1",
                 "score_delta": 47.5, "unidentified": False,
                 "item": _ring("Storm Loop"),
                 "comparisons": [
                     {"slot": "Ring 1", "verdict": "upgrade", "score_delta": 47.5,
                      "empty": False, "equipped": _ring("Weak Loop"),
                      "stats": [ODD, LIFE, RES]},
                     {"slot": "Ring 2", "verdict": "downgrade", "score_delta": -1,
                      "empty": False, "equipped": _ring("Strong Loop"), "stats": []}]}
    eval_err = {"ok": False, "error": "no_build", "verdict": None,
                "item": _ring("Odd Band"), "comparisons": []}
    price_done = {"status": "done", "wait_s": None, "league": "Dawn",
                  "item": {"name": "Storm Loop", "base": "Example Ring", "rarity": "Rare"},
                  "count": 5, "error": None,
                  "listings": [{"amount": 10, "currency": "exalted"},
                               {"amount": 11, "currency": "exalted"},
                               {"amount": 12, "currency": "exalted"},
                               {"amount": 14.5, "currency": "exalted"},
                               {"amount": 1, "currency": "divine"}]}
    price_search = dict(price_done, status="searching", count=0, listings=[])
    price_off = dict(price_done, status="off", count=0, listings=[])
    waystone = {"ok": True, "error": None, "verdict": None,
                "item": {"name": "Doom Trail", "base": "Waystone (Tier 15)"},
                "comparisons": [],
                "waystone": {"tier": 15, "build_loaded": True,
                             "risky": [{"label": "Extra Fire damage", "short": "Extra fire"},
                                       {"label": "Less Life recovery", "short": "Less recovery"},
                                       {"label": "Monster crits", "short": "Crits"}],
                             "rewards": [{"pct": 12, "label": "Monster pack size",
                                          "short": "Pack"},
                                         {"pct": 38, "label": "Item rarity",
                                          "short": "Rarity"}]}}
    waystone_unid = dict(waystone, waystone={"tier": 9, "unidentified": True})
    build = {"loaded": True, "character": "Cinderwisp", "class_name": "Sorceress",
             "ascendancy": None, "level": 1, "name": "Spark test"}
    build_mismatch = dict(build, class_name="Warrior", ascendancy="Titan")
    upgrades = {"items": [
        {"name": "Storm Loop", "base": "Example Ring", "slot": "Ring 1", "new": True,
         "replaces": "Weak Loop", "score_delta": 47.5, "source": "weights",
         "fit": {"kind": "class", "build_class": "Sorceress"}},
        {"name": None, "base": "Example Gloves", "slot": "Gloves", "new": False,
         "empty": True, "score_delta": 3.25, "source": "pob",
         "fit": {"kind": "level", "ok": False, "need": 40, "level": 4}}]}
    trades = _synth().Session(seed=11)
    trades.trade_whisper("Tradewind", "Grim Bane Ruby Ring", 5, "exalted")
    trades.trade_whisper("\u30b5\u30af\u30e9", "Dusk Fang", 2, "divine")
    trades.whisper("Quietfox", "still selling?")
    trades.trade_accepted()
    t = trades.lines
    return [
        ("eval", eval_card), ("price", price_search), ("price_keep", price_done),
        ("eval", eval_err), ("price", price_off),
        ("eval", waystone), ("eval", waystone_unid),
        ("build", None), ("build", build), ("build", build_mismatch),
        ("upgrades", upgrades), ("upgrades", {"items": []}),
        ("line", t[0]), ("line", t[1]), ("line", t[2]),
        ("event", {"type": "tailer_started", "source": "tailer"}),
        ("event", {"type": "tailer_reset", "source": "tailer", "reason": "truncated"}),
        ("event", {"type": "tailer_reset", "source": "tailer", "reason": "missing"}),
        ("event", {"type": "tailer_reset", "source": "tailer", "reason": "odd"}),
        ("line", t[3]), ("dismiss", None),
    ]


def corpus():
    return {"sessions": _session_lines(), "cards": [list(c) for c in _cards()]}


# -- one side: run in a subprocess with the tree's server/ on sys.path -------

def _jsonable(value):
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=repr)
    if isinstance(value, tuple):
        return list(value)
    return repr(value)


def _ts_epoch(ts_local):
    """The line's own time as a fixed epoch (treated as UTC: no host zone)."""
    try:
        date, clock = ts_local.split("T")
        y, mo, d = (int(x) for x in date.split("-"))
        h, mi, s = (int(x) for x in clock.split(":"))
        return float(calendar.timegm((y, mo, d, h, mi, s)))
    except (ValueError, AttributeError):
        return None


def _replay(tree, doc):
    sys.path.insert(0, str(tree))
    from server.al import parser
    from server.al.state import SessionState

    clock = {"t": float(EPOCH0)}
    snaps = {}

    def tick(t=None):
        clock["t"] = float(t) if t is not None else clock["t"] + 1.0
        return clock["t"]

    base = None
    for run in doc["sessions"]:
        clock["t"] = float(EPOCH0)
        st = SessionState(clock=lambda: clock["t"])
        for i, line in enumerate(run["lines"]):
            ev = parser.parse_line(line)
            if ev is None:
                continue
            t = _ts_epoch(ev.get("ts_local"))
            ev["recv_ts"] = tick(t if t is not None and t > clock["t"] else None)
            ev["seq"] = i + 1
            st.apply(ev)
        tick()
        snaps[f"session:{run['name']}"] = st.snapshot()
        if base is None:
            base = st
    st = base
    clock["t"] = max(clock["t"], float(EPOCH0) + 3600.0)
    for n, (kind, payload) in enumerate(doc["cards"]):
        at = tick()
        if kind == "eval":
            st.set_eval(payload, at=at)
        elif kind == "price":
            st.set_price(payload, at=at)
        elif kind == "price_keep":
            st.set_price(payload, keep_time=True)
        elif kind == "build":
            st.set_build_info(payload)
        elif kind == "upgrades":
            st.set_upgrades(payload)
        elif kind == "line":
            ev = parser.parse_line(payload)
            if ev is not None:
                st.apply(dict(ev, recv_ts=at, seq=1000 + n))
        elif kind == "event":
            st.apply(dict(payload, recv_ts=at))
        elif kind == "dismiss":
            st.dismiss_trade()
        tick()
        snaps[f"card{n:02d}:{kind}"] = st.snapshot()
    return snaps


def _child(tree):
    doc = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    out = _replay(Path(tree).resolve(), doc)
    sys.stdout.buffer.write(json.dumps(out, sort_keys=True, ensure_ascii=True,
                                       default=_jsonable).encode("ascii"))
    return 0


def run_side(tree, doc_bytes, env):
    r = subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                        "--replay", str(tree)],
                       input=doc_bytes, capture_output=True, timeout=TIMEOUT_S,
                       cwd=str(tree), env=env)
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError(f"replay in {tree} failed: "
                           + (err[-1] if err else f"rc {r.returncode}"))
    return json.loads(r.stdout.decode("ascii"))


# -- the reference export --------------------------------------------------

def _temp_dir():
    sys.path.insert(0, str(ROOT))
    try:
        from server.al import paths
    finally:
        sys.path.remove(str(ROOT))
    return paths.sidecar_dir("Temp")


def export_ref(rev, repo, base):
    """`git archive <rev> server` unpacked under base; returns the dir."""
    r = subprocess.run(["git", "archive", "--format=tar", rev, "server"],
                       cwd=str(repo), capture_output=True, timeout=TIMEOUT_S)
    if r.returncode != 0:
        msg = r.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git archive {rev} failed: {msg}")
    base.mkdir(parents=True, exist_ok=True)
    dest = Path(tempfile.mkdtemp(prefix="state_equiv-", dir=str(base)))
    with tarfile.open(fileobj=io.BytesIO(r.stdout), mode="r:") as tar:
        tar.extractall(dest, filter="data")
    return dest


# -- compare ----------------------------------------------------------------

def diff(a, b, path=""):
    """Key paths where two JSON values differ, in order."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            p = f"{path}/{k}" if path else str(k)
            if k not in a or k not in b:
                out.append(p)
            else:
                out.extend(diff(a[k], b[k], p))
        return out
    if isinstance(a, list) and isinstance(b, list):
        out = []
        for i in range(max(len(a), len(b))):
            p = f"{path}/{i}"
            if i >= len(a) or i >= len(b):
                out.append(p)
            else:
                out.extend(diff(a[i], b[i], p))
        return out
    return [] if a == b else [path]


def _at(doc, path):
    cur = doc
    for part in path.split("/"):
        if isinstance(cur, list):
            i = int(part)
            if i >= len(cur):
                return "<missing>"
            cur = cur[i]
        elif isinstance(cur, dict):
            if part not in cur:
                return "<missing>"
            cur = cur[part]
    return cur


def _short(value):
    text = json.dumps(value, sort_keys=True, ensure_ascii=True)
    return text if len(text) <= 120 else text[:117] + "..."


def main(argv=None):
    ap = argparse.ArgumentParser(description="TEST-STATE-EQUIV: compare SessionState "
                                             "snapshots of this tree and a revision")
    ap.add_argument("--ref", help="the reference revision (git archive <rev>)")
    ap.add_argument("--tree", default=str(ROOT),
                    help="the tree to check (default: this working tree)")
    ap.add_argument("--replay", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.replay:
        return _child(args.replay)
    if not args.ref:
        ap.error("--ref is required")
    tree = Path(args.tree).resolve()
    doc_bytes = json.dumps(corpus(), ensure_ascii=True).encode("ascii")
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    ref_dir = None
    try:
        ref_dir = export_ref(args.ref, ROOT, _temp_dir())
        print(f"state_equiv: reference {args.ref} exported to {ref_dir}", file=sys.stderr)
        ref = run_side(ref_dir, doc_bytes, env)
        cur = run_side(tree, doc_bytes, env)
    except (RuntimeError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"state_equiv: error: {exc}")
        return 2
    finally:
        if ref_dir is not None:
            shutil.rmtree(ref_dir, ignore_errors=True)
    paths = diff(ref, cur)
    if not paths:
        print("state_equiv: identical")
        return 0
    print(f"state_equiv: {len(paths)} differing key path(s) vs {args.ref}")
    for p in paths[:MAX_SHOWN]:
        print(f"  {p}: ref={_short(_at(ref, p))} tree={_short(_at(cur, p))}")
    if len(paths) > MAX_SHOWN:
        print(f"  (+{len(paths) - MAX_SHOWN} more)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
