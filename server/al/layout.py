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
import os
from pathlib import Path

CONFIG_KEY = "overlay"
CORNERS = ("top-left", "top-center", "top-right",
           "bottom-left", "bottom-center", "bottom-right")
# Floors from design 0001 (DS-OPACITY, DS-SCALE): window opacity fades text
# and plate together, so below 0.9 overlay text drops under 4.5:1 over a
# white scene (5.2); below 0.95 the 13px secondary text renders under 12px.
SCALE_MIN, SCALE_MAX = 0.95, 2.0
OPACITY_MIN, OPACITY_MAX = 0.9, 1.0
MARGIN_MAX = 400
MAX_DISPLAYS = 16

DEFAULT = {"display": "primary", "corner": "top-right", "scale": 1.0,
           "opacity": 0.9, "margin": 16}


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


def normalize(layout, strict=True):
    """A complete, valid layout dict. strict=True raises LayoutError on a bad
    field (API input); strict=False clamps an out-of-range number to its
    bound and drops any other bad field to the default (a hand-edited or
    older config file must never stop the app)."""
    if not isinstance(layout, dict):
        if strict:
            raise LayoutError("layout must be an object")
        layout = {}
    out = dict(DEFAULT)
    checks = {
        "corner": lambda v: v if v in CORNERS else _bad("corner must be one of "
                                                        + ", ".join(CORNERS)),
        "display": _display,
        "scale": lambda v: _number(v, "scale", SCALE_MIN, SCALE_MAX, not strict),
        "opacity": lambda v: _number(v, "opacity", OPACITY_MIN, OPACITY_MAX,
                                     not strict),
        "margin": lambda v: int(_number(v, "margin", 0, MARGIN_MAX, not strict)),
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
    return out


def _bad(msg):
    raise LayoutError(msg)


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
    try:
        cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    return from_config(cfg if isinstance(cfg, dict) else {})


def save(config_path, layout):
    """Write the layout into local.json under "overlay", keeping every other
    key. ASCII + LF, atomic replace. Returns the normalized layout."""
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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="ascii", newline="\n") as fh:
        fh.write(json.dumps(cfg, indent=2, ensure_ascii=True) + "\n")
    os.replace(tmp, path)
    return layout


def read_displays(runtime_dir):
    """Monitors the overlay last reported ([] when it has not run yet)."""
    try:
        doc = json.loads((Path(runtime_dir) / "displays.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
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
