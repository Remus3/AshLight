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

from tc_live_util import LIVE_REF, reference

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
SHAPE = [
    ("HeadlessWrapper.lua", r"^\s*(local\s+)?mainObject\b", "the launch object "
     "variable `mainObject` (local or global)", "mainObject"),
    ("HeadlessWrapper.lua", r"function\s+SetMainObject\s*\(", "SetMainObject()",
     "mainObject"),
    ("HeadlessWrapper.lua", r"function\s+runCallback\s*\(", "runCallback()",
     "runCallback"),
    ("HeadlessWrapper.lua", r"runCallback[\s\S]*mainObject\[name\]",
     "runCallback() calling mainObject[name] (bridge.lua reads mainObject "
     "from its upvalue)", "getupvalue"),
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
]


def test_guard_covers_what_bridge_lua_uses():
    """Every guarded name is still used by bridge.lua (no stale rows), and
    the PoB names bridge.lua calls are all guarded."""
    for _, _, what, token in SHAPE:
        assert token in BRIDGE_LUA, f"guard row for {what}: bridge.lua no longer uses {token!r}"
    guarded = {row[3] for row in SHAPE}
    for name in re.findall(r"(?:itemsTab|calcsTab|item|slot):([A-Za-z]+)\(", BRIDGE_LUA):
        assert any(name in g for g in guarded), (
            f"bridge.lua calls PoB method {name}() but the drift guard does not check it")


@STATIC
@pytest.mark.parametrize("rel,pattern,what,token", SHAPE,
                         ids=[f"{r[0]}:{r[3]}" for r in SHAPE])
def test_pinned_pob_api_shape(rel, pattern, what, token):
    path = SRC / rel
    assert path.is_file(), (
        f"PoB API drift: {rel} is gone from the pinned checkout; bridge.lua "
        f"relies on {what}. {FIX_HINT}")
    text = path.read_text(encoding="utf-8", errors="replace")
    assert re.search(pattern, text, re.M), (
        f"PoB API drift: {rel} no longer has {what} (pattern {pattern!r}); "
        f"bridge.lua relies on it via {token!r}. {FIX_HINT}")


@STATIC
def test_pinned_checkout_is_the_pin():
    pins = bridge._load_pins()
    assert SRC.parent.name == pins["pob2"]["top_dir"], (
        f"PoB checkout {SRC.parent.name} is not the pin {pins['pob2']['top_dir']}")


@LIVE_REF
@pytest.mark.slow
def test_live_launch_object_and_output_keys():
    ref, xml = reference()
    b = bridge.Bridge.from_component(start_timeout=180.0, timeout=120.0)
    try:
        try:
            b.load_build(xml)
        except bridge.BridgeError as exc:
            pytest.fail(f"PoB API drift: the bridge could not drive the pinned "
                        f"checkout ({exc}); the launch object or BUILD mode moved. "
                        f"{FIX_HINT}")
        out = b.outputs()
    finally:
        b.close()
    missing = [k for k in ("FullDPS", "TotalEHP", "Life", "EnergyShield") if k not in out]
    assert not missing, (
        f"PoB output key drift: {missing} missing from mainOutput; calcwire.DPS_KEYS "
        f"/ EHP_KEYS map PoB names to dps / ehp (decision 0024 R2). {FIX_HINT}")
    gone = sorted(set(ref["outputs"]) - set(out))
    assert not gone, f"PoB output key drift: reference keys {gone} gone. {FIX_HINT}"
    mapped = calcwire.map_outputs(out)
    assert mapped["dps"] == pytest.approx(ref["outputs"]["FullDPS"], rel=1e-3)
    assert mapped["ehp"] == pytest.approx(ref["outputs"]["TotalEHP"], rel=1e-3)
