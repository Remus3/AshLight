"""Overlay layout: where the click-through HUD sits (ROADMAP OVL-POS).

The layout lives in config/local.json under the key "overlay" (per-host,
gitignored), so it survives a restart. The dashboard edits it through
POST /api/overlay-layout; the overlay's main process watches the file and
moves its own window. Placement math (DPI, multi-monitor) is in
app/shared/layout.js; this module only validates and persists the choice.

The overlay main process lists the monitors it sees in ops/runtime/
displays.json so the dashboard can offer them; the core only reads that file.
"""

import json
import math
from pathlib import Path

from . import jsonfile

CONFIG_KEY = "overlay"
CORNERS = ("top-left", "top-center", "top-right",
           "bottom-left", "bottom-center", "bottom-right")
# Floors from design 0001 (DS-OPACITY, DS-SCALE): below 0.95 the 13px
# secondary text renders under 12px. OVL-TD05-PLATE (TD-05 part 2): the
# "opacity" key is the HUD plate alpha only (app/shared/layout.js sets
# --al-plate-a); text stays opaque, so the floor is the plate's own 0.80,
# where every overlay text colour keeps 4.5:1 over a white scene.
SCALE_MIN, SCALE_MAX = 0.95, 2.0
OPACITY_MIN, OPACITY_MAX = 0.8, 1.0
# Schema marker. A layout without "v": 2 was saved when "opacity" faded the
# whole page within 0.9 to 1.0; that value maps linearly onto 0.86 to 1.0
# once (migrate_opacity), at the next read. Any save writes "v": 2.
SCHEMA = 2
V1_OPACITY_MIN, V1_OPACITY_MAX = 0.9, 1.0
MARGIN_MAX = 400
MAX_DISPLAYS = 16

# OVL-OVERLAY-KEYS (plan 03 section 5.4): the overlay parts the player can
# switch off, all on by default. A failure word (offline, no Client.txt,
# not reading) is not a part: it always shows and can never be switched off.
PARTS = ("zone", "timer", "level", "deaths", "status", "trade", "item",
         "moment", "hint")
# Zone guide: shown on zone entry (default), always, or never.
ZONE_GUIDE = ("entry", "always", "never")
# OVL-TD18-CARD-TIME (TD-18): how long the press card (item check, price,
# merged) stays on the overlay, in seconds. 20 is the default; a slow reader
# keeps it longer. The card still leaves by itself. A layout carries
# "card_s" only when it is not the default (absent means 20), so a layout,
# config file or settings export saved before stays the same document.
CARD_S = (20, 60, 200)

DEFAULT = {"display": "primary", "corner": "top-right", "scale": 1.0,
           "opacity": 0.86, "margin": 16,
           "parts": {name: True for name in PARTS},
           # hide the zone line in town and hideout
           "quiet_town": False,
           "zone_guide": "entry",
           "v": SCHEMA}


class LayoutError(ValueError):
    pass


def _number(value, name, lo, hi, clamp=False):
    """A rounded number in [lo, hi]. clamp=True (lenient load) pulls an
    out-of-range number to the nearest bound, so a layout saved before a
    floor was raised clamps itself; strict input raises instead."""
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or value != value):  # wrong type or NaN
        raise LayoutError(f"{name} must be a number")
    if not lo <= value <= hi:
        if not clamp:
            raise LayoutError(f"{name} must be between {lo} and {hi}")
        value = min(hi, max(lo, value))
    return round(float(value), 2)


def migrate_opacity(old):
    """A schema 1 page opacity (0.9 to 1.0, already range-checked) as the
    schema 2 plate alpha: 0.9 -> 0.86, 1.0 -> 1.0, linear between, in whole
    hundredths. floor(x + 0.5) is JS Math.round, so app/shared/layout.js
    gets the same number from the same double."""
    return math.floor(140 * old - 40 + 0.5) / 100


def _opacity(value, current, strict):
    if current:
        return _number(value, "opacity", OPACITY_MIN, OPACITY_MAX, not strict)
    # type and range checked as before; the mapping reads the unrounded
    # value, as app/shared/layout.js does
    _number(value, "opacity", V1_OPACITY_MIN, V1_OPACITY_MAX, not strict)
    old = min(V1_OPACITY_MAX, max(V1_OPACITY_MIN, float(value)))
    return _number(migrate_opacity(old), "opacity", OPACITY_MIN, OPACITY_MAX,
                   True)


def _schema(value):
    if isinstance(value, bool) or value != SCHEMA:
        raise LayoutError(f"v must be {SCHEMA}")
    return SCHEMA


def normalize(layout, strict=True):
    """A complete, valid layout dict. strict=True raises LayoutError on a bad
    field (API input); strict=False clamps an out-of-range number to its
    bound and drops any other bad field to the default (a hand-edited or
    older config file must never stop the app). A layout without "v": 2
    (both modes: an old config file or an old settings export) reads its
    opacity on the schema 1 range and migrates it; the result always
    carries "v": 2."""
    if not isinstance(layout, dict):
        if strict:
            raise LayoutError("layout must be an object")
        layout = {}
    raw_v = layout.get("v")
    current = not isinstance(raw_v, bool) and raw_v == SCHEMA
    out = dict(DEFAULT)
    out["parts"] = dict(DEFAULT["parts"])
    checks = {
        "corner": lambda v: v if v in CORNERS else _bad("corner must be one of "
                                                        + ", ".join(CORNERS)),
        "display": _display,
        "scale": lambda v: _number(v, "scale", SCALE_MIN, SCALE_MAX, not strict),
        "opacity": lambda v: _opacity(v, current, strict),
        "margin": lambda v: int(_number(v, "margin", 0, MARGIN_MAX, not strict)),
        "parts": lambda v: _parts(v, strict),
        "quiet_town": lambda v: _flag(v, "quiet_town"),
        "zone_guide": lambda v: v if v in ZONE_GUIDE else _bad(
            "zone_guide must be one of " + ", ".join(ZONE_GUIDE)),
        "card_s": _card_s,
        "v": _schema,
    }
    for key, check in checks.items():
        if key not in layout:
            continue
        try:
            out[key] = check(layout[key])
        except LayoutError:
            if strict:
                raise
    if strict:
        extra = sorted(set(layout) - set(checks))
        if extra:
            raise LayoutError("unknown field: " + ", ".join(extra))
    if out.get("card_s") == CARD_S[0]:
        del out["card_s"]  # the default is never stored (absent means 20)
    return out


def _bad(msg):
    raise LayoutError(msg)


def _card_s(value):
    """One of CARD_S as an int (never true / false). 60.0 reads as 60, as
    JSON.parse in app/shared/layout.js reads it, so both sides agree."""
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or value not in CARD_S):
        raise LayoutError("card_s must be one of " + ", ".join(map(str, CARD_S)))
    return int(value)


def card_seconds(layout):
    """The press card time of a layout dict (any shape): its card_s when
    valid, else the default. Never raises."""
    value = layout.get("card_s") if isinstance(layout, dict) else None
    try:
        return _card_s(value)
    except LayoutError:
        return CARD_S[0]


def _flag(value, name):
    if not isinstance(value, bool):
        raise LayoutError(f"{name} must be true or false")
    return value


def _parts(value, strict):
    """The parts switches, every part filled in. A part missing from value
    keeps its default (on). Strict refuses an unknown part name or a value
    that is not true / false; lenient drops either and keeps the default."""
    if not isinstance(value, dict):
        raise LayoutError("parts must be an object")
    out = dict(DEFAULT["parts"])
    for name, on in value.items():
        if name not in PARTS:
            if strict:
                raise LayoutError("unknown overlay part: " + str(name)[:40]
                                  + " (parts are " + ", ".join(PARTS) + ")")
            continue
        if not isinstance(on, bool):
            if strict:
                raise LayoutError(f"parts.{name} must be true or false")
            continue
        out[name] = on
    return out


def _display(value):
    """"primary" or a 0-based monitor index (displays sorted left to right)."""
    if value == "primary":
        return value
    if isinstance(value, bool) or not isinstance(value, int) \
            or not 0 <= value < MAX_DISPLAYS:
        raise LayoutError(f'display must be "primary" or 0..{MAX_DISPLAYS - 1}')
    return value


def from_config(cfg):
    """The layout stored in a loaded local.json dict (defaults filled in)."""
    return normalize((cfg or {}).get(CONFIG_KEY) or {}, strict=False)


def load(config_path):
    """The stored layout; a half-written local.json is restored from the
    .bak layout.save keeps (F-014)."""
    return from_config(jsonfile.read_json(config_path, kind=dict, default={},
                                          backup=True))


def save(config_path, layout):
    """Write the layout into local.json under "overlay", keeping every other
    key. ASCII + LF, atomic replace, one .bak of the written copy (F-014).
    Returns the normalized layout."""
    layout = normalize(layout)
    path = Path(config_path)
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            cfg = {}
    except FileNotFoundError:
        cfg = {}
    except (OSError, ValueError) as e:
        # Never overwrite a config file the user broke by hand.
        raise LayoutError(f"config/local.json is unreadable: {e}") from e
    cfg[CONFIG_KEY] = layout
    jsonfile.write_json(path, cfg, indent=2, backup=True)
    return layout


def read_displays(runtime_dir):
    """Monitors the overlay last reported ([] when it has not run yet)."""
    doc = jsonfile.read_json(Path(runtime_dir) / "displays.json")
    rows = doc.get("displays") if isinstance(doc, dict) else None
    out = []
    for d in (rows or [])[:MAX_DISPLAYS]:
        if not isinstance(d, dict) or not isinstance(d.get("index"), int):
            continue
        out.append({"index": d["index"], "primary": bool(d.get("primary")),
                    "label": str(d.get("label") or "")[:80],
                    "width": d.get("width"), "height": d.get("height"),
                    "scale_factor": d.get("scale_factor")})
    return out
