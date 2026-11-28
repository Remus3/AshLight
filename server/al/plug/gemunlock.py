"""TC-GEM-UNLOCK (research 0064 G3, decision 0095): feeds the gem unlock
card through the plug seam (decision 0056).

On every build load (the build store's listener) the loaded build's enabled
gem names go into the state (gemunlock.build_gems). A core tick keeps the
state's gems snapshot table current: the cached repoe-fork gems.json beside
the base item list the core already reads (DATA-GEMS-SNAP, decision 0009),
through the one gem helper (theorycraft/gemadvice.index: re-read only on a
stat change, last good copy kept) and only while a build is loaded, so a
player without a build never pays for the parse. A missing or bad file
reads as no table: no card.

Reads only the local cache and the player's own build; no fetch, nothing
sent anywhere.
"""

from .. import gemunlock
from ..theorycraft import gemadvice

ORDER = 100
TICK = "gem_unlock"


class Feeder:
    """feed the state the build gems (on load) and the snapshot table (tick)."""

    def __init__(self, core):
        self.core = core
        self.path = gemadvice.gems_file(core)

    def on_build(self, build):
        self.core.state.set_gem_unlock(gems=gemunlock.build_gems(build))

    def tick(self):
        if getattr(self.core.builds, "build", None) is None:
            return
        self.core.state.set_gem_unlock(index=gemadvice.index(self.path))


def attach(core):
    feeder = Feeder(core)
    core.gem_unlock = feeder
    core.builds.add_listener(feeder.on_build)
    feeder.on_build(core.builds.build)
    core.add_tick(TICK, feeder.tick)
