"""DATA-PRICE-TYPE-PROOF (F-201): tools/price_type_report.py says per price
type how many entries the cache holds and how many a press can reach, and
lists note-price alias ids the rates do not carry; the shape watch checks
the Currency body for the same ids. Synthetic fixtures only (no real item
name, decision 0009's spirit); tmp folders only; nothing reaches the
network."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import price_type_report as ptr  # noqa: E402
from server.al import ninjashape, pricebook  # noqa: E402
from server.al.theorycraft import value  # noqa: E402

UNIQUE = ("UniqueAlpha", "UniqueBeta", "PrecursorLike")
EXCHANGE = ("StackA", "StackB")


def _types(monkeypatch):
    monkeypatch.setattr(pricebook, "types", lambda: (UNIQUE, EXCHANGE))


def _unique(i, name=None, base=None):
    return {"name": name or f"Synth Unique {i}", "base": base or f"Synth Base {i}",
            "corrupted": False, "value": 1.0 + i, "listings": 20 + i, "change": None}


def _stack(i):
    return {"name": f"Synth Stack {i}", "value": 0.5 + i, "volume": 3.0, "change": None}


def _write(d, types, rates=None):
    d.mkdir(parents=True, exist_ok=True)
    doc = {"types": {n: {"kind": k, "league": "L", "entries": e}
                     for n, (k, e) in types.items()}}
    (d / pricebook.CACHE_NAME).write_text(json.dumps(doc), encoding="ascii")
    if rates is None:
        rates = {i: {"value": 1.0} for i in value.alias_ids()}
    (d / "rates.json").write_text(json.dumps({"primary": "divine", "rates": rates}),
                                  encoding="ascii")


def _full(dead=False):
    return {
        "UniqueAlpha": ("unique", [_unique(i) for i in range(3)]),
        "UniqueBeta": ("unique", [_unique(10 + i) for i in range(2)]),
        # a non-unique item listed in an item overview: name equals base
        "PrecursorLike": ("unique", [_unique(20 + i, name=f"Synth Tablet {i}",
                                             base=f"Synth Tablet {i}")
                                     for i in range(4)] if dead
                          else [_unique(30)]),
        "StackA": ("exchange", [_stack(i) for i in range(5)]),
        "StackB": ("exchange", [_stack(10 + i) for i in range(2)]),
    }


def test_report_counts_entries_and_matching_paths_per_type(monkeypatch, tmp_path):
    _types(monkeypatch)
    d = tmp_path / "ninja"
    _write(d, _full())
    rep = ptr.report(d)
    assert rep["round"] is True and rep["ok"] is True
    got = {t["type"]: (t["kind"], t["entries"], t["matching"], t["state"])
           for t in rep["types"]}
    assert got == {"UniqueAlpha": ("unique", 3, 3, ptr.OK),
                   "UniqueBeta": ("unique", 2, 2, ptr.OK),
                   "PrecursorLike": ("unique", 1, 1, ptr.OK),
                   "StackA": ("exchange", 5, 5, ptr.OK),
                   "StackB": ("exchange", 2, 2, ptr.OK)}
    assert [t["type"] for t in rep["types"]] == list(UNIQUE + EXCHANGE)
    assert rep["aliases"] == {"ids": len(value.alias_ids()), "missing": []}
    assert ptr.main(["--cache", str(d)]) == 0
    # counts, type names and alias ids only: never an item name
    text = json.dumps(rep) + "\n".join(ptr._lines(rep))
    assert "Synth" not in text and str(tmp_path) not in text
    # a type the cache does not hold yet, and one with no entries
    doc = _full()
    del doc["StackB"]
    doc["UniqueBeta"] = ("unique", [])
    _write(d, doc)
    rep = ptr.report(d)
    states = {t["type"]: t["state"] for t in rep["types"]}
    assert states["StackB"] == ptr.MISSING and states["UniqueBeta"] == ptr.EMPTY
    assert rep["ok"] is False and ptr.main(["--cache", str(d)]) == 1
    # no round at all: exit 2, nothing claimed
    empty = tmp_path / "none"
    empty.mkdir()
    assert ptr.report(empty)["round"] is False
    assert ptr.main(["--cache", str(empty)]) == 2
    assert not list(empty.iterdir())  # the report writes nothing


def test_a_type_no_press_can_match_is_reported_dead(monkeypatch, tmp_path, capsys):
    _types(monkeypatch)
    d = tmp_path / "ninja"
    _write(d, _full(dead=True))
    rep = ptr.report(d)
    dead = [t for t in rep["types"] if t["state"] == ptr.DEAD]
    assert dead == [{"type": "PrecursorLike", "kind": "unique", "entries": 4,
                     "matching": 0, "state": ptr.DEAD}]
    assert rep["ok"] is False
    assert ptr.main(["--cache", str(d)]) == 1
    out = capsys.readouterr().out
    assert "PrecursorLike: unique entries=4 matching=0 dead" in out
    assert out.strip().splitlines()[-1] == "verdict: fix or drop: PrecursorLike"
    # the press model goes through the real lookup: a unique press reaches
    # its entry, a non-unique item's press never searches the unique types
    book = pricebook.PriceBook(d)
    hit = book.lookup(ptr.press_for("unique", _unique(0)))
    assert hit["type"] == "UniqueAlpha"
    tablet = {"name": "Synth Tablet 0", "base": "Synth Tablet 0"}
    assert book.lookup(ptr.press_for("unique", tablet)) is None
    # dropping the dead type from the lists makes the report green
    monkeypatch.setattr(pricebook, "types", lambda: (UNIQUE[:2], EXCHANGE))
    assert ptr.report(d)["ok"] is True
    assert ptr.main(["--cache", str(d), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["ok"] is True and len(doc["types"]) == 4


def test_alias_ids_missing_from_the_rates_are_reported(monkeypatch, tmp_path):
    _types(monkeypatch)
    ids = value.alias_ids()
    assert ids == tuple(sorted(set(value.ALIASES.values())))
    assert "exalted" in ids and "divine" in ids
    d = tmp_path / "ninja"
    gone = ("mirror", "vaal")
    _write(d, _full(), rates={i: {"value": 2.0} for i in ids if i not in gone})
    rep = ptr.report(d)
    assert rep["aliases"]["missing"] == sorted(gone)
    assert rep["ok"] is False
    assert ptr.main(["--cache", str(d)]) == 1
    # the shape watch checks every Currency body for the same ids
    def body(missing):
        lines = [{"id": i, "primaryValue": 1.0 if i == "divine" else 0.5,
                  "volumePrimaryValue": 5.0, "sparkline": {"totalChange": 0.0}}
                 for i in ids if i not in missing]
        items = [{"id": x["id"], "name": f"Synth {n}"} for n, x in enumerate(lines)]
        return json.dumps({"core": {"primary": "divine", "items": items[:1]},
                           "lines": lines, "items": items}).encode()

    w = ninjashape.Watch(tmp_path / "rt", clock=lambda: 1_800_000_000.0)
    full = body(())
    n = len(ids)
    assert w.record("exchange", "Currency", 200, {}, full, n, n) == ninjashape.PASS
    short = body(gone)
    got = w.record("exchange", "Currency", 200, {}, short, n - 2, n - 2)
    assert got == ninjashape.CHANGE  # information: the parser still reads
    reason = w.results[("exchange", "Currency")]["reason"]
    assert "alias_ids" in reason and "mirror, vaal" in reason
    assert not (tmp_path / "rt" / ninjashape.FLAG_NAME).exists()
    # only the Currency body carries the note currencies
    w2 = ninjashape.Watch(tmp_path / "rt2", clock=lambda: 1_800_000_000.0)
    assert w2.record("exchange", "Runes", 200, {}, short, n - 2, n - 2) == ninjashape.PASS
    assert ninjashape.alias_missing([]) == []
