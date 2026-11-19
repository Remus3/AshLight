#!/usr/bin/env python3
"""Loop preflight (package LOOP-PREFLIGHT-CMD, AUTO-21 checks 3 and 4).

    python tools/loop_preflight.py            run the loop gates once, report
    python tools/loop_preflight.py --handoff  print 'hand-off loop items: <n>'

The default run claims one loop lane through the kit lane context
(al_lane.lanes().run_lane, the way al_lane.run_lane claims one), which puts
the lane worktree clean on main's HEAD with no change; it runs every command
of ops/loop/gates.txt there ONCE, in order, as argv (a whole pytest suite goes
through the kit suite gate, exactly as the loop's own gates do), prints one
line per gate and releases the claim. Exit 0 when every gate is green, else 1.
A busy lane set (every lane refused) exits 1 with the reasons.

--handoff counts the hand-off's "Carried forward" items the loop would take
(handoff_items entries whose skip is None) and prints only that line.

It spawns no headless run: no kit spawn, no governor slot, no claude. docs/plan
/06 spells it 'al_loop.py preflight'; it lives here because al_loop.py is line
capped. Nothing imports this file.
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_lane  # noqa: E402
import al_loop  # noqa: E402

RUN_ID = "preflight"


def handoff_count(root=ROOT):
    """Hand-off items the loop would take (skip None), from the MAIN checkout."""
    main = al_lane.lanes().main_tree(root)
    path = Path(main) / f"{al_loop.CODE}-NEXT-SESSION.txt"
    text = path.read_text(encoding="utf-8")
    return sum(1 for item in al_loop.handoff_items(text) if item["skip"] is None)


def run_gates(cwd, run=al_loop._run_gate, argv_of=al_loop._gate_argv):
    """[(cmd, ok, detail)] for every gate of cwd, each run once, in order.
    Fail closed (one red row) with no gate list or a command the loop cannot
    run as argv. A red gate does not stop the later ones: one line each."""
    cmds, src = al_loop.gate_commands(cwd)
    if cmds is None:
        return [("gates", False, src)]
    if not cmds:
        return [("gates", False, f"no gate command in {src}: fail closed")]
    rows = []
    for cmd in cmds:
        if not cmd.strip():
            rows.append(("(empty)", False, f"empty gate command in {src}"))
            continue
        op = al_loop._shell_operator(cmd)
        if op is not None:
            rows.append((cmd, False, f"shell operator {op!r} unsupported"))
            continue
        try:
            rc, tail = run(argv_of(cmd), cwd)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            rows.append((cmd, False, type(exc).__name__))
            continue
        last = next((ln.strip() for ln in reversed((tail or "").splitlines())
                     if ln.strip()), "")
        rows.append((cmd, rc == 0, f"rc={rc}" + (f" {last[:160]}" if last else "")))
    return rows


def preflight(root=ROOT, lane_ctx=None, gates=run_gates, out=print, lanes=None):
    """Claim a lane on main's HEAD, run the gates once there, release. 0 / 1."""
    if lane_ctx is None:
        lane_ctx = al_lane.lanes().run_lane
    refused = []
    for lane in lanes or al_lane.LANES:
        try:
            with lane_ctx(root, al_loop.CODE, lane, RUN_ID, cap=al_lane.lane_cap()) as claim:
                wt = Path(claim["worktree"])
                out(f"preflight: lane {lane} worktree {wt.name} on main HEAD")
                rows = gates(wt)
        except Exception as exc:  # noqa: BLE001 - a refused claim tries the next lane
            if type(exc).__name__ != "LaneRefused":
                out(f"preflight: lane {lane}: {type(exc).__name__}: {exc}")
                return 1
            refused.append(f"{lane}: {exc}")
            continue
        for cmd, ok, detail in rows:
            out(f"{'PASS' if ok else 'FAIL'} {cmd} ({detail})")
        green = bool(rows) and all(ok for _, ok, _ in rows)
        out(f"preflight: {'green' if green else 'red'} ({len(rows)} gates)")
        return 0 if green else 1
    out("preflight: no lane free: " + "; ".join(refused))
    return 1


def main(argv=None, root=ROOT, out=print):
    ap = argparse.ArgumentParser(prog="loop_preflight.py", description=__doc__.splitlines()[0])
    ap.add_argument("--handoff", action="store_true",
                    help="print only 'hand-off loop items: <n>'")
    args = ap.parse_args(argv)
    if args.handoff:
        try:
            n = handoff_count(root)
        except OSError as exc:
            out(f"preflight: hand-off unreadable: {type(exc).__name__}")
            return 1
        out(f"hand-off loop items: {n}")
        return 0
    return preflight(root, out=out)


if __name__ == "__main__":
    sys.exit(main())
