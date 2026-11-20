#!/usr/bin/env python3
"""Provenance - a source and a check date for every authored fact (F-097).

    provenance.py [--before YYYY-MM-DD]

Lists every entry of AshLight's authored data, one line each:

    <checked> <src> <where>

where <where> names the entry (`zone_guide G1 The Riverbank`,
`zone_guide G1 default`, `boss G1_15`, `waystone rule ground`,
`waystone reward rarity`, ...). With --before only the entries checked
before that date are listed: the re-verify list (for example the 1.0
launch, 2026-12-11). The last line is a count. An entry with no source
or date, or with a malformed one, prints `MISSING` and the exit code is 1.

Where an entry's pair comes from (the first one found):
- zone_guide.json: the zone entry's own `src` / `checked`, else its act
  table's pair; the act default and the endgame entry carry their own
  (the one authored zone file since DATA-GUIDE-MERGE: the zone notes
  became `layout` fields, decision 0043 amendment 2026-11-19);
- campaign.BOSS_ZONES: campaign.BOSS_PROVENANCE under the same area id;
- theorycraft.waystone RULES and REWARDS: each entry's own pair.

Allowed `src` forms (never a URL or a host name; the research note or
snapshot holds the address):
- research:<NNNN>         a note in docs/research/
- snapshot:<source name>  a build-time snapshot by its manifest name
- ggg-export:<name>       a GGG data export by name
- log                     the player's own Client.txt observation
- operator                text the operator pasted

Stdlib only, read-only: reads the tracked guide file and imports the two
modules, writes nothing, fetches nothing.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "server" / "al" / "data"
GUIDE = DATA / "zone_guide.json"

SRC_RE = re.compile(r"^(?:research:\d{4}|snapshot:[a-z0-9_-]+|ggg-export:[a-z0-9_-]+"
                    r"|log|operator)$")
# Host or address text that a src must never carry.
HOST_RE = re.compile(r"://|www\.|[a-z0-9-]+\.[a-z]{2,}", re.I)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def valid_src(value):
    """True for one of the allowed src forms, never a URL or a host."""
    return (isinstance(value, str) and SRC_RE.match(value) is not None
            and HOST_RE.search(value) is None)


def valid_checked(value):
    """True for a real calendar date written YYYY-MM-DD."""
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _pair(*sources):
    """(src, checked) from the first dict that has a src or a checked key."""
    for s in sources:
        if isinstance(s, dict) and ("src" in s or "checked" in s):
            return s.get("src"), s.get("checked")
    return None, None


def _read(path):
    return json.loads(Path(path).read_text(encoding="ascii"))


def guide_entries(doc):
    out = []
    acts = doc.get("acts") if isinstance(doc.get("acts"), dict) else {}
    for key, act in acts.items():
        act = act if isinstance(act, dict) else {}
        src, checked = _pair(act)
        out.append({"where": f"zone_guide {key} default", "src": src, "checked": checked})
        zones = act.get("zones") if isinstance(act.get("zones"), dict) else {}
        for zone, z in zones.items():
            src, checked = _pair(z, act)
            out.append({"where": f"zone_guide {key} {zone}", "src": src,
                        "checked": checked})
    if "endgame" in doc:
        src, checked = _pair(doc.get("endgame"))
        out.append({"where": "zone_guide endgame", "src": src, "checked": checked})
    return out


def code_entries():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from server.al import campaign
    from server.al.theorycraft import waystone
    out = []
    table = getattr(campaign, "BOSS_PROVENANCE", {})
    for area_id in campaign.BOSS_ZONES:
        src, checked = _pair(table.get(area_id))
        out.append({"where": f"boss {area_id}", "src": src, "checked": checked})
    for kind, rules in (("rule", waystone.RULES), ("reward", waystone.REWARDS)):
        for r in rules:
            src, checked = _pair(r)
            out.append({"where": f"waystone {kind} {r.get('id')}", "src": src,
                        "checked": checked})
    return out


def entries(guide=GUIDE):
    """Every authored entry as {"where", "src", "checked", "ok"}."""
    out = guide_entries(_read(guide)) + code_entries()
    for e in out:
        e["ok"] = valid_src(e["src"]) and valid_checked(e["checked"])
    return out


def before(items, date):
    """The entries checked before `date` (YYYY-MM-DD), plus every entry
    without a valid pair (they need a check too)."""
    return [e for e in items if not e["ok"] or e["checked"] < date]


def line(e):
    if not e["ok"]:
        return f"MISSING {e['src'] or '-'} {e['where']}"
    return f"{e['checked']} {e['src']} {e['where']}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--before", metavar="YYYY-MM-DD",
                    help="list only the entries checked before this date")
    args = ap.parse_args(argv)
    if args.before is not None and not valid_checked(args.before):
        ap.error("--before needs a date written YYYY-MM-DD")
    items = entries()
    shown = before(items, args.before) if args.before else items
    for e in shown:
        print(line(e))
    missing = sum(1 for e in items if not e["ok"])
    tail = f" checked before {args.before}" if args.before else ""
    print(f"provenance: {len(shown)} of {len(items)} entries{tail}, {missing} missing")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
