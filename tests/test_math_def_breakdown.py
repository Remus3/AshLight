"""MATH-DEF-BREAKDOWN (theorycraft/health.py): PoB's remaining warnFunc
conditions and the defence / sustain list.

Stat names are the ones the pinned PoB-PoE2 checkout writes (PlayerStat
via BuildDisplayStats.lua, CalcDefence / CalcPerform outputs via the
calc); values are invented. Nothing is recomputed (decision 0004): every
check is a PoB value against PoB's own warn condition.
"""

from pathlib import Path

import pytest

from server.al import paths
from server.al.theorycraft import health, model


def _build(**stats):
    rows = "".join(f'<PlayerStat stat="{k}" value="{v}"/>\n' for k, v in stats.items())
    return model.parse('<PathOfBuilding2><Build level="80" className="Ranger">\n' + rows
                       + '</Build></PathOfBuilding2>')


def _ids(doc):
    return [w["id"] for w in doc["warnings"]]


def test_unreserved_life_zero_warns_high():
    doc = health.health(_build(Life=1000, LifeUnreserved=0))
    w = next(w for w in doc["warnings"] if w["id"] == "life-reserved")
    assert w["severity"] == "high" and w["value"] == 0 and "Life" in w["text"]


def test_warning_texts_exact():
    b = _build(Life=3000, LifeUnreserved=0, ManaUnreserved=-12, MainHandAccuracy=2617,
               TotalDotDPS=health.DOT_DPS_CAP)
    texts = {w["id"]: w["text"] for w in health.health(b, {"PreciseTechnique": True})["warnings"]}
    assert texts["life-reserved"] == ("Your unreserved Life is 0: your skills reserve all "
                                      "of your Life.")
    assert texts["mana-reserved"] == ("Your unreserved Mana is -12: your skills reserve "
                                      "more Mana than you have.")
    assert texts["precise-MainHandAccuracy"] == (
        "Your main hand Accuracy (2,617) is below your Life (3,000), and Precise "
        "Technique needs at least as much Accuracy as Life.")
    assert texts["dot-cap-TotalDotDPS"] == (
        "Your damage over time (35,791,394 per second) is at the game's limit, so more "
        "of it adds nothing.")


def test_unreserved_life_positive_no_warning():
    assert "life-reserved" not in _ids(health.health(_build(LifeUnreserved=1)))


def test_unreserved_mana_negative_warns_zero_does_not():
    assert "mana-reserved" in _ids(health.health(_build(ManaUnreserved=-12)))
    assert "mana-reserved" not in _ids(health.health(_build(ManaUnreserved=0)))


def test_precise_technique_needs_calc_flag():
    b = _build(Life=3000, MainHandAccuracy=2617, OffHandAccuracy=3100)
    assert not any(i.startswith("precise") for i in _ids(health.health(b)))
    doc = health.health(b, {"PreciseTechnique": True})
    assert [i for i in _ids(doc) if i.startswith("precise")] == ["precise-MainHandAccuracy"]
    w = next(w for w in doc["warnings"] if w["id"] == "precise-MainHandAccuracy")
    assert w["value"] == 2617 and w["limit"] == 3000 and "main hand" in w["text"]
    assert not any(i.startswith("precise")
                   for i in _ids(health.health(b, {"PreciseTechnique": False})))


def test_dot_cap_uses_pob_constant():
    at = health.health(_build(TotalDotDPS=health.DOT_DPS_CAP, IgniteDPS=10))
    assert _ids(at) == ["dot-cap-TotalDotDPS"]
    below = health.health(_build(TotalDotDPS=health.DOT_DPS_CAP - 1))
    assert not any(i.startswith("dot-cap") for i in _ids(below))


def test_high_warnings_sort_first():
    doc = health.health(_build(FireResist=50, ManaUnreserved=-1, TotalDotDPS=4e7))
    assert doc["warnings"][0]["id"] == "mana-reserved"
    sev = [w["severity"] for w in doc["warnings"]]
    assert sev == sorted(sev, key=health.SEVERITY_RANK.get)


def test_missing_stats_show_nothing():
    doc = health.health(_build(Life=1000))
    assert not any(i in ("life-reserved", "mana-reserved") or i.startswith(("dot", "precise"))
                   for i in _ids(doc))
    assert doc["defence"] == []


def test_sustain_rows_show_with_calc_off():
    doc = health.health(_build(ManaPerSecondCost=85.5036, ManaRegenRecovery=47.8,
                               NetManaRegen=-37.7))
    assert [r["id"] for r in doc["defence"]] == ["ManaPerSecondCost", "ManaRegenRecovery",
                                                 "NetManaRegen"]
    assert doc["defence"][0]["value"] == 85.5036  # as PoB exports it
    assert doc["calc_on"] is False


def test_calc_only_rows_hidden_with_calc_off():
    doc = health.health(_build(StunThreshold=900, IgniteAvoidChance=30))
    assert doc["defence"] == []


def test_calc_rows_show_with_calc_on_in_list_order():
    calc = {"PoisonAvoidChance": 20, "IgniteAvoidChance": 100, "StunThreshold": 1234.0,
            "CharmEffect": 25, "LifeFlaskChargeGen": float("nan"), "NetManaRegen": 3.5}
    doc = health.health(_build(NetManaRegen=-1), calc)
    rows = {r["id"]: r for r in doc["defence"]}
    assert list(rows) == ["IgniteAvoidChance", "PoisonAvoidChance", "StunThreshold",
                          "CharmEffect", "NetManaRegen"]
    assert rows["NetManaRegen"]["value"] == 3.5  # the calc wins over the saved stat
    assert rows["CharmEffect"]["unit"] == "%" and rows["IgniteAvoidChance"]["unit"] == "%"
    assert doc["calc_on"] is True


def test_calc_outputs_alone_without_playerstat():
    b = model.parse('<PathOfBuilding2><Build level="80"></Build></PathOfBuilding2>')
    doc = health.health(b, {"StunThreshold": 500})
    assert [r["id"] for r in doc["defence"]] == ["StunThreshold"]
    assert health.health(b)["message"] == health.NO_STATS


def test_calc_keys_cover_every_calc_read():
    keys = set(health.CALC_KEYS)
    assert {d[0] for d in health.DEFENCE} <= keys
    assert {"PreciseTechnique", "LifeUnreserved", "ManaUnreserved", "Life"} <= keys


# ---- live leg: the pinned PoB checkout and the reference build ----------

def _pob_src():
    import json
    pins = Path(__file__).resolve().parents[1] / "config" / "tc_pins.json"
    top = json.loads(pins.read_text(encoding="ascii"))["pob2"]["top_dir"]
    return paths.all_runtime_paths()["pob2_cache"] / top / "src"


def test_live_dot_cap_matches_pinned_checkout():
    data = _pob_src() / "Modules" / "Data.lua"
    if not data.is_file():
        pytest.skip("pinned PoB checkout absent (setup.ps1 -TcCalc)")
    text = data.read_text(encoding="utf-8", errors="replace")
    assert f"DotDpsCap = {health.DOT_DPS_CAP}," in text


def test_live_defence_names_in_pinned_checkout():
    mods = _pob_src() / "Modules"
    if not mods.is_dir():
        pytest.skip("pinned PoB checkout absent (setup.ps1 -TcCalc)")
    text = "".join((mods / f).read_text(encoding="utf-8", errors="replace")
                   for f in ("CalcDefence.lua", "CalcPerform.lua", "BuildDisplayStats.lua",
                             "Data.lua", "CalcOffence.lua"))
    for name in ("StunThreshold", "StunAvoidChance", "FlaskChargeGen", "LifeFlaskChargeGen",
                 "ManaFlaskChargeGen", "CharmEffect", "ManaPerSecondCost",
                 "ManaRegenRecovery", "NetManaRegen", "LifeUnreserved", "ManaUnreserved",
                 "PreciseTechnique", '"Ignite", "Chill", "Freeze", "Shock"',
                 '"Bleed", "Poison"', 'ailment.."AvoidChance"'):
        assert name in text, name


def test_live_reference_build_breakdown():
    from tc_live_util import reference
    ref = reference()
    if ref is None:
        pytest.skip("reference build absent (sidecar Cache\\tc_bridge)")
    doc = health.health(model.parse(ref[1]))
    ids = _ids(doc)
    assert "life-reserved" not in ids and "mana-reserved" not in ids
    assert not any(i.startswith(("dot-cap", "precise")) for i in ids)
    rows = {r["id"]: r["value"] for r in doc["defence"]}
    assert rows["ManaPerSecondCost"] == pytest.approx(85.5036)
    assert rows["ManaRegenRecovery"] == pytest.approx(47.8)
    assert "StunThreshold" not in rows  # calc off: calc-only rows hidden
