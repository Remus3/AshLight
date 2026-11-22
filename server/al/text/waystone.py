"""Waystone check text (UTIL-WAYSTONE, decision 0030; UTIL-WAYSTONE-REWARD).

Moved byte for byte out of server/al/state.py (TEST-STATE-TEXT-2);
state.py re-exports every name, so state.<name> is the same object.
Pure functions and constants; stdlib only.
"""

from .. import num as num_mod
from .common import _dict, _dicts, _short_list, _signed, _text

# CARD-LINE-LIMIT-COPY2: the overlay lines fit 26 characters while
# common.CARD_LINE stays 34; CARD-LINE-LIMIT-FLIP lowers CARD_LINE to it.
LINE_FIT = 26


WAYSTONE_LISTED = 3  # design 0001 rule 1: the sentence names at most 3 mods


def waystone_rewards_text(ws):
    """UTIL-WAYSTONE-REWARD: `rewards` (the dashboard sentence) and
    `reward_line` (the overlay card's item line, "" when there is nothing to
    show). Exact tests in tests/test_waystone_reward.py."""
    ws = _dict(ws)
    if ws.get("unidentified"):
        return {"rewards": "Rewards: identify it to see them.", "reward_line": ""}
    rows = [r for r in _dicts(ws.get("rewards"))
            if _reward_pct(r.get("pct")) is not None and _text(r.get("label"), "")]
    if not rows:
        return {"rewards": "Rewards: none found in the item text.", "reward_line": ""}
    full = ", ".join(f"{_signed(r['pct'])}% {_text(r.get('label'), '')}" for r in rows)
    shorts = [f"{_signed(r['pct'])}% {_text(r.get('short'), '') or _text(r.get('label'), '')}"
              for r in rows]
    return {"rewards": f"Rewards: {full}.", "reward_line": _short_list(shorts, LINE_FIT)}


def _reward_pct(v):
    v = num_mod.finite(v)
    return v if v is not None and abs(v) <= 10000 and v != 0 else None


def waystone_text(ws):
    """UTIL-WAYSTONE (decision 0030): `head`, `line` and `sentence` for a
    waystone check, plus the UTIL-WAYSTONE-REWARD `rewards` / `reward_line`.
    Exact tests in tests/test_waystone.py."""
    out = _waystone_risk_text(ws)
    out.update(waystone_rewards_text(ws))
    return out


def _waystone_risk_text(ws):
    ws = _dict(ws)
    tier = ws.get("tier")
    what = (f"Tier {tier} waystone" if isinstance(tier, int) and not isinstance(tier, bool)
            else "Waystone")
    if ws.get("unidentified"):
        return {"head": "Waystone unidentified", "line": "Identify it to check mods",
                "sentence": f"{what}. Identify it to see its mods, then press the hotkey "
                            "again."}
    risky = _dicts(ws.get("risky"))
    labels = [_text(r.get("label"), "") for r in risky if _text(r.get("label"), "")]
    shorts = [_text(r.get("short"), "") for r in risky if _text(r.get("short"), "")]
    loaded = bool(ws.get("build_loaded"))
    if not labels:
        if loaded:
            return {"head": "No risky mods found", "line": what,
                    "sentence": f"{what}. None of its mods look risky for this build."}
        return {"head": "No risky mods found", "line": "No build loaded",
                "sentence": f"{what}. None of its mods look risky. Load a build to check "
                            "them against your resistances too."}
    head = "Risky for this build" if loaded else "Risky waystone"
    sentence = (f"{what}. Risky for this build: " if loaded
                else f"{what}. Risky mods (no build loaded, so resistances are unknown): ")
    listed = ", ".join(labels[:WAYSTONE_LISTED])
    if len(labels) > WAYSTONE_LISTED:
        listed += f", and {len(labels) - WAYSTONE_LISTED} more"
    return {"head": head, "line": _short_list(shorts, LINE_FIT), "sentence": sentence + listed + "."}
