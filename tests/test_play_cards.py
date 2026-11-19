"""PLAY-TD-07B: snapshot()['play'] carries region C's available modes, the
item card and the kept checks, composed and capped at the source
(server/al/playcards.py).

Caps (plan 03 section 3.4): a context block has a title of at most 38
characters and at most 7 body rows of at most 52 (and a facts row of at
most 52); the item card a verdict word, a sentence of 2 rows of at most 36,
exactly 5 compare rows of at most 36, a price row and at most 2 links; the
kept checks at most 3 rows of at most 42. G5 words: 52 / 60 / 24, names
left out (they are data). A guide entry that needs more than 7 rows fails
the data test.
"""

import json

import pytest

import play_states as ps
from server.al import playcards as pc
from server.al import playview as pv
from server.al import state as state_mod
from server.al import zoneguide
from server.al.state import SessionState, eval_card_text, price_card_text
from server.al.theorycraft import searchstr

NOW = 1_800_000_000.0


# -- caps --------------------------------------------------------------------------

def test_caps_are_the_plan_figures():
    assert pc.CAP_TITLE == ps.CAP_CONTEXT_TITLE == 38
    assert pc.CAP_ROW == ps.CAP_CONTEXT_ROW == 52
    assert pc.CONTEXT_ROWS == 7
    assert pc.CAP_SENTENCE == ps.CAP_ITEM_SENTENCE == 36
    assert pc.SENTENCE_ROWS == ps.ITEM_SENTENCE_ROWS == 2
    assert pc.COMPARE_ROWS == 5 and pc.MAX_LINKS == 2
    assert pc.CAP_KEPT == ps.CAP_KEPT_ROW == 42 and pc.KEPT_ROWS == 3
    assert (pc.WORDS_CONTEXT, pc.WORDS_ITEM, pc.WORDS_KEPT) == (52, 60, 24)
    assert pc.SEARCH_MAX == searchstr.MAX_LEN == 250
    assert pc.SAME_PRESS_S == state_mod.SAME_PRESS_S


def _words(text, names):
    for n in sorted((n for n in names if n), key=len, reverse=True):
        text = text.replace(n, " ")
    return pv.words(text)


def assert_context_caps(context, names=()):
    assert context is None or (isinstance(context, dict) and context)
    for mode, b in (context or {}).items():
        assert mode in pc.MODES and b["mode"] == mode
        assert len(b["title"]) <= pc.CAP_TITLE, b
        assert len(b["rows"]) <= pc.CONTEXT_ROWS, b
        assert all(len(r["text"]) <= pc.CAP_ROW for r in b["rows"]), b
        assert len(b["facts"]) <= pc.CAP_ROW, b
        total = sum(_words(t, names) for t in [b["title"], b["facts"]]
                    + [r["text"] for r in b["rows"]])
        assert total <= pc.WORDS_CONTEXT, (mode, total)


def assert_item_caps(item, names=()):
    if item is None:
        return
    assert item["word"] and item["glyph"] in ("[+]", "[-]", "[?]")
    assert 1 <= len(item["sentence"]) <= pc.SENTENCE_ROWS, item
    assert all(len(r) <= pc.CAP_SENTENCE for r in item["sentence"]), item
    rows = item["compare"]["rows"]
    assert len(rows) == pc.COMPARE_ROWS, item
    for r in rows:
        assert len(r["text"]) + (len(r["value"]) + 1 if r["value"] else 0) <= pc.CAP_COMPARE, r
    assert len(item["compare"]["label"]) <= pc.CAP_COMPARE
    assert set(item["price"]) == {"value", "source"}
    assert len(item["price"]["value"]) <= pc.CAP_PRICE and item["price"]["value"]
    assert len(item["price"]["source"]) <= pc.CAP_PRICE
    assert len(item["links"]) <= pc.MAX_LINKS
    for link in item["links"]:
        assert link["url"].startswith("https://") and link["label"]
    texts = ([item["word"], item["compare"]["label"], item["price"]["value"],
              item["price"]["source"]] + item["sentence"]
             + [r["text"] for r in rows] + [r["value"] for r in rows]
             + [x["label"] for x in item["links"]])
    assert sum(_words(t, names) for t in texts) <= pc.WORDS_ITEM


def assert_kept_caps(kept, names=()):
    if kept is None:
        return
    assert len(kept["rows"]) <= pc.KEPT_ROWS
    assert all(len(r["text"]) <= pc.CAP_KEPT for r in kept["rows"]), kept
    assert len(kept["empty"]) <= pc.CAP_KEPT
    total = sum(_words(r["text"], tuple(names) + tuple(r["item"] for r in kept["rows"])
                       + tuple(r["slot"] for r in kept["rows"])) for r in kept["rows"])
    assert total <= pc.WORDS_KEPT


# -- the block on the core's own snapshot -------------------------------------------

def test_first_run_snapshot_offers_setup_only():
    play = SessionState().snapshot()["play"]
    assert list(play["context"]) == ["setup"]
    assert play["item"] is None and play["kept"] is None
    json.dumps(play)


def test_view_never_raises_on_wrong_types():
    junk = [None, 1, "x", [], {}, {"a": 1}, [None, 1], float("nan"), True]
    keys = ("tailer", "diag", "build", "session_summary", "game_idle", "maps", "eval",
            "price", "in_hideout", "in_town", "area_id", "zone_guide", "zone_note",
            "campaign", "underlevel", "upgrades", "level", "deaths")
    for j in junk:
        pc.context_view(j)
        pc.check_view(j)
        for k in keys:
            for v in (j, {"current": j, "recent": [j], "checks": [j], "hints": [j],
                          "items": [j], "text": j, "optional": [j], "kind": "campaign",
                          "objective": j, "waystone": j, "comparisons": [j]}):
                snap = {k: v}
                assert_context_caps(pc.context_view(snap))
                item, kept = pc.check_view(snap)
                assert_item_caps(item)
                assert_kept_caps(kept)


# -- C: setup ------------------------------------------------------------------------

def _check(cid, status):
    return {"id": cid, "label": cid, "status": status, "detail": "", "fix": None}


def test_setup_block_rows():
    b = pc.setup_block({"tailer": {"consented": False, "path": None}})
    assert b["title"] == "Set up AshLight"
    assert [(r["kind"], r.get("glyph"), r["text"]) for r in b["rows"]] == [
        ("step", "[ ]", "Let AshLight read the game's log, read only:"),
        ("path", None, "Client.txt not found yet. Start the game once."),
        ("button", None, "Allow reading Client.txt"),
        ("step", "[ ]", "Your build: not set, optional"),
        ("step", "[ ]", "Prices: off, optional"),
        ("step", "[ ]", "Overlay: not running, optional"),
    ]
    assert b["facts"] == "Read only. AshLight never touches the game."
    path = "Games/" + "Steam Library/" * 6 + "logs/Client.txt"
    done = pc.setup_block({"tailer": {"consented": False, "path": path},
                           "build": {"loaded": True},
                           "diag": {"checks": [_check("web_data", "pass"),
                                               _check("overlay", "pass")]}})
    row = done["rows"][1]
    assert row["full"] == path and row["text"].endswith("logs/Client.txt")
    assert len(row["text"]) == pc.CAP_ROW and row["text"].startswith("...")
    assert [r["text"] for r in done["rows"][3:]] == ["Your build: loaded", "Prices: on",
                                                    "Overlay: on"]
    assert [r["glyph"] for r in done["rows"][3:]] == ["[+]"] * 3
    off = pc.setup_block({"tailer": {"consented": False},
                          "diag": {"checks": [_check("overlay", "off")]}})
    assert off["rows"][5]["text"] == "Overlay: off, optional"
    assert pc.setup_block({"tailer": {"consented": True}}) is None
    assert pc.setup_block({}) is None


# -- C: idle -------------------------------------------------------------------------

def test_idle_block_from_the_summary_card():
    card = {"reason": "idle", "reason_text": "after 20 minutes with no game activity",
            "ended_at": NOW, "played_s": 3725, "level_from": 12, "level_to": 15,
            "levels": 3, "per_hour": 2.9, "maps": 4, "deaths": 1,
            "lines": ["Played 1:02:05 and reached level 15.",
                      "Price movers: Example Orb up 61%, Other Shard down 20%."]}
    b = pc.idle_block({"game_idle": True, "session_summary": card})
    assert b["title"] == "Last session"
    assert [r["text"] for r in b["rows"]] == [
        "Played: 1:02:05", "Level: 12 to 15", "Pace: 2.9 levels an hour", "Maps: 4",
        "Deaths: 1", "Price movers: Example Orb up 61%, Other Shard..."]
    assert b["rows"][-1]["full"] == "Price movers: Example Orb up 61%, Other Shard down 20%"
    assert b["facts"] == f"Ended {pv.clock(NOW)} after 20 minutes with no game activity"
    live = pc.idle_block({"game_idle": True, "level": 9, "deaths": 2,
                          "maps": {"count": 0}, "tailer": {"last_line_at": NOW}})
    assert [r["text"] for r in live["rows"]] == ["Level: 9", "Maps: 0", "Deaths: 2"]
    assert live["facts"] == f"Last log line at {pv.clock(NOW)}"
    assert pc.idle_block({"game_idle": False, "session_summary": card}) is None


# -- C: map --------------------------------------------------------------------------

STRINGS = [{"id": "resists", "label": "Resistances you still need",
            "why": "Finds gear with the resistances your build has below the cap.",
            "text": '"fire res|cold res"'},
           {"id": "waystone", "label": "Waystones without risky mods",
            "why": "Finds waystones without the mods that are risky for your build.",
            "text": '"!reflect|regen"'}]


def _maps(**kw):
    base = {"count": 3, "done": 2, "current": None, "avg_s": 250, "per_hour": 5.24,
            "deaths_text": "1 death in maps.",
            "recent": [{"name": "Crypt", "area_level": 65, "time_s": 262, "deaths": 1}]}
    base.update(kw)
    return base


def test_map_block_inside_a_map():
    snap = {"maps": _maps(current={"name": "Sun Temple", "area_level": 66, "time_s": 192,
                                   "deaths": 0, "inside": True}),
            "eval": {"waystone": {"tier": 15, "risky": [{"label": "reflect"}]},
                     "text": {"head": "Risky for this build"}}}
    b = pc.map_block(snap)
    assert b["title"] == "Sun Temple, level 66"
    assert [r["text"] for r in b["rows"]] == [
        "This map: 3:12, no deaths", "Maps this session: 3, 5.2 an hour",
        "Average map: 4:10", "Last waystone: Risky for this build"]
    assert b["facts"] == "1 death in maps."


def test_map_block_in_the_hideout_after_a_map():
    snap = {"in_hideout": True, "maps": _maps(per_hour=None),
            "build": {"loaded": True, "search_strings": STRINGS}}
    b = pc.map_block(snap)
    assert b["title"] == "Between maps"
    assert [r["text"] for r in b["rows"]] == [
        "Last map: Crypt, 4:22, 1 death", "Maps this session: 3", "Average map: 4:10",
        "Waystones without risky mods"]
    copy = b["rows"][-1]
    assert copy["kind"] == "copy" and copy["copy"] == '"!reflect|regen"'
    assert pc.map_block({"in_hideout": True, "maps": _maps(count=0)}) is None
    assert pc.map_block({"maps": _maps()}) is None


# -- C: town -------------------------------------------------------------------------

def test_town_row_shows_in_town_only_with_a_build():
    zg = {"kind": "campaign", "zone": "Clearfell Encampment",
          "objective": "Town: talk to Renly for a gem, sell, then head into Clearfell.",
          "next": "Clearfell"}
    snap = {"area_id": "G1_town", "in_town": True, "zone_guide": zg,
            "build": {"loaded": True, "search_strings": STRINGS}}
    b = pc.town_block(snap)
    assert b["title"] == "In town"
    assert [(r["kind"], r["text"]) for r in b["rows"]] == [
        ("copy", "Resistances you still need"),
        ("text", "Town: talk to Renly for a gem, sell, then head into"),
        ("text", "Clearfell."),
        ("next", "Next: Clearfell.")]
    assert b["rows"][0]["copy"] == '"fire res|cold res"'
    no_build = pc.town_block(dict(snap, build={"loaded": False, "search_strings": STRINGS}))
    assert [r["kind"] for r in no_build["rows"]] == ["text", "text", "next"]
    # leaving town hides the row (and the block)
    assert pc.town_block(dict(snap, area_id="G1_2", in_town=False)) is None
    # the game's 250-character limit: a longer string is never offered
    long = [dict(STRINGS[0], text='"' + "a" * 260 + '"')]
    assert pc.town_block(dict(snap, build={"loaded": True, "search_strings": long})
                         )["rows"][0]["kind"] == "text"
    note = pc.town_block({"in_town": True, "zone_note": {"text": "Town: sell junk."}})
    assert [r["text"] for r in note["rows"]] == ["Town: sell junk."]
    hide = pc.town_block({"in_hideout": True,
                          "build": {"loaded": True, "search_strings": STRINGS}})
    assert hide["title"] == "In your hideout" and len(hide["rows"]) == 1


# -- C: guide ------------------------------------------------------------------------

def _guide(zone="Clearfell", area_id="G1_2", level=4, area_level=2, waypoint=True):
    doc = zoneguide.load()
    graph = {area_id: {"name": zone, "waypoint": waypoint, "town": False, "links": []}}
    return zoneguide.view(doc, graph, area_id, zone, False, level, area_level, None)


def test_guide_block_on_the_bundled_entry():
    zg = _guide()
    b = pc.guide_block({"zone_guide": zg})
    assert b["title"] == "Find the Grelwood exit; the Mud Burrow"
    assert b["full"] == zg["objective"]
    assert [(r["kind"], r["text"]) for r in b["rows"]] == [
        ("objective", "cave is a short detour."),
        ("bonus", "+10% cold resistance - beat Beira at a ritual site"),
        ("bonus", "near the middle."),
        ("layout", "The Mud Burrow entrance tends to sit near the"),
        ("layout", "waypoint."),
        ("next", "Next: Mud Burrow. Waypoint in this zone.")]
    assert b["facts"] == "Your level fits: clear what is on your way."
    # 7 rows fit, but the second bonus line would take the block to 58
    # words (G5 cap 52), so it leaves first
    words = sum(pv.words(t) for t in [b["title"], b["facts"]] + [r["text"] for r in b["rows"]])
    assert words - pv.words("Mud Burrow") <= pc.WORDS_CONTEXT


def test_guide_block_drops_the_lowest_priority_part_first():
    zg = _guide(level=1, area_level=9)
    hints = [{"id": "boss", "word": "Cold res 30%",
              "text": "This zone's boss deals mostly cold damage. Your build has 30% cold "
                      "resistance (the cap is 75%)."},
             {"id": "boots", "word": "Boots: no speed",
              "text": "Your build's boots have no movement speed. Boots with it help in "
                      "the campaign."}]
    b = pc.guide_block({"zone_guide": zg, "campaign": {"hints": hints},
                        "underlevel": {"text": "8 levels under this zone (zone level 9)."}})
    kinds = [r["kind"] for r in b["rows"]]
    # 9 rows and over 52 words wanted: the boots hint (7), the second bonus (6)
    # and then the layout (4) leave; the boss hint (3) stays
    assert kinds == ["objective", "bonus", "bonus", "hint", "next"]
    assert b["rows"][3]["text"] == "Boss: cold damage. Your cold res: 30%."
    assert b["facts"] == "8 levels under this zone (zone level 9)."
    assert pc.guide_block({"zone_guide": dict(zg, kind="endgame")}) is None
    assert pc.guide_block({"zone_guide": zg, "in_hideout": True}) is None


def test_next_row_ladder():
    near = {"next": "Mud Burrow", "waypoint": "No waypoint here. Nearest: The Riverbank."}
    assert pc._next_row(near)[0]["text"] == "Next: Mud Burrow. Nearest waypoint: The Riverbank."
    far = dict(near, waypoint="No waypoint here. Nearest: Clearfell Encampment Outer.")
    assert pc._next_row(far)[0]["text"] == "Next: Mud Burrow."
    assert pc._next_row({"waypoint": "Waypoint in this zone."})[0]["text"] == \
        "Waypoint in this zone."
    assert pc._next_row({}) is None


def _entry_view(entry, act):
    return {"kind": "campaign", "objective": entry.get("objective") or act.get("default"),
            "optional": zoneguide._optional(entry), "layout": entry.get("layout"),
            "next": entry.get("next"), "waypoint": zoneguide.WAYPOINT_YES}


def test_every_bundled_guide_entry_fits_7_rows():
    doc = zoneguide.load()
    over = []
    for key, act in doc["acts"].items():
        for zone, entry in act["zones"].items():
            need = pc.guide_rows_needed(_entry_view(entry, act))
            if need > pc.CONTEXT_ROWS:
                over.append(f"{key} {zone}: {need} rows")
    assert not over, "guide entries over 7 rows of 52: " + "; ".join(over)
    key, zone, _size = ps.longest_guide_entry(doc)
    assert pc.guide_rows_needed(_entry_view(doc["acts"][key]["zones"][zone],
                                            doc["acts"][key])) <= pc.CONTEXT_ROWS


def test_a_guide_entry_over_7_rows_fails_the_data_check():
    act = {"default": "Act 1."}
    entry = {"objective": "Beat the boss at the far end of the long and winding river path.",
             "layout": "A long layout note that needs two rows of the fifty-two character "
                       "width to say.",
             "optional": [{"kind": "gem", "text": "A first bonus line that is long enough to "
                                                  "need a second row here."},
                          {"kind": "resist", "text": "A second bonus line that is long enough "
                                                     "to need a second row too."}],
             "next": "The Next Zone"}
    assert pc.guide_rows_needed(_entry_view(entry, act)) == 8
    # the live block still fits: the lowest-priority part leaves
    b = pc.guide_block({"zone_guide": _entry_view(entry, act)})
    assert len(b["rows"]) <= pc.CONTEXT_ROWS


# -- I: the item card -------------------------------------------------------------------

def _comp(slot, verdict, delta, name="Old Grip", stats=()):
    return {"slot": slot, "verdict": verdict, "score_delta": delta, "empty": False,
            "equipped": {"name": name, "base": "Example Gloves"}, "stats": list(stats)}


def _stat(key, delta, score):
    return {"key": key, "delta": delta, "score_delta": score, "weighted": True}


STATS = [_stat("+# to maximum Life", 30, 30), _stat("#% increased Attack Speed", -12, -24),
         _stat("+#% to Fire Resistance", 15, 15), _stat("+#% to Cold Resistance", 10, 10),
         _stat("+#% to Lightning Resistance", -10, -10), _stat("+# to Strength", 8, 4)]


def _eval(**kw):
    card = {"ok": True, "error": None, "verdict": "upgrade", "slot": "Gloves",
            "score_delta": 21, "unidentified": False, "calc": {"source": "weights"},
            "item": {"name": "Grim Clutch", "base": "Example Gloves"},
            "comparisons": [_comp("Gloves", "upgrade", 21, stats=STATS)],
            "upgrade": {"url": "https://www.pathofexile.com/trade2/search/poe2/Standard?q=u"},
            "at": NOW}
    card.update(kw)
    return dict(card, text=eval_card_text(card))


def _price(**kw):
    card = {"status": "link", "item": {"name": "Grim Clutch"}, "league": "Standard",
            "url": "https://www.pathofexile.com/trade2/search/poe2/Standard?q=t",
            "ninja": None, "at": NOW}
    card.update(kw)
    return dict(card, text=price_card_text(card))


def test_item_card_verdict():
    item = pc.item_view({"eval": _eval(), "price": _price()})
    assert (item["kind"], item["glyph"], item["word"], item["name"]) == (
        "verdict", "[+]", "Upgrade", "Grim Clutch")
    assert item["sentence"] == ["21 points more than your Gloves."]
    assert item["compare"]["label"] == "vs Old Grip"
    assert item["compare"]["rows"] == [
        {"text": "+30 to maximum Life", "value": "+30 points"},
        {"text": "-12% increased Attack...", "value": "-24 points"},
        {"text": "+15% to Fire Resistance", "value": "+15 points"},
        {"text": "+10% to Cold Resistance", "value": "+10 points"},
        {"text": "-10% to Lightning...", "value": "-10 points"}]
    assert item["price"] == {"value": "Trade link ready", "source": ""}
    assert [x["label"] for x in item["links"]] == ["Trade search", "Upgrade search"]
    assert item["at"] == NOW
    assert_item_caps(item, names=["Grim Clutch", "Old Grip"])


def test_item_card_other_slots_and_pob_line():
    ev = _eval(calc={"source": "pob"}, comparisons=[
        dict(_comp("Ring 1", "upgrade", 21, stats=STATS[:2]), dps={"pct": 4.2, "old": 1,
                                                                     "new": 2},
             ehp={"pct": -1, "old": 1, "new": 1}),
        _comp("Ring 2", "downgrade", -3, name="Band")], slot="Ring 1")
    item = pc.item_view({"eval": ev})
    assert item["compare"]["label"] == "vs Old Grip (+1 other slot)"
    assert item["compare"]["rows"][0] == {"text": "DPS +4.2%, EHP -1%", "value": ""}
    assert item["compare"]["rows"][3:] == [{"text": "", "value": ""}] * 2
    assert item["price"] == {"value": "No price for this check", "source": ""}
    assert [x["label"] for x in item["links"]] == ["Upgrade search"]


def test_item_card_price_of_another_press_is_not_shown():
    item = pc.item_view({"eval": _eval(), "price": _price(at=NOW - 30)})
    assert item["price"]["value"] == "No price for this check"
    off = pc.item_view({"eval": _eval(), "price": _price(status="off", url=None)})
    assert off["price"] == {"value": "Web data is off",
                            "source": "Turn it on in Prices and web data"}
    assert [x["label"] for x in off["links"]] == ["Upgrade search"]


def test_item_card_error_and_waystone():
    err = pc.item_view({"eval": _eval(ok=False, error="not an item", verdict=None,
                                      comparisons=[], upgrade=None)})
    assert (err["kind"], err["glyph"], err["word"]) == ("error", "[-]", "Not an item")
    assert err["sentence"] == ["The clipboard did not hold an item."]
    assert err["compare"]["rows"] == [{"text": "", "value": ""}] * 5
    ws = {"tier": 15, "risky": [{"label": "Monsters reflect 18% of Elemental Damage",
                                 "short": "reflect"}],
          "rewards": [{"pct": 40, "label": "Item Rarity", "short": "rarity"}],
          "build_loaded": True}
    way = pc.item_view({"eval": _eval(waystone=ws, comparisons=[], upgrade=None)})
    assert (way["kind"], way["glyph"], way["word"]) == ("waystone", "[?]", "Risky")
    assert way["sentence"] == ["Risky for this build: Monsters", "reflect 18% of Elemental Damage."]
    assert way["compare"]["rows"][:2] == [
        {"text": "Rewards: +40% Item Rarity.", "value": ""},
        {"text": "Monsters reflect 18% of...", "value": "risky"}]
    assert_item_caps(err)
    assert_item_caps(way)


def test_item_card_long_strings_stay_under_the_caps():
    long = ps.text_at(400)
    stats = [_stat(long + " #", 9, 9)] * 9
    ev = _eval(item={"name": long, "base": long}, slot=long,
               comparisons=[_comp(long, "sidegrade", 0.4, name=long, stats=stats)] * 3,
               verdict="sidegrade")
    item = pc.item_view({"eval": ev, "price": _price(ninja={
        "value": 12345.678, "unit": long, "league": long, "listings": 3, "change": 55.5})})
    assert_item_caps(item, names=[long])
    assert item["name"] == long  # names are data: never cut here


# -- U: kept checks ------------------------------------------------------------------------

def _notice(name, slot, delta, at, source="weights"):
    return {"name": name, "base": "Example", "slot": slot, "score_delta": delta,
            "source": source, "at": at, "new": False}


def test_kept_checks_best_three_now():
    items = [_notice("Grim Clutch", "Gloves", 21, NOW - 50),
             _notice("Example Unique", "Weapon 1", 95, NOW - 90),
             _notice("Ring", "Ring 1", 1, NOW - 10),
             _notice("Belt", "Belt", 21, NOW - 5, source="pob")]
    kept = pc.kept_view({"build": {"loaded": True},
                         "upgrades": {"build_loaded": True, "checked": 6, "items": items}})
    assert [r["text"] for r in kept["rows"]] == [
        "[+] Upgrade +95 points, Example Unique",
        "[+] Upgrade +21%, Belt, Belt, " + pv.clock(NOW - 5),
        "[+] Upgrade +21 points, Grim Clutch"]
    assert kept["rows"][2]["full"] == "Upgrade +21 points: Grim Clutch, Gloves, " + \
        pv.clock(NOW - 50)
    assert kept["empty"] == "" and kept["checked"] == 6
    long = ps.text_at(80)
    cut = pc.kept_view({"build": {"loaded": True},
                        "upgrades": {"items": [_notice(long, "Gloves", 12.25, NOW)]}})
    assert cut["rows"][0]["text"].endswith("..., Gloves")
    assert_kept_caps(cut)
    none = pc.kept_view({"build": {"loaded": True}, "upgrades": {"items": []}})
    assert none == {"rows": [], "empty": "None of your checks is an upgrade now.",
                    "checked": 0}
    nob = pc.kept_view({"build": {"loaded": False}, "upgrades": {"items": items}})
    assert nob["rows"] == [] and nob["empty"] == "Load a build to rank your checks."
    assert pc.kept_view({}) is None


# -- the core's state, end to end ------------------------------------------------------

def test_state_snapshot_carries_the_cards():
    st = SessionState(clock=lambda: NOW)
    st.set_tailer(consented=True, reading=True, path="Client.txt")
    st.set_build_info({"loaded": True, "class_name": "Ranger", "level": 80})
    card = _eval()
    card.pop("text")
    card.pop("at")
    st.set_eval(card, at=NOW)
    st.set_upgrades({"character": None, "checked": 1, "build_loaded": True,
                     "items": [_notice("Grim Clutch", "Gloves", 21, NOW)]})
    snap = st.snapshot()
    play = snap["play"]
    assert play["context"] is None  # opted in, no zone yet: the renderer's none
    assert play["item"]["word"] == "Upgrade"
    assert [r["item"] for r in play["kept"]["rows"]] == ["Grim Clutch"]
    assert play == pv.view({k: v for k, v in snap.items() if k != "play"})
    json.dumps(play)


# -- the evidence-pack states ---------------------------------------------------------------

PACK = {"a": ["setup"], "c": ["guide"], "d": ["idle", "guide"], "f": ["map"],
        "long": ["guide"]}


def _names(snap):
    out = [snap.get("character"), snap.get("zone")]
    ev = snap.get("eval") or {}
    out += [(ev.get("text") or {}).get("item")]
    for c in ev.get("comparisons") or ():
        out.append(((c or {}).get("equipped") or {}).get("name"))
    out += [(snap.get("tailer") or {}).get("path")]
    return [n for n in out if isinstance(n, str) and n]


@pytest.mark.server
@pytest.mark.parametrize("name", tuple(PACK))
def test_pack_states_compose_the_cards(name, tmp_path):
    with ps.open_state(name, tmp_path / name) as st:
        snap = st.state()
    play = snap["play"]
    names = _names(snap)
    assert list(play["context"] or {}) == PACK[name]
    assert_context_caps(play["context"], names)
    assert_item_caps(play["item"], names)
    assert_kept_caps(play["kept"], names)
    if snap.get("eval"):
        assert play["item"]["word"] == snap["eval"]["text"]["word"] or \
            play["item"]["kind"] == "error"
    else:
        assert play["item"] is None
    assert play == pv.view({k: v for k, v in snap.items() if k != "play"})
