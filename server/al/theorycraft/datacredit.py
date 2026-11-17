"""Game-data snapshot attribution (ROADMAP TC-SNAP-UI, decision 0009).

The one home of the snapshot ATTRIBUTION text and the snapshot cache
location. No network, no fetch: the core imports this module (never
snapshot.py, see tests/test_tc_snap.py) to tell whether snapshot data exists
and to publish the attribution in GET /api/version as "data_credit".
"""

import json

from .. import DISCLAIMER, paths

# The copyright sentence every game-data credit carries (one source).
COPYRIGHT = "Game data (c) Grinding Gear Games."
# Short sentences (design review TC-SNAP-UI-1, design 0001 P1 / P2).
ATTRIBUTION = (COPYRIGHT + " Item, mod and stat data comes from "
               "the RePoE fork community export (repoe-fork). Trade search stat ids "
               "are Grinding Gear Games' trade site data, passed on by repoe-fork. Ids it "
               "lacks come from Path of Building Community (PoE2, MIT license) when its "
               "optional calc files are installed. "
               "Passive tree data comes "
               "from Grinding Gear Games' public skill tree export. AshLight downloaded "
               "all of it to this computer when it was built. This product isn't affiliated "
               "with or endorsed by Grinding Gear Games in any way.")
# The UI shows the non-affiliation line on its own already, so the credit line
# is the attribution without that sentence (never shown twice).
CREDIT = (ATTRIBUTION[:-len(DISCLAIMER)].rstrip() if ATTRIBUTION.endswith(DISCLAIMER)
          else ATTRIBUTION)
# The credit line under the HUD-ACT zone level table (server/al/acts.py,
# decision 0020); the zone levels come from the same snapshot cache.
ZONE_LEVELS_CREDIT = ("Zone levels: RePoE fork export, downloaded when AshLight "
                      "was built. " + COPYRIGHT)
MANIFEST = "manifest.json"


def cache_dir(environ=None):
    return paths.sidecar_dir("Cache", environ) / "gamedata"


def has_snapshot(directory=None, environ=None):
    """True when the snapshot cache holds data: a readable manifest listing at
    least one source whose <name>.json file is on disk."""
    directory = cache_dir(environ) if directory is None else directory
    try:
        doc = json.loads((directory / MANIFEST).read_text(encoding="ascii"))
    except (OSError, ValueError):
        return False
    files = doc.get("files") if isinstance(doc, dict) else None
    if not isinstance(files, dict):
        return False
    return any(isinstance(name, str) and (directory / f"{name}.json").is_file()
               for name in files)


def credit_doc(directory=None, environ=None):
    """The /api/version "data_credit" value: None without snapshot data."""
    if not has_snapshot(directory, environ):
        return None
    return {"attribution": ATTRIBUTION, "credit": CREDIT}
