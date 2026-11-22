"""DATA-PRICE-TYPE-PROOF (F-201): prove each poe.ninja price type after a
real round.

    python tools/price_type_report.py [--cache DIR] [--json]

Reads only AshLight's own cache files in DIR (default: the sidecar
Cache\\ninja, server.al.ninja.cache_dir): the price book book.json and the
Currency rates rates.json. Makes no request, writes nothing.

Per requested type (server/al/data/price_types.json, pricebook.types()):
- entries: how many entries the cache holds for it;
- matching: how many of them a press can reach. Each entry is turned into
  the press that would show that item and run through the real
  PriceBook.lookup(): a unique-type entry whose name differs from its base
  is a unique item (pressed with rarity UNIQUE, name and base); one whose
  name equals its base is not a unique item, so its press carries no unique
  name and lookup() never searches the unique types for it (the
  PrecursorTablets case); an exchange-type entry is pressed as a stackable
  (rarity CURRENCY, base = its name). An entry counts when lookup() answers
  with this type and this entry;
- state: ok (entries and a matching path), dead (entries, none reachable),
  empty (no entries), missing (the type is not in the cache yet).

Aliases: every id of theorycraft.value.alias_ids() must be a key of the
rates in rates.json; a missing one is listed.

Output is counts, type names and alias ids only: never an item name, a
price or a league. Exit 0 when every type is ok and no alias is missing;
1 when a type is dead, empty or missing or an alias is missing; 2 when the
cache holds no round (book.json or rates.json absent or unreadable).

report(directory) gives the same result as a dict, for a later loop-tick
host (AUTO-05 watcher frame).
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import jsonfile, ninja, pricebook  # noqa: E402
from server.al.theorycraft import value  # noqa: E402

OK, DEAD, EMPTY, MISSING = "ok", "dead", "empty", "missing"
MAX_BYTES = 32 * 1024 * 1024


def _key(text):
    return " ".join(text.split()).lower() if isinstance(text, str) else ""


def press_for(kind, entry):
    """The parsed press (a dict lookup() reads) that would show `entry`."""
    name, base = entry.get("name"), entry.get("base")
    if kind == "unique":
        if _key(name) and _key(name) != _key(base):
            return {"rarity": "UNIQUE", "name": name, "base": base or "",
                    "flags": {"corrupted": entry.get("corrupted") is True}}
        # not a unique item: its press names only the base, never as UNIQUE
        return {"rarity": "RARE", "name": "", "base": base or name or "", "flags": {}}
    return {"rarity": "CURRENCY", "name": name, "base": name, "flags": {}}


def _reaches(book, type_name, kind, entry):
    hit = book.lookup(press_for(kind, entry))
    return (isinstance(hit, dict) and hit.get("type") == type_name
            and _key(hit.get("name")) == _key(entry.get("name")))


def _read(path):
    return jsonfile.read_json(path, max_bytes=MAX_BYTES, encoding="ascii", kind=dict)


def report(directory):
    """{"round": bool, "types": [{type, kind, entries, matching, state}],
    "aliases": {"ids": n, "missing": [ids]}, "ok": bool}."""
    directory = Path(directory)
    book_doc = _read(directory / pricebook.CACHE_NAME)
    rates_doc = _read(directory / ninja.CACHE_NAME)
    have_round = (isinstance(book_doc, dict) and isinstance(book_doc.get("types"), dict)
                  and isinstance(rates_doc, dict))
    out = {"round": have_round, "types": [], "aliases": {}, "ok": False}
    if not have_round:
        return out
    book = pricebook.PriceBook(directory)
    for name, _path, kind in pricebook._all_types():
        t = book.doc["types"].get(name)
        entries = [e for e in (t.get("entries") or ()) if isinstance(e, dict)] \
            if isinstance(t, dict) and isinstance(t.get("entries"), list) else None
        if entries is None:
            out["types"].append({"type": name, "kind": kind, "entries": 0,
                                 "matching": 0, "state": MISSING})
            continue
        matching = sum(1 for e in entries if _reaches(book, name, kind, e))
        state = EMPTY if not entries else (OK if matching else DEAD)
        out["types"].append({"type": name, "kind": kind, "entries": len(entries),
                             "matching": matching, "state": state})
    rates = rates_doc.get("rates") if isinstance(rates_doc.get("rates"), dict) else {}
    ids = value.alias_ids()
    out["aliases"] = {"ids": len(ids), "missing": [i for i in ids if i not in rates]}
    out["ok"] = (all(t["state"] == OK for t in out["types"])
                 and not out["aliases"]["missing"])
    return out


def _lines(rep):
    if not rep["round"]:
        return ["no round: the cache holds no price book or rates yet"]
    lines = [f"{t['type']}: {t['kind']} entries={t['entries']} "
             f"matching={t['matching']} {t['state']}" for t in rep["types"]]
    missing = rep["aliases"]["missing"]
    lines.append(f"aliases: {rep['aliases']['ids']} ids, missing "
                 + (", ".join(missing) if missing else "none"))
    bad = [t["type"] for t in rep["types"] if t["state"] != OK]
    lines.append("verdict: " + ("ok" if rep["ok"] else
                                "fix or drop: " + ", ".join(bad + missing)))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cache", help="the ninja cache folder (default: the sidecar's)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    args = ap.parse_args(argv)
    directory = Path(args.cache) if args.cache else ninja.cache_dir()
    rep = report(directory)
    if args.json:
        print(json.dumps(rep, sort_keys=True))
    else:
        print("\n".join(_lines(rep)))
    if not rep["round"]:
        return 2
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
