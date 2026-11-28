"""KINDLER-STORE (decision 0081 points 7, 11 and 17): the Kindler tabs.

One bounded player-data file, FILE_NAME under the core's runtime dir
(ops/runtime, gitignored), schema 1, written atomically with one `.bak`
of its last good copy (jsonfile, F-014) and read with the .bak restore.
It holds at most MAX_TABS generator tabs in all (a seventh is refused
with FULL_TEXT) and which tab is shown, so the tab list and the shown tab
survive a reload and an app exit.

Per tab: a stable id, the player's label (at most MAX_LABEL characters,
control characters stripped; empty means the default label), the class,
the league, the toggle values (TOGGLES, each tri-state with "unsure" =
no constraint; DEFENCE for the defence toggle), the chosen template id,
the follow flag (point 17, on by default), the candidate count and a
result summary (template id, PoB headline numbers, time, partial,
scored, stale; set only by the engine through set_result; decision 0096
adds the best row's stage id and variant, optional, so a restart can
restore the plan with no Generate). Never item
text, a path or a name of another player. The order is the list order
(point 11): move() swaps a tab with its neighbour; nothing is dragged.

A class or toggle change marks the result stale (point 4); nothing is
regenerated here. clear() empties the file and removes the .bak (Clear
run history, decision 0036). export_block() / check_block() are the
settings export block (settingsio.with_gen_builds / gen_builds_of): no
ids and no shown tab, every field strictly checked on import.

A change is made in memory first, then written; an OSError from the
write leaves the change in memory (the plug marks its Saver, which
writes it again with back-off, RUN-DURABLE-STORES). Thread safe.
Standard library only; nothing is read from the game, nothing is sent.
"""

import re
import threading
from pathlib import Path

from .. import jsonfile, num, paths

FILE_NAME = "gen_builds.json"
SCHEMA = 1
MAX_TABS = 6
MAX_LABEL = 32
MAX_FIELD = 64  # class, league, template id
MAX_CANDIDATES = 12  # decision 0081 point 3
MAX_BYTES = 64 * 1024
MAX_SERIAL = 999999

TOGGLES = ("melee", "spell", "minion", "bow", "crit")
TRI = ("yes", "no", "unsure")
DEFENCE = ("life", "energy_shield", "hybrid", "unsure")
UNSURE = "unsure"
TOGGLE_KEYS = TOGGLES + ("defence",)
RESULT_NUMBERS = ("dps", "ehp")
TAB_FIELDS = ("id", "label", "class", "league", "toggles", "template", "follow",
              "candidates", "result")
RESULT_FIELDS = ("template", "at", "dps", "ehp", "partial", "scored", "stale", "key",
                 "stage", "variant")
MAX_VARIANT = 7  # decision 0096: the best row's main skill index (0-based)

# Player words (design 0001: plain, no jargon)
FULL_TEXT = "You can keep 6 Kindler tabs. Close one to add another."
GONE_TEXT = "That Kindler tab is gone. Reload the page."
BAD_TEXT = "That change isn't one AshLight understands."

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_ID = re.compile(r"^k[0-9]{1,6}$")
_TEMPLATE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_KEY = re.compile(r"^[0-9a-f]{64}$")


class GenError(ValueError):
    """A change the store refuses; str() is the player's sentence."""


def default_path(runtime=None):
    """FILE_NAME in `runtime`, else in paths.runtime_dir()."""
    return Path(runtime if runtime is not None else paths.runtime_dir()) / FILE_NAME


def clean_text(value, cap):
    """value with control characters removed, trimmed and cut to `cap`;
    None for a non-string."""
    if not isinstance(value, str):
        return None
    return _CONTROL.sub("", value).strip()[:cap].strip()


def clean_label(value):
    """A player label: control characters stripped, at most MAX_LABEL
    characters; "" (the default label) for anything else."""
    out = clean_text(value, MAX_LABEL)
    return out or ""


def default_label(serial):
    return f"Kindler {serial}"


def _serial(tab_id):
    return int(tab_id[1:])


def default_toggles():
    return {k: UNSURE for k in TOGGLE_KEYS}


def _bad(strict):
    if strict:
        raise GenError(BAD_TEXT)


def _field(value, cap, strict):
    out = clean_text(value, cap) if value is not None else ""
    if out is None:
        _bad(strict)
        return ""
    return out


def _toggles(raw, strict, base=None):
    out = dict(base) if base else default_toggles()
    if raw is None:
        return out
    if not isinstance(raw, dict):
        _bad(strict)
        return out
    for key, value in raw.items():
        allowed = DEFENCE if key == "defence" else TRI
        if key not in TOGGLE_KEYS or value not in allowed:
            _bad(strict)
            continue
        out[key] = value
    return out


def _template(value, strict):
    if value in (None, ""):
        return ""
    if isinstance(value, str) and _TEMPLATE.match(value):
        return value
    _bad(strict)
    return ""


def _count(value, strict):
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) \
            or not 0 <= value <= MAX_CANDIDATES:
        _bad(strict)
        return 0
    return value


def clean_result(raw, strict=False):
    """A bounded result summary, or None."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        _bad(strict)
        return None
    if set(raw) - set(RESULT_FIELDS):
        _bad(strict)
    template = _template(raw.get("template"), strict)
    at = num.finite(raw.get("at"))
    if not template or at is None or at < 0:
        _bad(strict)
        return None
    out = {"template": template, "at": int(at)}
    for key in RESULT_NUMBERS:
        v = raw.get(key)
        if v is None:
            out[key] = None
            continue
        f = num.finite(v)
        if f is None or isinstance(v, bool):
            _bad(strict)
            f = None
        out[key] = None if f is None else round(f, 2)
    for key in ("partial", "scored", "stale"):
        v = raw.get(key, False)
        if not isinstance(v, bool):
            _bad(strict)
            v = False
        out[key] = v
    key = raw.get("key", "")
    if key and not (isinstance(key, str) and _KEY.match(key)):
        _bad(strict)
        key = ""
    out["key"] = key
    # decision 0096: the best row's stage id and variant (optional; an old
    # file without them restores the last stage and variant 0)
    stage = _template(raw.get("stage"), strict)
    if stage:
        out["stage"] = stage
    variant = raw.get("variant")
    if variant is not None:
        if isinstance(variant, bool) or not isinstance(variant, int)                 or not 0 <= variant <= MAX_VARIANT:
            _bad(strict)
        else:
            out["variant"] = variant
    if not out["scored"]:  # decision 0081 points 5, 12: no number with the calc off
        out["dps"] = out["ehp"] = None
    return out


def clean_tab(raw, strict=False, tab_id=None):
    """A bounded tab, or None for a non-dict. strict: raise GenError on
    any bad field instead of falling back to its default. tab_id: the id
    to give it (import), else its own (load)."""
    if not isinstance(raw, dict):
        _bad(strict)
        return None
    if set(raw) - set(TAB_FIELDS):
        _bad(strict)  # never item text or any other field
    if tab_id is None:
        tab_id = raw.get("id")
        if not (isinstance(tab_id, str) and _ID.match(tab_id)):
            return None
    label = raw.get("label", "")
    if label is not None and not isinstance(label, str):
        _bad(strict)
        label = ""
    follow = raw.get("follow", True)
    if not isinstance(follow, bool):
        _bad(strict)
        follow = True
    return {"id": tab_id, "label": clean_label(label),
            "class": _field(raw.get("class"), MAX_FIELD, strict),
            "league": _field(raw.get("league"), MAX_FIELD, strict),
            "toggles": _toggles(raw.get("toggles"), strict),
            "template": _template(raw.get("template"), strict),
            "follow": follow,
            "candidates": _count(raw.get("candidates"), strict),
            "result": clean_result(raw.get("result"), strict)}


def clean_doc(doc):
    """(tabs, shown, next serial) of a loaded document; bad parts dropped."""
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return [], "", 1
    tabs, seen = [], set()
    for raw in doc.get("tabs") if isinstance(doc.get("tabs"), list) else ():
        tab = clean_tab(raw)
        if tab is None or tab["id"] in seen:
            continue
        seen.add(tab["id"])
        tabs.append(tab)
        if len(tabs) >= MAX_TABS:
            break
    shown = doc.get("shown")
    if shown not in seen:
        shown = tabs[0]["id"] if tabs else ""
    top = max((_serial(t["id"]) for t in tabs), default=0)
    nxt = doc.get("next")
    if isinstance(nxt, bool) or not isinstance(nxt, int) or nxt <= top \
            or nxt > MAX_SERIAL:
        nxt = top + 1
    return tabs, shown, nxt


def check_block(block):
    """The settings import block, strictly checked: [tab without id] of at
    most MAX_TABS. Raises GenError on anything the store would not keep."""
    if not isinstance(block, dict) or set(block) != {"tabs"} \
            or not isinstance(block["tabs"], list) or len(block["tabs"]) > MAX_TABS:
        raise GenError(BAD_TEXT)
    out = []
    for raw in block["tabs"]:
        if not isinstance(raw, dict) or "id" in raw:
            raise GenError(BAD_TEXT)
        tab = clean_tab(raw, strict=True, tab_id="k0")
        del tab["id"]
        out.append(tab)
    return {"tabs": out}


class GenStore:
    """The Kindler tabs file and its in-memory copy."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        doc = jsonfile.read_json(self.path, max_bytes=MAX_BYTES, kind=dict, backup=True)
        self._tabs, self._shown, self._next = clean_doc(doc)

    # -- reads
    def _find(self, tab_id):
        for i, tab in enumerate(self._tabs):
            if tab["id"] == tab_id:
                return i
        raise GenError(GONE_TEXT)

    def doc(self):
        """The file document of the memory copy."""
        with self._lock:
            return self._doc()

    def _doc(self):
        return {"schema": SCHEMA, "shown": self._shown, "next": self._next,
                "tabs": [dict(t, toggles=dict(t["toggles"]),
                              result=dict(t["result"]) if t["result"] else None)
                         for t in self._tabs]}

    def tab(self, tab_id):
        with self._lock:
            return self._doc()["tabs"][self._find(tab_id)]

    def view(self):
        """The route's answer: tabs in order with their shown label."""
        with self._lock:
            doc = self._doc()
        tabs = []
        for t in doc["tabs"]:
            tabs.append(dict(t, label=t["label"] or default_label(_serial(t["id"])),
                             custom_label=bool(t["label"])))
        return {"tabs": tabs, "shown": doc["shown"], "max": MAX_TABS,
                "full": len(tabs) >= MAX_TABS,
                "full_text": FULL_TEXT if len(tabs) >= MAX_TABS else ""}

    # -- the write
    def save(self):
        """Write the memory copy (Saver callable). An empty list also
        removes the .bak (a cleared store keeps no copy)."""
        with self._lock:
            doc = self._doc()
        jsonfile.write_json(self.path, doc, backup=True)
        if not doc["tabs"]:
            try:
                jsonfile.bak_path(self.path).unlink(missing_ok=True)
            except OSError:
                pass  # it holds the empty document written just before

    def _change(self, fn):
        with self._lock:
            out = fn()
        self.save()  # OSError: the change stays in memory
        return out

    # -- changes (each raises GenError for a refused change)
    def add(self, label=None, cls=None, league=None):
        """A new tab at the end, shown. Returns its id."""
        def go():
            if len(self._tabs) >= MAX_TABS:
                raise GenError(FULL_TEXT)
            if self._next > MAX_SERIAL:
                self._next = 1
                while any(_serial(t["id"]) == self._next for t in self._tabs):
                    self._next += 1
            tab = clean_tab({"label": label, "class": cls, "league": league},
                            strict=True, tab_id=f"k{self._next}")
            self._next += 1
            self._tabs.append(tab)
            self._shown = tab["id"]
            return tab["id"]
        return self._change(go)

    def rename(self, tab_id, label):
        if label is not None and not isinstance(label, str):
            raise GenError(BAD_TEXT)

        def go():
            self._tabs[self._find(tab_id)]["label"] = clean_label(label)
        return self._change(go)

    def move(self, tab_id, step):
        """Move a tab one place left (-1) or right (+1). False at an end."""
        if step not in (-1, 1):
            raise GenError(BAD_TEXT)

        def go():
            i = self._find(tab_id)
            j = i + step
            if not 0 <= j < len(self._tabs):
                return False
            self._tabs[i], self._tabs[j] = self._tabs[j], self._tabs[i]
            return True
        with self._lock:
            i = self._find(tab_id)
            if not 0 <= i + step < len(self._tabs):
                return False
        return self._change(go)

    def close(self, tab_id):
        """Close a tab; a shown tab passes the shown mark to its right
        neighbour, else its left one, else none."""
        def go():
            i = self._find(tab_id)
            del self._tabs[i]
            if self._shown == tab_id:
                if self._tabs:
                    self._shown = self._tabs[min(i, len(self._tabs) - 1)]["id"]
                else:
                    self._shown = ""
        return self._change(go)

    def show(self, tab_id):
        def go():
            self._find(tab_id)
            self._shown = tab_id
        return self._change(go)

    def update(self, tab_id, fields):
        """Change class, league, toggles, template and follow (any of
        them). A class or toggle change marks the result stale."""
        if not isinstance(fields, dict) or not fields or set(fields) - {
                "class", "league", "toggles", "template", "follow"}:
            raise GenError(BAD_TEXT)

        def go():
            tab = self._tabs[self._find(tab_id)]
            new = dict(tab)
            if "class" in fields:
                new["class"] = _field(fields["class"], MAX_FIELD, True)
            if "league" in fields:
                new["league"] = _field(fields["league"], MAX_FIELD, True)
            if "toggles" in fields:
                new["toggles"] = _toggles(fields["toggles"], True, base=tab["toggles"])
            if "template" in fields:
                new["template"] = _template(fields["template"], True)
            if "follow" in fields:
                if not isinstance(fields["follow"], bool):
                    raise GenError(BAD_TEXT)
                new["follow"] = fields["follow"]
            if new["result"] and (new["class"] != tab["class"]
                                  or new["toggles"] != tab["toggles"]):
                new["result"] = dict(new["result"], stale=True)
            tab.update(new)
        return self._change(go)

    def set_result(self, tab_id, result, candidates=0):
        """The engine's result summary (not stale) and candidate count."""
        res = clean_result(dict(result, stale=False) if isinstance(result, dict)
                           else result, strict=True)
        count = _count(candidates, True)

        def go():
            tab = self._tabs[self._find(tab_id)]
            tab["result"] = res
            tab["candidates"] = count
        return self._change(go)

    def clear(self):
        """Forget every tab (Clear run history): the file holds an empty
        list and its .bak is removed."""
        def go():
            self._tabs = []
            self._shown = ""
        return self._change(go)

    # -- the settings export block (decision 0036)
    def export_block(self):
        """{"tabs": [tab without id]} in order, or None with no tab."""
        with self._lock:
            tabs = self._doc()["tabs"]
        if not tabs:
            return None
        return {"tabs": [{k: v for k, v in t.items() if k != "id"} for t in tabs]}

    def import_tabs(self, tabs):
        """Add checked block tabs (check_block) after the current ones
        while there is room; a tab is never overwritten. Returns (added,
        full)."""
        def go():
            added = 0
            for raw in tabs:
                if len(self._tabs) >= MAX_TABS:
                    break
                tab = dict(raw, id=f"k{self._next}", toggles=dict(raw["toggles"]),
                           result=dict(raw["result"]) if raw["result"] else None)
                self._next += 1
                self._tabs.append(tab)
                added += 1
            if added and not self._shown:
                self._shown = self._tabs[0]["id"]
            return added, len(tabs) - added
        if not tabs:
            return 0, 0
        return self._change(go)
