"""RUN-LEDGER-CORE: the parse ledger (server/al/logshapes.py; research 0051
'Design: the parse ledger', F-061). Seeded, stdlib only; no file is
written (the writer is RUN-LEDGER-WIRE's)."""

import ast
import json
import random
import re
import string
from pathlib import Path

from server.al import logshapes, parser

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "tests" / "fixtures" / "client_live_shapes.txt"
P = "2026/11/16 20:00:00 1000 1a2b3c4d [INFO Client 4242] "
SEED = 20261118

# The placeholders, spelled out here so the test does not trust the module.
HOLDERS = {"<n>", "<addr>", "<path>", "<host>", "<hex>", "<w>", "<name>",
           "<class>", "<text>", "<more>"}
PUNCT = set(".,;:!?()[]{}\"'-")
TAGS_OK = re.compile(r"^[A-Z][A-Z_]{1,15}$")


def _feed(lines, now=1000.0, step=0.0, led=None):
    led = led or logshapes.Ledger()
    for i, ln in enumerate(lines):
        led.observe(ln, parser.parse_line(ln), now=now + i * step)
    return led


def _token_ok(tok):
    i, j = 0, len(tok)
    while i < j and tok[i] in PUNCT:
        i += 1
    while j > i and tok[j - 1] in PUNCT:
        j -= 1
    core = tok[i:j]
    if not core:
        return 0 < len(tok) <= 3
    if core in HOLDERS:
        return True
    return (re.fullmatch(r"[a-z']+", core) is not None
            and core in (logshapes.ALLOW | logshapes.TEMPLATE_WORDS))


def _stored_shapes(led):
    data = json.loads(led.dumps())
    return [row[1] for row in data["shapes"]]


# -- hostile generator ----------------------------------------------------

_LETTERS = string.ascii_letters + "\u00e4\u00f6\u00df\u0416\u042f\u6f22\u5b57"


def _secret(rng):
    """A token no allow word or placeholder can equal: 8 characters, a
    letter first, at least one digit."""
    body = [rng.choice(_LETTERS)] + [rng.choice(_LETTERS + string.digits)
                                     for _ in range(6)] + [rng.choice(string.digits)]
    return "".join(body)


def _hostile_text(rng, secrets):
    out = []
    for _ in range(rng.randint(1, 30)):
        r = rng.random()
        if r < 0.35:
            out.append(rng.choice(sorted(logshapes.ALLOW)))
        elif r < 0.55:
            s = _secret(rng)
            secrets.add(s)
            out.append(s)
        elif r < 0.62:
            s = _secret(rng)
            secrets.add(s)
            out.append(rng.choice([f"..\\{s}\\Client.txt", f"/home/{s}/x",
                                   f"{s}@mail{s}.com", f"https://{s}.example/a"]))
        elif r < 0.68:
            out.append(".".join(str(rng.randint(0, 255)) for _ in range(4))
                       + f":{rng.randint(1, 65535)}")
        elif r < 0.74:
            out.append("".join(rng.choice("0123456789abcdef") for _ in range(40)))
        elif r < 0.80:
            out.append(str(rng.randint(-10 ** 6, 10 ** 6)))
        elif r < 0.86:
            s = _secret(rng)
            secrets.add(s)
            out.append(rng.choice(['"', "(", "'", "["]) + s + rng.choice(['".', ").", "!", "]"]))
        else:
            out.append(rng.choice(sorted(logshapes.ALLOW)).upper())
    return " ".join(out)


def _hostile_line(rng, secrets):
    name = _secret(rng)
    secrets.add(name)
    text = _hostile_text(rng, secrets)
    kind = rng.randrange(17)
    body = [
        ": " + text,
        text,
        f": {name} has been slain by {text}",
        f": {name} ({_secret(rng)}) is now level 7 {text}",
        f": {name} has joined the area and {text}",
        f": AFK mode is now ON. Autoreply \"{text}\"",
        f"@From {name}: {text}",
        f"@From <{name}> {name}: Hi, I would like to buy your {text}",
        f"@To {name}: Hi, I'd like to buy your {text}",
        f"#{name}: {text}",
        f"{name}: {text}",
        f"{name * 7}: {text}",
        f"{name}:{text}",
        f"[{name}] {text}",
        f"[SCENE] Set Source [{text}]",
        f"[WINDOW] {text}",
        f'Generating level 3 area "{name}" with seed 1',
    ][kind]
    r = rng.random()
    if r < 0.03:
        return text  # no prefix
    if r < 0.05:
        return P + body + " " + "x" * 600  # long
    return P + body


def test_10000_hostile_lines_store_only_allow_list_tokens():
    rng = random.Random(SEED)
    secrets = set()
    lines = [_hostile_line(rng, secrets) for _ in range(10000)]
    led = _feed(lines, step=7.0)
    text = led.dumps()
    assert text.isascii()
    data = json.loads(text)
    assert data["shapes"], "the generator must reach the shape ledger"
    for shape in _stored_shapes(led):
        for tok in shape.split(" "):
            assert _token_ok(tok), (tok, shape)
        assert logshapes.is_safe_shape(shape)
    for tag in data["tags"]:
        assert TAGS_OK.match(tag), tag
    # Area ids are engine constants (Generating level lines only); every
    # other secret, in any form, is absent from the file text.
    rest = dict(data, area_ids={})
    flat = json.dumps(rest).lower()
    for s in secrets:
        if s.isascii():
            assert s.lower() not in flat, s
    for aid in data["area_ids"]:
        assert re.fullmatch(r"[A-Za-z0-9_]{1,48}", aid), aid


def test_chat_whisper_and_speech_like_lines_are_never_stored():
    lines = [P + b for b in (
        "#Chatterbox: you have been slain in the area",
        "$<MKT> Seller: trade is now accepted",
        "%Partyguy: Emberwright (Witch) is now level 99",
        "&Guildie: you have joined the guild",
        "@From Pal: you are now level 3 in the area",
        "@From <GLD> Pal: hey there, you have mail",
        "@To Pal: on my way to your hideout",
        "@From Quietfox: Hi, I would like to buy your Plain Belt in Standard "
        '(stash tab "Dump"; position: left 1, top 2)',
        "Riverside Miller: Grind you down!",
        "Some Npc Name: you have been slain",
        "#Weird no colon at all",
    )]
    led = _feed(lines)
    assert _stored_shapes(led) == []
    c = led.counts
    assert c["chat_like"] == 1 and c["speech_like"] == 2
    # the parsed chat and whispers count only their pattern ids
    for pid in ("chat.global", "chat.trade", "chat.party", "chat.guild",
                "whisper_in", "whisper_in.guild", "whisper_out", "trade.unpriced"):
        assert pid in led.hits, pid
    text = led.dumps()
    for word in ("Chatterbox", "Seller", "Pal", "Quietfox", "Belt", "Dump",
                 "Grind", "Miller", "mail", "hey"):
        assert word.lower() not in text.lower(), word


def test_long_speaker_and_colon_without_space_are_never_stored():
    speaker = "Averyveryverylongspeakernamethatkeepsgoingonandon"  # 49 characters
    assert len(speaker) > 48
    lines = [P + b for b in (
        speaker + ": you have been slain in the area",
        speaker + " " + speaker + ": you are now level 3",
        "Pal:you have joined the area",
        "Pal :you have left",
        "Someone said:: you have been",
        "x" * 300 + ": you have",
    )]
    led = _feed(lines)
    assert _stored_shapes(led) == []
    assert led.counts["speech_like"] == len(lines)
    for cls in ("system", "plain"):
        assert led.counts[cls] == 0


def test_death_line_of_a_character_named_like_an_allow_word():
    # The real line is an event: counted by id, never shaped.
    led = _feed([P + ": Trade has been slain.", P + ": Trade has committed suicide."])
    assert led.hits["death"][0] == 1 and led.hits["death.suicide"][0] == 1
    assert _stored_shapes(led) == []
    # A drifted death line becomes a shape; the name slot is place-held.
    led = _feed([P + ": Trade has been slain by a Zombie.",
                 P + ": Level (Party) is now level 12 again",
                 P + ": You has joined the area of guild"])
    shapes = _stored_shapes(led)
    assert "<name> has been slain by a <w>." in shapes
    assert "<name> (<class>) is now level <n> again" in shapes
    assert "<name> has joined the area of guild" in shapes
    for s in shapes:
        assert not s.startswith(("trade", "level", "you")), s
    assert logshapes.mask("Trade has been slain.") == "<name> has been slain."
    # The AFK / DND autoreply (the player's own words) is place-held too.
    assert logshapes.mask('AFK mode is now ON. Autoreply "you have trade"') == (
        "afk mode is now on. <text>")


def test_live_shapes_fixture_yields_expected_pattern_ids():
    lines = LIVE.read_text(encoding="ascii").splitlines()
    led = _feed(lines)
    assert set(led.hits) == {
        "log_opened", "scene.set", "scene.unknown", "scene.null", "scene.zone",
        "scene.act", "session_connect", "area.campaign", "area.act.G1",
        "chat.global", "chat.trade", "system.unknown", "level_up",
        "trade_cancelled"}
    assert led.hits["scene.set"][0] == 15 and led.hits["area.act.G1"][0] == 2
    assert led.tags == {"WINDOW": 1}
    assert sorted(_stored_shapes(led)) == [
        "<w> to <w>() after level generation was <w>",
        "you can't send whispers until you are level <n>"]
    assert led.counts["speech_like"] == 1 and led.area_ids == {}
    drift = logshapes.Drift()
    for ln in lines:
        drift.observe(ln, parser.parse_line(ln))
    assert drift.total == 0 and not drift.due


def test_file_text_under_64_kb_after_1000000_lines():
    rng = random.Random(SEED + 1)
    words = sorted(logshapes.ALLOW)
    pool = []
    for i in range(5000):
        r = i % 10
        if r < 4:  # distinct worst-size shapes: 24 allow words, never a slot
            pool.append(P + ": " + " ".join(rng.choice(words) for _ in range(24)))
        elif r < 5:
            pool.append(P + "[" + "".join(rng.choice(string.ascii_uppercase)
                                          for _ in range(12)) + "] x")
        elif r < 6:
            pool.append(P + 'Generating level 3 area "Zz'
                        + "".join(rng.choice(string.ascii_letters) for _ in range(44))
                        + '" with seed 1')
        else:
            pool.append(P + "[SCENE] Set Source [The Riverbank]")
    led = logshapes.Ledger()
    parsed = [(ln, parser.parse_line(ln)) for ln in pool]
    now = 1795000000.0
    for n in range(1000000):
        ln, ev = parsed[n % len(parsed)]
        led.observe(ln, ev, now=now + n * 0.05)
    text = led.dumps()
    assert len(text.encode("ascii")) < 64 * 1024
    data = json.loads(text)
    assert len(data["shapes"]) <= logshapes.MAX_SHAPES
    assert len(data["tags"]) == logshapes.MAX_TAGS and data["tags_dropped"] > 0
    assert len(data["area_ids"]) == logshapes.MAX_AREA_IDS
    assert data["evicted"] > 0
    assert sum(data["counts"].values()) == 1000000


def test_two_sighting_rule_60_s_apart():
    line = P + ": You have been removed"
    led = logshapes.Ledger()
    led.observe(line, parser.parse_line(line), now=1000.0)
    led.observe(line, parser.parse_line(line), now=1059.0)
    assert led.confirmed() == []
    led.observe(line, parser.parse_line(line), now=1060.0)
    assert led.confirmed() == [("sys", "you have been <w>")]
    row = json.loads(led.dumps())["shapes"][0]
    assert row[2] == 3 and row[5] is True
    # Hour grain: stored times carry no minutes or seconds.
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}", row[3])
    # A shape read back from a file re-arms: two sightings in this run.
    led2 = logshapes.Ledger.from_dict(json.loads(led.dumps()))
    other = P + ": Your party is full again"
    for now in (5000.0, 5030.0):
        led2.observe(other, parser.parse_line(other), now=now)
    assert ("sys", "your party is full again") not in led2.confirmed()
    led2.observe(other, parser.parse_line(other), now=5060.0)
    assert ("sys", "your party is full again") in led2.confirmed()


# -- supporting properties -------------------------------------------------

def test_from_dict_drops_unsafe_or_malformed_content():
    data = {"schema": 1,
            "hits": {"death": [2, "2026-11-18T21", "2026-11-18T22"],
                     "Bad Id": [1, "2026-11-18T21", "2026-11-18T21"],
                     "level_up": [1, "2026-11-18 21:05", "x"]},
            "area_ids": {"G9_odd": [1, "2026-11-18T21", "2026-11-18T21"],
                         "has space": [1, "2026-11-18T21", "2026-11-18T21"]},
            "tags": {"SCENE": 3, "lower": 1},
            "counts": {"event": 5, "nope": 1},
            "shapes": [["sys", "you have been <w>", 2, "2026-11-18T21", "2026-11-18T21", True],
                       ["sys", "Emberwright says hello", 1, "2026-11-18T21",
                        "2026-11-18T21", False],
                       ["chat", "you", 1, "2026-11-18T21", "2026-11-18T21", False]],
            "evicted": 4}
    led = logshapes.Ledger.from_dict(data)
    assert set(led.hits) == {"death"}
    assert set(led.area_ids) == {"G9_odd"}
    assert led.tags == {"SCENE": 3}
    assert led.counts["event"] == 5 and "nope" not in led.counts
    assert list(led.shapes) == [("sys", "you have been <w>")]
    assert led.evicted == 4
    assert logshapes.Ledger.from_dict({"schema": 2}).hits == {}
    assert logshapes.Ledger.from_dict("junk").shapes == {}


def test_near_miss_keeps_template_words_only():
    line = (P + "@From <GLD> Pal: Hi, I would like to buy your Grim Ring listed "
            "for 5 exalted at Standard (stash tab \"Sale\"; position: left 3, top 7) you have")
    led = _feed([line])
    assert led.counts["near_miss"] == 1
    (shape,) = _stored_shapes(led)
    assert shape.startswith("hi, i would like to buy your <w> listed for <n> <w>")
    assert "you have" not in shape and "pal" not in shape.lower()


def test_dirty_only_on_meaningful_change():
    led = logshapes.Ledger()
    line = P + "[SCENE] Set Source [The Riverbank]"
    ev = parser.parse_line(line)
    led.observe(line, ev, now=1000.0)
    assert led.dirty
    led.dirty = False
    led.observe(line, ev, now=1010.0)
    assert not led.dirty  # a bare count increment rides along
    led.observe(line, ev, now=1000.0 + 3600)
    assert led.dirty  # the last-seen hour moved


def test_counters_and_classes_hold_no_content():
    c = logshapes.Counters()
    for ln in LIVE.read_text(encoding="ascii").splitlines():
        c.observe(ln, parser.parse_line(ln))
    snap = c.snapshot()
    assert set(snap) == set(logshapes.CLASSES)
    assert all(isinstance(v, int) for v in snap.values())
    assert snap["event"] == 24 and snap["tag"] == 1


def test_live1_items_and_unverified_ids_are_real_pattern_ids():
    lines = [P + b for b in (
        ": Emberwright has been slain.", ": Emberwright has committed suicide.",
        "@From Pal: hi", "@From <G> Pal: hi", "@To Pal: hi",
        "%Pal: hi", "&Pal: hi", ": AFK mode is now ON.", ": AFK mode is now OFF.",
        ": DND mode is now ON.", ": DND mode is now OFF.",
        ": Pal has joined the area.", ": Pal has left the area.", ": Trade accepted.",
        ": You have entered Clearfell.", "[SCENE] Load Source [Felled Hideout]",
        "Connecting to instance server at 10.0.0.1:6112",
        'Generating level 2 area "HideoutFelled" with seed 1',
        'Generating level 60 area "C_G1_1" with seed 1',
        'Generating level 65 area "MapCrypt" with seed 1',
        'Generating level 30 area "P1_1" with seed 1',
        '@From Tw: Hi, I would like to buy your Ring listed for 5 exalted in Standard '
        '(stash tab "S"; position: left 3, top 7)',
        "@From Qf: Hi, I would like to buy your Belt in Standard "
        '(stash tab "D"; position: left 1, top 2)',
        "@From Cm: Hi, I'd like to buy your 10 Chaos Orb for my 1 Divine Orb in Standard.",
    )]
    led = _feed(lines)
    for item, ids in logshapes.LIVE1_ITEMS.items():
        assert any(i in led.hits for i in ids), item
    for pid in logshapes.UNVERIFIED:
        assert pid in led.hits, pid
    assert "area.interlude" in led.hits and "area.act.P1" in led.hits
    assert led.hits["area.act.C1"][0] == 1
    # every UNVERIFIED pattern id is named in parser.py's comments
    src = (ROOT / "server" / "al" / "parser.py").read_text(encoding="utf-8")
    for pid in logshapes.UNVERIFIED:
        assert pid in src, pid


def test_module_does_no_io():
    tree = ast.parse((ROOT / "server" / "al" / "logshapes.py").read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add("." * node.level + (node.module or ""))
        elif isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)):
            name = getattr(node.func, "id", None) or node.func.attr
            assert name not in ("open", "write_text", "read_text", "write_bytes",
                                "replace", "unlink", "mkdir"), name
    assert mods == {"json", "re", "time", "."}, mods
