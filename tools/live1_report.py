"""RUN-LEDGER-REPORT: what the parse ledger saw, per LIVE-1 item (finding
F-061, OPEN-01, OPEN-02, LIVE-1, TEST-LIVE-CLICKS; decision 0071).

Reads AshLight's own bounded file ops/runtime/logshapes.json (written by
server/al/plug/ledger.py while the ledger consent is on; the runtime dir
follows AL_RUNTIME_DIR, or pass --file) and prints:

- one verdict line per LIVE-1 item (logshapes.LIVE1_ITEMS, the
  LIVE-1-<ITEM> rows) and one for LIVE-WAYSTONE:
  VERIFIED live  a pattern id of the item has a live hit (for the
                 waystone: a masked property-block shape was kept);
  NEW SHAPE      no hit, but a masked shape that passed the two-sighting
                 rule carries one of the item's words (SHAPE_WORDS), or an
                 unknown area id seen twice looks like the item (AREA_HINTS);
  NOT SEEN       neither;
- the five TEST-LIVE-CLICKS read-back fields (seen / not seen);
- the masked waystone property-block shapes;
- every masked shape that passed the two-sighting rule (NEW SHAPE lines,
  the work list of a LOG-SHAPE row).

The file is re-checked on the way in by the ledger's own loaders
(logshapes.Ledger.from_dict and Wire.load), so a tampered file cannot put
raw text into the report: every printed shape is an allow-list word, a
placeholder or punctuation. A missing or unreadable file reports every
item NOT SEEN and exits 0.

Text only: it never writes ROADMAP.md, docs/roadmap/ or the ledger, sends
nothing anywhere, and never reads Client.txt or the game. Standard library
only.

Usage: python tools/live1_report.py [--file PATH] [--json]
Exit codes: 0 ok (also with no file yet), 2 bad arguments.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import jsonfile, logshapes, paths  # noqa: E402
from server.al.core import LEDGER_FILE  # noqa: E402
from server.al.plug import ledger as ledger_mod  # noqa: E402

VERIFIED = "VERIFIED live"
NEW_SHAPE = "NEW SHAPE"
NOT_SEEN = "NOT SEEN"

WAYSTONE = "WAYSTONE"
ROW_PREFIX = {WAYSTONE: "LIVE-WAYSTONE"}   # else LIVE-1-<ITEM>

# Allow-list words (logshapes.ALLOW) whose presence in a confirmed masked
# shape ties it to an item. A near-miss shape (a trade whisper that failed
# all three templates) belongs to TRADE alone.
SHAPE_WORDS = {
    "DEATH": frozenset(("slain", "suicide")),
    "WHISPER": frozenset(("whisper", "whispers")),
    "TRADE": frozenset(),
    "PARTY": frozenset(("party",)),
    "GUILD": frozenset(("guild",)),
    "AFK": frozenset(("afk", "dnd", "autoreply")),
    "JOINED": frozenset(("joined", "left")),
    "ACCEPTED": frozenset(("accepted", "cancelled", "declined")),
    "HIDEOUT": frozenset(("hideout",)),
    "CRUEL": frozenset(),
    "MAP": frozenset(("map",)),
}

# Unknown area ids (class "other", kept verbatim as engine constants) that
# look like an item's area class.
AREA_HINTS = {
    "CRUEL": re.compile(r"^C\d|cruel", re.IGNORECASE),
    "MAP": re.compile(r"map", re.IGNORECASE),
    "HIDEOUT": re.compile(r"hideout", re.IGNORECASE),
}
AREA_MIN_SIGHTINGS = 2

MAX_LEDGER_BYTES = 2 * logshapes.MAX_BYTES


def default_path():
    return paths.runtime_dir() / LEDGER_FILE


def load(path):
    """(state, ledger, wire) for the file at path; state is "found",
    "missing" or "unreadable". The ledger and wire hold only what their
    loaders accept."""
    p = Path(path)
    data = jsonfile.read_json(p, max_bytes=MAX_LEDGER_BYTES, encoding="ascii",
                              kind=dict, default=None)
    wire = ledger_mod.Wire(None)
    if data is None:
        try:
            state = "unreadable" if p.exists() else "missing"
        except OSError:
            state = "unreadable"
        return state, wire.ledger, wire
    wire.load(data)
    return "found", wire.ledger, wire


def _words(shape):
    out = set()
    for tok in shape.split(" "):
        core = tok.strip("".join(logshapes.PUNCT)).lower()
        if core:
            out.add(core)
    return out


def confirmed_shapes(led):
    """[{"kind", "shape", "n", "first", "last", "items"}] for each masked
    shape that passed the two-sighting rule, in ledger order."""
    out = []
    for (kind, shape), rec in led.shapes.items():
        if not rec[3] or not logshapes.is_safe_shape(shape):
            continue
        if kind == logshapes.KIND_NEAR:
            items = ["TRADE"]
        else:
            words = _words(shape)
            items = [k for k, ws in SHAPE_WORDS.items() if ws & words]
        out.append({"kind": kind, "shape": shape, "n": rec[0],
                    "first": rec[1], "last": rec[2], "items": items})
    return out


def area_hints(led):
    """{item: [area id]} for unknown area ids seen at least twice that look
    like the item."""
    out = {}
    for aid, rec in led.area_ids.items():
        if rec[0] < AREA_MIN_SIGHTINGS:
            continue
        for item, rx in AREA_HINTS.items():
            if rx.search(aid):
                out.setdefault(item, []).append(aid)
    return out


def verdicts(led, wire):
    """[{"item", "row", "verdict", "hits", "first", "last", "shapes",
    "area_ids"}] in LIVE1_ITEMS order, then the waystone item."""
    shapes = confirmed_shapes(led)
    hints = area_hints(led)
    out = []
    for item, pids in logshapes.LIVE1_ITEMS.items():
        hits = {p: led.hits[p][0] for p in pids if p in led.hits and led.hits[p][0] > 0}
        firsts = [led.hits[p][1] for p in hits]
        lasts = [led.hits[p][2] for p in hits]
        n_shapes = sum(1 for s in shapes if item in s["items"])
        aids = sorted(hints.get(item, ()))
        if hits:
            verdict = VERIFIED
        elif n_shapes or aids:
            verdict = NEW_SHAPE
        else:
            verdict = NOT_SEEN
        out.append({"item": item, "row": ROW_PREFIX.get(item, "LIVE-1-" + item),
                    "verdict": verdict, "hits": hits,
                    "first": min(firsts) if firsts else None,
                    "last": max(lasts) if lasts else None,
                    "shapes": n_shapes, "area_ids": aids})
    ways = waystones(wire)
    out.append({"item": WAYSTONE, "row": ROW_PREFIX[WAYSTONE],
                "verdict": VERIFIED if ways else NOT_SEEN,
                "hits": {}, "first": min((w["first"] for w in ways), default=None),
                "last": max((w["last"] for w in ways), default=None),
                "shapes": len(ways), "area_ids": []})
    return out


def waystones(wire):
    return [{"lines": list(k), "n": v[0], "first": v[1], "last": v[2]}
            for k, v in wire.waystones.items()
            if all(ledger_mod.is_safe_line(x) for x in k)]


def build(path):
    state, led, wire = load(path)
    return {
        "schema": 1,
        "ledger": state,
        "items": verdicts(led, wire),
        "readback": {k: wire.readback.get(k) is True for k in ledger_mod.READBACK},
        "waystone": waystones(wire),
        "new_shapes": confirmed_shapes(led),
        "pending_shapes": sum(1 for r in led.shapes.values() if not r[3]),
    }


def _item_line(it):
    text = f"{it['row']}: {it['verdict']}"
    if it["verdict"] == VERIFIED and it["hits"]:
        parts = ", ".join(f"{p} {n}" for p, n in sorted(it["hits"].items()))
        text += f" ({parts}; first {it['first']}, last {it['last']})"
    elif it["verdict"] == VERIFIED:
        text += f" ({it['shapes']} shape(s); last {it['last']})"
    elif it["verdict"] == NEW_SHAPE:
        bits = []
        if it["shapes"]:
            bits.append(f"{it['shapes']} confirmed shape(s)")
        if it["area_ids"]:
            bits.append("area ids " + ", ".join(it["area_ids"]))
        text += " (" + "; ".join(bits) + ")"
    return text


def render(doc):
    lines = [f"ledger: {doc['ledger']}", "items:"]
    lines += ["  " + _item_line(it) for it in doc["items"]]
    lines.append("read-back (TEST-LIVE-CLICKS):")
    for k, v in doc["readback"].items():
        lines.append(f"  {k}: {'seen' if v else 'not seen'}")
    lines.append("waystone shapes:" + ("" if doc["waystone"] else " none"))
    for i, w in enumerate(doc["waystone"], 1):
        lines.append(f"  {i} (n {w['n']}, last {w['last']}): " + " | ".join(w["lines"]))
    lines.append("shapes past the two-sighting rule:"
                 + ("" if doc["new_shapes"] else " none"))
    for s in doc["new_shapes"]:
        items = ",".join(s["items"]) or "-"
        lines.append(f"  {NEW_SHAPE} {s['kind']}: {s['shape']} "
                     f"(n {s['n']}, last {s['last']}, items {items})")
    lines.append(f"pending shapes (one sighting so far): {doc['pending_shapes']}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--file", help="ledger file (default: <runtime dir>/" + LEDGER_FILE + ")")
    ap.add_argument("--json", action="store_true", help="print the JSON document")
    args = ap.parse_args(argv)
    path = Path(args.file) if args.file else default_path()
    doc = build(path)
    if args.json:
        sys.stdout.write(json.dumps(doc, indent=1, ensure_ascii=True) + "\n")
    else:
        sys.stdout.write(render(doc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
