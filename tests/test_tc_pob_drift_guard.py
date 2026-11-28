"""MATH-POB-DRIFT-GUARD: fail loudly when the pinned Path of Building PoE2
checkout no longer has the API shape bridge.lua relies on (decision 0028),
so a TC-DRIFT pin move (decision 0025) cannot silently break the calc.

Static part: reads the installed, unmodified checkout's Lua sources (no
luajit needed) for every name bridge.lua uses: the HeadlessWrapper launch
object and callbacks, the BUILD mode, the items / calcs tabs and the item
class. Live part: the bridge starts, finds the launch object, loads the
reference build and PoB's output table still carries the keys calcwire
maps. Each failure names what moved, where, and what to update.

Skips when the checkout (static) or the component / reference (live) is
absent; tests/test_tc_bridge.py keeps the fake-bridge protocol tests.
"""

import re

import pytest

from tc_live_util import LIVE_CALC, LIVE_REF, reference

from server.al.theorycraft import bridge, calcwire

try:
    COMP = bridge.component_paths()
    SRC = COMP["pob_src"]
except (OSError, ValueError, KeyError):  # pins unreadable: nothing to guard
    COMP, SRC = None, None
HAVE_SRC = SRC is not None and (SRC / "HeadlessWrapper.lua").is_file()
BRIDGE_LUA = bridge.SCRIPT.read_text(encoding="ascii")

STATIC = pytest.mark.skipif(not HAVE_SRC, reason="pinned PoB checkout absent "
                            "(setup.ps1 -TcCalc)")

FIX_HINT = ("Update server/al/theorycraft/bridge.lua (and this guard) before "
            "moving the PoB pin in config/tc_pins.json (TC-DRIFT, decision 0025).")

# (file under src/, regex that must match, what it is, the bridge.lua token
# that relies on it)
# A rel of "A.lua|B.lua" passes when any one of those files matches.
# TC-BRIDGE-NEXT: the launch object rows accept either launch shape: the
# pinned `local mainObject` read through runCallback's upvalue, or a global
# `__mainObject__` (the expected 1.0-era shape), set in HeadlessWrapper.lua
# or Launch.lua.
LAUNCH_FILES = "HeadlessWrapper.lua|Launch.lua"
MAIN_OBJ = r"(?:mainObject|__mainObject__)"
SHAPE = [
    (LAUNCH_FILES, r"^\s*(local\s+)?" + MAIN_OBJ + r"\b", "the launch object "
     "variable `mainObject` (local or global) or the global `__mainObject__`",
     "mainObject"),
    (LAUNCH_FILES, r"function\s+SetMainObject\s*\(|^\s*__mainObject__\s*=",
     "SetMainObject() or a `__mainObject__ =` assignment", "__mainObject__"),
    ("HeadlessWrapper.lua", r"function\s+runCallback\s*\(", "runCallback()",
     "runCallback"),
    ("HeadlessWrapper.lua", r"runCallback[\s\S]*" + MAIN_OBJ + r"\[name\]",
     "runCallback() calling mainObject[name] or __mainObject__[name] (bridge.lua "
     "reads mainObject from its upvalue, else the global)", "getupvalue"),
    ("HeadlessWrapper.lua", r"function\s+loadBuildFromXML\s*\(", "loadBuildFromXML()",
     "loadBuildFromXML"),
    ("HeadlessWrapper.lua", r"dofile\(\s*\"Launch\.lua\"\s*\)", "dofile(\"Launch.lua\")",
     "dofile"),
    ("HeadlessWrapper.lua", r"promptMsg", "mainObject.promptMsg", "promptMsg"),
    ("Modules/Main.lua", r"self\.modes\[\"BUILD\"\]", "main.modes[\"BUILD\"]",
     'modes["BUILD"]'),
    ("Modules/Main.lua", r"function\s+main:SetMode\s*\(", "main:SetMode()", "SetMode"),
    ("Modules/Build.lua", r"self\.itemsTab\s*=\s*new\(\"ItemsTab\"", "build.itemsTab",
     "itemsTab"),
    ("Modules/Build.lua", r"self\.calcsTab\s*=\s*new\(\"CalcsTab\"", "build.calcsTab",
     "calcsTab"),
    ("Modules/Build.lua", r"self\.buildFlag\s*=\s*true", "build.buildFlag", "buildFlag"),
    ("Modules/Common.lua", r"function\s+new\s*\(\s*className", "new(className, ...)",
     'new("Item"'),
    ("Classes/ItemsTab.lua", r"self\.slots\s*=", "itemsTab.slots", ".slots["),
    ("Classes/ItemsTab.lua", r"function\s+ItemsTabClass:AddItem\s*\(\s*item\s*,\s*noAutoEquip",
     "ItemsTab:AddItem(item, noAutoEquip, ...)", "AddItem(item, true)"),
    ("Classes/ItemsTab.lua", r"function\s+ItemsTabClass:PopulateSlots\s*\(",
     "ItemsTab:PopulateSlots()", "PopulateSlots"),
    ("Classes/ItemsTab.lua", r"newClass\(\"ItemsTab\",\s*\"UndoHandler\"",
     "ItemsTab inheriting UndoHandler", "AddUndoState"),
    ("Classes/UndoHandler.lua", r"function\s+UndoHandlerClass:AddUndoState\s*\(",
     "UndoHandler:AddUndoState()", "AddUndoState"),
    ("Classes/CalcsTab.lua", r"function\s+CalcsTabClass:BuildOutput\s*\(",
     "CalcsTab:BuildOutput()", "BuildOutput"),
    ("Classes/CalcsTab.lua", r"self\.mainOutput\s*=", "calcsTab.mainOutput", "mainOutput"),
    ("Classes/Item.lua", r"function\s+ItemClass:NormaliseQuality\s*\(",
     "Item:NormaliseQuality()", "NormaliseQuality"),
    ("Classes/Item.lua", r"function\s+ItemClass:GetPrimarySlot\s*\(",
     "Item:GetPrimarySlot()", "GetPrimarySlot"),
    ("Classes/ItemSlotControl.lua", r"function\s+ItemSlotClass:SetSelItemId\s*\(",
     "ItemSlot:SetSelItemId()", "SetSelItemId"),
    # TC-CALC-CONFINE-LUA: the lockdown runs after the HeadlessWrapper load,
    # so PoB's whole start (OnInit plus a first OnFrame) must happen inside
    # that load; lazy lcurl requires stay skipped by PoB's own require
    # wrapper (the lockdown empties package.cpath); PoB deletes a build file
    # only for its "~~temp~~" build, which the bridge never loads.
    ("HeadlessWrapper.lua", r"runCallback\(\"OnInit\"\)\s*\n\s*runCallback\(\"OnFrame\"\)",
     "PoB's start (OnInit plus one OnFrame) inside the HeadlessWrapper load", "lockdown"),
    ("HeadlessWrapper.lua", r"function\s+require\s*\([\s\S]{0,200}name\s*==\s*\"lcurl\.safe\"",
     "HeadlessWrapper's require skipping lcurl.safe", 'package.cpath = ""'),
    ("Modules/Build.lua", r"buildName\s*==\s*\"~~temp~~\"[\s\S]{0,200}os\.remove\(",
     "os.remove of the build file only for a \"~~temp~~\" build", "os.remove = function"),
]

# TC-CALC-CONFINE-LUA: what the lockdown in bridge.lua takes away must stay
# unused by PoB's code (top-level src/*.lua, Classes/, Modules/) and its Lua
# runtime libraries (runtime/lua/). Export/ is PoB's developer data tool and
# never loads headless. (regex, what is dropped, the bridge.lua token, scan
# the runtime libraries too)
DROPPED_RE = r"getlocal|setlocal|getupvalue|setupvalue|upvalueid|upvaluejoin|getregistry"
LOCKDOWN = [
    (r"\bos\.execute\b", "os.execute", "os.execute = nil", True),
    (r"\bio\.popen\b", "io.popen", "io.popen = nil", True),
    (r"\bos\.tmpname\b", "os.tmpname", "os.tmpname = nil", True),
    (r"\bpackage\.loadlib\b", "package.loadlib", "package.loadlib = nil", True),
    (r"\bio\.output\b", "io.output", "io.output = function", True),
    (r"\bdebug\.(?:" + DROPPED_RE + r"|setmetatable|setfenv|debug)\b",
     "the debug functions the lockdown drops", '"getupvalue"', True),
    # runtime/lua/sha2.lua picks ffi up optionally at start (before the
    # lockdown) and keeps its own reference; PoB's own code must not need it
    (r"\brequire\s*\(?\s*[\"']ffi[\"']", "require of ffi", 'package.loaded["ffi"] = nil',
     False),
]


def _pob_code_files(with_runtime):
    files = sorted(SRC.glob("*.lua"))
    for sub in ("Classes", "Modules"):
        files += sorted((SRC / sub).rglob("*.lua"))
    if with_runtime:
        files += sorted((SRC.parent / "runtime" / "lua").rglob("*.lua"))
    return files


def test_guard_covers_what_bridge_lua_uses():
    """Every guarded name is still used by bridge.lua (no stale rows), and
    the PoB names bridge.lua calls are all guarded."""
    for _, _, what, token in SHAPE:
        assert token in BRIDGE_LUA, f"guard row for {what}: bridge.lua no longer uses {token!r}"
    for _, what, token, _ in LOCKDOWN:
        assert token in BRIDGE_LUA, f"lockdown row for {what}: bridge.lua no longer has {token!r}"
    for name in DROPPED_RE.split("|"):
        assert f'"{name}"' in BRIDGE_LUA, f"bridge.lua no longer drops debug.{name}"
    guarded = {row[3] for row in SHAPE}
    for name in re.findall(r"(?:itemsTab|calcsTab|item|slot):([A-Za-z]+)\(", BRIDGE_LUA):
        assert any(name in g for g in guarded), (
            f"bridge.lua calls PoB method {name}() but the drift guard does not check it")


@STATIC
@pytest.mark.parametrize("rel,pattern,what,token", SHAPE,
                         ids=[f"{r[0]}:{r[3]}" for r in SHAPE])
def test_pinned_pob_api_shape(rel, pattern, what, token):
    texts = {n: (SRC / n).read_text(encoding="utf-8", errors="replace")
             for n in rel.split("|") if (SRC / n).is_file()}
    assert texts, (
        f"PoB API drift: {rel} is gone from the pinned checkout; bridge.lua "
        f"relies on {what}. {FIX_HINT}")
    assert row_matches(texts, rel, pattern), (
        f"PoB API drift: {rel} no longer has {what} (pattern {pattern!r}); "
        f"bridge.lua relies on it via {token!r}. {FIX_HINT}")


@STATIC
@pytest.mark.parametrize("pattern,what,token,with_runtime", LOCKDOWN,
                         ids=[r[1] for r in LOCKDOWN])
def test_pinned_pob_needs_nothing_the_lockdown_drops(pattern, what, token, with_runtime):
    files = _pob_code_files(with_runtime)
    assert files, "PoB code files missing from the pinned checkout"
    rx = re.compile(pattern)
    hits = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            code = line.split("--", 1)[0]  # a Lua comment never runs
            if rx.search(code):
                hits.append(f"{path.relative_to(SRC.parent).as_posix()}:{n}")
    assert not hits, (
        f"PoB now uses {what} ({hits[:5]}), which the bridge.lua lockdown takes "
        f"away after the start ({token!r}); check whether the headless calc path "
        f"needs it and keep or refuse it there. {FIX_HINT}")


def row_matches(texts, rel, pattern):
    """True when any file named in rel ("A.lua|B.lua") is in texts and
    matches pattern."""
    return any(re.search(pattern, texts[n], re.M)
               for n in rel.split("|") if n in texts)


# Synthetic launch sources (shape only, written for this test, not PoB code).
_UPVALUE_WRAPPER = """local mainObject
function SetMainObject(object)
  mainObject = object
end
function runCallback(name, ...)
  if mainObject[name] then
    return mainObject[name](mainObject, ...)
  end
end
dofile("Launch.lua")
"""
_GLOBAL_WRAPPER = """function runCallback(name, ...)
  if __mainObject__ and __mainObject__[name] then
    return __mainObject__[name](__mainObject__, ...)
  end
end
dofile("Launch.lua")
"""
_GLOBAL_LAUNCH = """local launch = {}
__mainObject__ = launch
"""
_NEITHER_WRAPPER = """local launcher
function runCallback(name, ...)
  return launcher[name](launcher, ...)
end
"""
LAUNCH_ROWS = [r for r in SHAPE if r[3] in ("mainObject", "__mainObject__",
                                             "runCallback", "getupvalue")]


@pytest.mark.parametrize("shape,texts", [
    ("upvalue", {"HeadlessWrapper.lua": _UPVALUE_WRAPPER, "Launch.lua": ""}),
    ("global", {"HeadlessWrapper.lua": _GLOBAL_WRAPPER, "Launch.lua": _GLOBAL_LAUNCH}),
])
def test_main_object_either_shape(shape, texts):
    """TC-BRIDGE-NEXT: the launch rows accept the local mainObject upvalue
    shape and the global __mainObject__ shape, refuse a source with
    neither, and pob_main() in bridge.lua reads both."""
    assert len(LAUNCH_ROWS) == 4
    for rel, pattern, what, _ in LAUNCH_ROWS:
        assert row_matches(texts, rel, pattern), f"{shape} shape fails the row for {what}"
    neither = {"HeadlessWrapper.lua": _NEITHER_WRAPPER, "Launch.lua": ""}
    assert not all(row_matches(neither, r[0], r[1]) for r in LAUNCH_ROWS)
    body = re.search(r"local function pob_main\(\)([\s\S]*?)\nend\n", BRIDGE_LUA)
    assert body, "bridge.lua lost pob_main()"
    body = body.group(1)
    glob = body.index('type(__mainObject__) == "table" then return __mainObject__')
    upv = body.index("getupvalue(runCallback")
    assert glob < upv, "the global __mainObject__ is read before the upvalue scan"
    assert 'name == "mainObject"' in body, "the upvalue path stays"


@STATIC
def test_pinned_checkout_is_the_pin():
    pins = bridge._load_pins()
    assert SRC.parent.name == pins["pob2"]["top_dir"], (
        f"PoB checkout {SRC.parent.name} is not the pin {pins['pob2']['top_dir']}")


@LIVE_CALC
@LIVE_REF
@pytest.mark.slow
def test_live_launch_object_and_output_keys(warm_bridge):
    ref, xml = reference()
    b = warm_bridge  # TEST-FULLSTACK-CALC-WARM: the session's warm bridge
    try:
        b.load_build(xml)
    except bridge.BridgeError as exc:
        pytest.fail(f"PoB API drift: the bridge could not drive the pinned "
                    f"checkout ({exc}); the launch object or BUILD mode moved. "
                    f"{FIX_HINT}")
    out = b.outputs()
    missing = [k for k in ("FullDPS", "TotalEHP", "Life", "EnergyShield") if k not in out]
    assert not missing, (
        f"PoB output key drift: {missing} missing from mainOutput; calcwire.DPS_KEYS "
        f"/ EHP_KEYS map PoB names to dps / ehp (decision 0024 R2). {FIX_HINT}")
    gone = sorted(set(ref["outputs"]) - set(out))
    assert not gone, f"PoB output key drift: reference keys {gone} gone. {FIX_HINT}"
    mapped = calcwire.map_outputs(out)
    assert mapped["dps"] == pytest.approx(ref["outputs"]["FullDPS"], rel=1e-3)
    assert mapped["ehp"] == pytest.approx(ref["outputs"]["TotalEHP"], rel=1e-3)


# MATH-TRADESTAT-POB (decision 0037 amendment): the trade stat id fallback
# reads src/Data/TradeSiteStats.lua as data. Its presence, line shape and
# sha256 pin (config/tc_pins.json "pob2_files") are guarded here so a pin
# move cannot silently drop or change the fallback.
TRADE_HINT = ("Re-read src/Data/TradeSiteStats.lua in the new checkout, check the "
              "id / text / type line shape still matches server/al/tradestats.py "
              "parse_pob_trade_stats, and update pob2_files in config/tc_pins.json.")


@STATIC
def test_pinned_trade_site_stats_shape_and_hash():
    from server.al import tradestats
    import hashlib
    pins = bridge._load_pins()
    path = SRC.parent / tradestats.POB_REL
    assert path.is_file(), f"PoB data drift: {tradestats.POB_REL} is gone. {TRADE_HINT}"
    raw = path.read_bytes()
    want = pins["pob2_files"][tradestats.POB_REL]["sha256"]
    assert hashlib.sha256(raw).hexdigest() == want, (
        f"PoB data drift: {tradestats.POB_REL} sha256 differs from the pin. {TRADE_HINT}")
    assert len(raw) <= tradestats.POB_MAX_BYTES
    text = raw.decode("utf-8")
    assert "trade2/data/stats" in text[:2000] and "Grinding Gear Games" in text[:2000]
    idx = tradestats.parse_pob_trade_stats(text)
    assert len(idx) > 1000, f"PoB data drift: only {len(idx)} explicit rows parsed. {TRADE_HINT}"
    assert tradestats.load_pob_index(path, pins) == idx


# ITEM-INFO-POB-TEXT (decision 0083 point 3): the item info popover's
# where-found rows read WorldAreas.lua and the Uniques slot files' Source
# lines as data. Every such file is pinned in pob2_files, the pins match,
# and the parse still finds the rows, so a pin move cannot silently drop
# or change them.
WHERE_HINT = ("Re-read src/Data/WorldAreas.lua and src/Data/Uniques/*.lua in the new "
              "checkout, check the Source line and worldAreas block shapes still match "
              "server/al/theorycraft/pobtext.py, and update pob2_files in "
              "config/tc_pins.json.")


@STATIC
def test_pinned_where_found_files_shape_and_hash():
    import hashlib
    from server.al.theorycraft import pobtext
    pins = bridge._load_pins()
    pinned = dict(pobtext.pinned_files(pins))
    assert pobtext.WORLD_AREAS in pinned, f"WorldAreas.lua has no pin. {WHERE_HINT}"
    with_source = sorted(
        f"{pobtext.UNIQUES_DIR}{p.name}" for p in (SRC / "Data" / "Uniques").glob("*.lua")
        if any(line.startswith("Source:") for line in
               p.read_text(encoding="utf-8", errors="replace").splitlines()))
    missing = [rel for rel in with_source if rel not in pinned]
    assert not missing, f"PoB data drift: Source lines in unpinned {missing}. {WHERE_HINT}"
    for rel, want in pinned.items():
        path = SRC.parent.joinpath(*rel.split("/"))
        assert path.is_file(), f"PoB data drift: {rel} is gone. {WHERE_HINT}"
        raw = path.read_bytes()
        assert len(raw) <= pobtext.MAX_BYTES
        assert hashlib.sha256(raw).hexdigest() == want, (
            f"PoB data drift: {rel} sha256 differs from the pin. {WHERE_HINT}")
    idx = pobtext.load(SRC.parent, pins)
    assert sorted(idx["files"]) == sorted(pinned)
    uniques = idx["uniques"]
    assert len(uniques) >= 40, f"PoB data drift: only {len(uniques)} uniques. {WHERE_HINT}"
    assert any(e.get("no_longer_obtainable") for e in uniques.values())
    zones = {r["zone"] for e in uniques.values() for r in e["drops"] if "zone" in r}
    known = [z for z in zones if pobtext.key(z) in idx["areas"]]
    assert len(idx["areas"]) > 200 and len(known) >= 3, (
        f"PoB data drift: WorldAreas names {len(known)} Source zones. {WHERE_HINT}")


# DATA-AUGMENT-POB-TEXT (decision 0091): augment effects, values and slot
# rules read src/Data/ModRunes.lua as data. Its pob2_files entry is checked
# against the pin's commit always, and against the checkout when present.
AUGMENT_HINT = ("Re-read src/Data/ModRunes.lua in the new checkout, check its augment "
                "and slot block shapes still match server/al/theorycraft/pobtext.py "
                "parse_augments, and update pob2_files in config/tc_pins.json.")


def augment_pin_problem(pins):
    """None when pins carry a well-formed ModRunes.lua pob2_files entry on
    the pinned commit, else what is wrong."""
    import re
    from server.al.theorycraft import pobtext
    row = ((pins or {}).get("pob2_files") or {}).get(pobtext.AUGMENTS)
    if not isinstance(row, dict):
        return f"{pobtext.AUGMENTS} has no pob2_files entry"
    if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256"))):
        return f"{pobtext.AUGMENTS} sha256 is not a sha256"
    size = row.get("size")
    if not isinstance(size, int) or not 0 < size <= pobtext.AUGMENTS_MAX_BYTES:
        return f"{pobtext.AUGMENTS} size {size!r} is outside the cap"
    if row.get("commit") != ((pins.get("pob2") or {}).get("commit")):
        return f"{pobtext.AUGMENTS} entry is not on the pinned commit"
    return None


def test_tracked_pins_carry_the_augment_entry():
    problem = augment_pin_problem(bridge._load_pins())
    assert problem is None, f"PoB data drift: {problem}. {AUGMENT_HINT}"


def test_augment_pin_problem_names_each_failure():
    import copy
    from server.al.theorycraft import pobtext
    good = bridge._load_pins()
    assert augment_pin_problem(good) is None
    cases = [
        (lambda p: p["pob2_files"].pop(pobtext.AUGMENTS), "no pob2_files entry"),
        (lambda p: p["pob2_files"][pobtext.AUGMENTS].update(sha256="x"), "not a sha256"),
        (lambda p: p["pob2_files"][pobtext.AUGMENTS].update(size=2 * 1024 * 1024),
         "outside the cap"),
        (lambda p: p["pob2_files"][pobtext.AUGMENTS].update(commit="0" * 40),
         "not on the pinned commit"),
    ]
    for change, words in cases:
        pins = copy.deepcopy(good)
        change(pins)
        assert words in augment_pin_problem(pins)
    assert "no pob2_files entry" in augment_pin_problem({})


@STATIC
def test_pinned_mod_runes_shape_and_hash():
    import hashlib
    from server.al.theorycraft import pobtext
    pins = bridge._load_pins()
    path = SRC.parent.joinpath(*pobtext.AUGMENTS.split("/"))
    assert path.is_file(), f"PoB data drift: {pobtext.AUGMENTS} is gone. {AUGMENT_HINT}"
    raw = path.read_bytes()
    row = pins["pob2_files"][pobtext.AUGMENTS]
    assert len(raw) == row["size"] and len(raw) <= pobtext.AUGMENTS_MAX_BYTES
    assert hashlib.sha256(raw).hexdigest() == row["sha256"], (
        f"PoB data drift: {pobtext.AUGMENTS} sha256 differs from the pin. {AUGMENT_HINT}")
    idx = pobtext.load_augments(SRC.parent, pins)
    assert len(idx) == 287, f"PoB data drift: {len(idx)} augments parsed. {AUGMENT_HINT}"
