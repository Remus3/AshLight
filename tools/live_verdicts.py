"""RUN-VERDICTS-CORE: read the 'Tried in game' verdicts back and draft the
ROADMAP flips (finding F-062, OPEN-27; decision 0040 amendment
2026-11-18).

Reads ops/runtime/verdicts.json (server/al/verdicts.py; the runtime dir
follows AL_RUNTIME_DIR, or pass --file) and prints:

- every check with its newest verdict (worked / refused, date, note) or
  "not tried";
- the draft done line for each ROADMAP row whose checks all have a newest
  verdict of "worked" (the docs/roadmap/done/<ID>.md text the fold reads);
- a draft fix row for each check whose newest verdict is "refused".

Text only: this script never writes ROADMAP.md or docs/roadmap/; the
integrator does the flip. It reads one local file, sends nothing anywhere
and never reads the game or Client.txt. Standard library only.

Usage: python tools/live_verdicts.py [--file PATH] [--json]
Exit codes: 0 ok (also with no file yet), 2 bad arguments.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import paths, verdicts  # noqa: E402

# ROADMAP row closed by each check's "worked" verdict; a row fed by several
# checks flips only when every one of them worked.
ROWS = {
    "TC-BUILDFILE-LIVE": "RUN-BUILDFILE-LIVE-CLOSE",
    "LIVE-SEARCHSTR": "RUN-VERDICTS-CLOSE",
    "LIVE-FILTER": "RUN-VERDICTS-CLOSE",
    "LIVE-FILTER-MERGE": "RUN-VERDICTS-CLOSE",
    "OVL-FPS": "OVL-FPS",
}
DONE_DIR = "docs/roadmap/done"


def day(at):
    """The local YYYY-MM-DD of an epoch second."""
    return time.strftime("%Y-%m-%d", time.localtime(at))


def _verdict_text(row):
    text = f"{row['result']} {day(row['at'])}"
    if row.get("note"):
        text += f" (note: {row['note']})"
    return text


def drafts(rows):
    """{"flips": [{"row", "file", "line", "checks"}], "fixes": [{"check",
    "line"}], "waiting": [{"row", "checks"}]} for the verdict rows
    (oldest first)."""
    last = verdicts.latest(rows)
    feeds = {}
    for cid in verdicts.CHECK_IDS:
        feeds.setdefault(ROWS[cid], []).append(cid)
    flips, waiting, fixes = [], [], []
    for row_id, cids in feeds.items():
        if all(last.get(c, {}).get("result") == "worked" for c in cids):
            when = max(last[c]["at"] for c in cids)
            said = ", ".join(f"{c} worked {day(last[c]['at'])}" for c in cids)
            flips.append({"row": row_id, "file": f"{DONE_DIR}/{row_id}.md",
                          "line": f" -- done {day(when)} (in-game verdict: {said})",
                          "checks": cids})
        else:
            open_ = [c for c in cids if last.get(c, {}).get("result") != "worked"]
            waiting.append({"row": row_id, "checks": open_})
    for cid in verdicts.CHECK_IDS:
        r = last.get(cid)
        if r is None or r["result"] != "refused":
            continue
        note = f" Player note: {r['note']}." if r.get("note") else ""
        fixes.append({"check": cid, "line": (
            f"- [ ] {cid}-FIX (build) Fix what the game refused: "
            f"{verdicts.LABELS[cid]} (verdict refused {day(r['at'])}).{note} "
            f"ACCEPT: python tools/live_verdicts.py lists a worked verdict for {cid}. "
            f"ZERO-CLICK: One more try by the player ends in one click. "
            f"DEPENDS: {ROWS[cid]}.")})
    return {"flips": flips, "fixes": fixes, "waiting": waiting}


def report(path):
    """(text, doc) of the verdict file at `path`."""
    rows = verdicts.load(path)
    doc = verdicts.view(rows)
    doc.update(drafts(rows))
    lines = [f"Tried in game verdicts ({len(rows)} recorded, newest per check):"]
    for c in doc["checks"]:
        v = c["verdict"]
        lines.append(f"- {c['id']}: {_verdict_text(v) if v else 'not tried'}")
    lines.append("Draft ROADMAP flips (text only; nothing is written):")
    if doc["flips"]:
        for f in doc["flips"]:
            lines.append(f"- {f['row']}: {f['file']}:{f['line']}")
    else:
        lines.append("- none yet")
    for w in doc["waiting"]:
        lines.append(f"- {w['row']} waits on: {', '.join(w['checks'])}")
    lines.append("Draft fix rows:")
    if doc["fixes"]:
        lines.extend(x["line"] for x in doc["fixes"])
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n", doc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--file", help="verdict file (default: <runtime dir>/verdicts.json)")
    ap.add_argument("--json", action="store_true", help="print the JSON document")
    args = ap.parse_args(argv)
    path = Path(args.file) if args.file else verdicts.default_path(paths.runtime_dir())
    text, doc = report(path)
    if args.json:
        sys.stdout.write(json.dumps(doc, indent=1, ensure_ascii=True) + "\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
