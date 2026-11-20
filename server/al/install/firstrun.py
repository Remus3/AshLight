"""The first-run config of an install (REL-INSTALL-SHELL, finding F-050,
DEP-09; docs/plan/05-deployment.md Design point 15 and "Installed-mode
layout").

- first_run_config(): the document, built from PLAYER_DEFAULTS, a fixed
  table of player keys in code. The tracked config/local.example.json
  carries dev keys (loop, ...) and is neither shipped nor read here.
- write_first_run(home): writes <home>/data/local.json once. An existing
  local.json (file, folder or link, or a .bak of one) is never overwritten
  or changed: the result is "kept". A new file is written to a unique temp
  file, fsynced, and linked into place only when the name is still free,
  then read back.

What the file never holds: web data on (decision 0013: off until the
player's own click), Client.txt consent (consent.json is the floor's
opt-in, given on the first window with its visible indicator; this
module never writes it), a contact, a log path, a port, and any dev-only
key (DEV_KEYS). Every key is one the settings allow-list
(server/al/settingsio.py ALLOWED) names. Standard library only; no game
folder is read or written.
"""

import json
import os

from .. import jsonfile
from . import home as homemod

# key -> first-run value: the ONE table (player keys only)
PLAYER_DEFAULTS = {
    "web_data": False,  # decision 0013: the player's own switch
    "tc_calc": False,   # decision 0018: the optional calc stays off
    "character": "",
    "league": "",
}
# never written into a player's local.json (plan 05 "What moves out")
DEV_KEYS = ("loop", "loop_push", "hot_reload", "tc_drift_live_unattended")
# never written by an install: the floor's opt-ins and per-host values
NEVER_KEYS = ("contact", "client_log", "consent", "port", "token", "poesessid")


class FirstRunError(Exception):
    """The first-run config could not be written or did not read back."""


def first_run_config():
    """A fresh copy of the first-run document."""
    return dict(PLAYER_DEFAULTS)


def config_path(home):
    """<home>/data/local.json."""
    return homemod.layout(home)["local_config"]


def _present(path):
    """True when anything sits at path (a broken link included)."""
    return os.path.lexists(path)


def write_first_run(home):
    """Write <home>/data/local.json when none exists; returns "written" or
    "kept" (an existing one, never touched). <home>/data must already be
    laid out (home.make_layout gives it the private ACL first)."""
    path = config_path(home)
    if _present(path) or _present(jsonfile.bak_path(path)):
        return "kept"
    if not os.path.isdir(path.parent):
        raise FirstRunError("the data folder is not laid out")
    doc = first_run_config()
    data = jsonfile.dumps(doc).encode("ascii")
    tmp = jsonfile.tmp_path(path, "firstrun.%d.%s" % (os.getpid(), os.urandom(6).hex()))
    try:
        with open(tmp, "xb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.link(tmp, path)  # fails when the name is taken: never overwrites
        except FileExistsError:
            return "kept"
        except OSError:
            if _present(path):
                return "kept"
            os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    try:
        back = json.loads(path.read_text(encoding="ascii"))
    except (OSError, ValueError) as exc:
        raise FirstRunError(f"read-back failed: {exc.__class__.__name__}") from None
    if back != doc:
        raise FirstRunError("read-back differs from what was written")
    return "written"
