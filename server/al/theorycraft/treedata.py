"""Reader for the cached GGG PoE2 passive tree export (ROADMAP DATA-TREE-SRC).

The file is GGG's own `data.json` from the public poe2-skilltree-export
repository, fetched at build time by `snapshot.py` into
`<sidecar>\\Cache\\gamedata\\skilltree.json` (decision 0009 item 3 as
amended: fetch-only, never bundled). This module only READS that cache; it
never fetches, and the core works the same when the file is missing (every
lookup then returns None and `TreeCache.get()` returns None).

Shape, checked against the real PoE2 file in research 0014
(DATA-TREE-SHAPE, 2026-11-17):
- top level: an object with `nodes` (object keyed by the node id as a
  string) and `classes` (list of objects with `name` and an optional
  `ascendancies` list of objects with `id` / `name`);
- a node: `skill` (int id; the key is used when missing), `name`, `stats`
  (list of strings, may hold [Key|Shown] markup; `display_stat` strips it),
  `ascendancyId` (an ascendancy id on ascendancy nodes, mapped to its name
  through classes[].ascendancies; the id itself when unmapped),
  `isNotable` / `isKeystone` / `isJewelSocket` (bools), and on a class start
  `classStartIndex` (a list of indexes into `classes`; a bare int is also
  accepted).
Legacy keys `ascendancyName` (a name) and `classesStart` (class names) are
still accepted. The pseudo node `root` has no skill and a non-numeric key,
so it is skipped. Unknown fields are ignored; a malformed node is skipped,
never an error.

Drawing fields (PROGRESSION-VIEW, decision 0092; checked against the
cached export 2026-11-27): each node also carries `x` / `y` (its position
in the export's own units, about -22600 to 21800 wide; the ascendancy
trees sit apart from the main tree), `group` / `orbit` / `orbitIndex`
(not kept: x / y already place the node), `out` / `in` (linked node ids
as strings, "root" for the pseudo node) and `isMastery`. The top level
also has an `edges` list ({from, to}) and `groups`; the node lists give
the same links, so only they are read.

Id space (DATA-TREE-IDS, research 0015): a PoB2 build's Spec `nodes`
attribute holds PoB2 tree node ids, and PoB2 sets each node's id from its
`skill` field; PoB2's own GGG converter keeps the export's `skill` ids
unchanged, and PoB2's 0_5 tree ids were all found in the GGG export with the
same names. So spec node ids ARE export `skill` ids and `resolve` maps them
1:1 with no table. `id_match` is the guard: a spec whose ids mostly miss the
loaded tree (a different id space, or a far-off tree version) reads as not
ok, and the build view then shows no names rather than wrong ones.

String ids (TC-BUILDFILE, research 0021): each node also carries the
export's `id` slug (e.g. `strength89`; null on some nodes), kept as
`Node.gid`. The game's `.build` file names passives by that slug, so the
mapping PoB node id -> `.build` passive id is: spec id == export `skill` ->
that node's `id`. No table, no guess: a null or missing slug is skipped.

Class map (TC-ASC-FROM-TREE, F-113): `parse` also keeps ascendancy name ->
class name from classes[].ascendancies (`TreeData.class_map`), and each
good read of the CURRENT export by `TreeCache.get()` publishes it, so
`class_of(name)` answers for an ascendancy GGG adds with no code change.
The newest good map stays published while the file is missing or broken;
the previous export (DATA-TREE-HOLD) never publishes. Names come only from
the cached GGG export (decision 0009: nothing bundled); the built-in table
in charjson stays the fallback and gains no name.
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .. import paths

FILE_NAME = "skilltree.json"
MAX_BYTES = 256 * 1024 * 1024
# Share of a spec's ids that must exist in the tree for its names to be
# trusted (DATA-TREE-IDS). Same id space across one tree version measured
# 99.5 percent; ids from an unrelated space hit about 8 percent by chance
# (about 5k nodes over a 16-bit id range), so 0.5 separates the two.
MIN_ID_MATCH = 0.5

_MARKUP = re.compile(r"\[([^\[\]|]*)\|([^\[\]]*)\]|\[([^\[\]|]*)\]")


def display_stat(text):
    """Stat text for display: `[Key|Shown]` reads as `Shown` and `[Word]`
    as `Word`; anything else is left as is."""
    if not isinstance(text, str):
        return text
    return _MARKUP.sub(lambda m: m.group(2) if m.group(2) is not None
                       else m.group(3), text)


@dataclass(frozen=True)
class Node:
    id: int
    name: str = None
    stats: tuple = ()
    ascendancy: str = None  # ascendancy name, None for the main tree
    notable: bool = False
    keystone: bool = False
    jewel_socket: bool = False
    class_start: tuple = ()  # class names that start on this node
    gid: str = None  # the export's string `id` slug (TC-BUILDFILE), None when null
    asc_start: bool = False  # `isAscendancyStart` (TC-TREE-URL)
    # PROGRESSION-VIEW (decision 0092): the export's own drawing position
    # (`x` / `y`, None when the node has none), its links (`out` and `in`,
    # numeric ids only, so the pseudo node `root` is left out) and
    # `isMastery`; not part of to_dict
    x: float = None
    y: float = None
    links: tuple = ()
    mastery: bool = False

    @property
    def display_stats(self):
        return tuple(display_stat(s) for s in self.stats)

    @property
    def is_ascendancy(self):
        return bool(self.ascendancy)

    def to_dict(self):
        return {"id": self.id, "name": self.name,
                "stats": list(self.display_stats),
                "ascendancy": self.ascendancy, "notable": self.notable,
                "keystone": self.keystone, "jewel_socket": self.jewel_socket,
                "class_start": list(self.class_start)}


def _id(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def _str(value):
    return value if isinstance(value, str) and value else None


class TreeData:
    def __init__(self, nodes, classes, ascendancy_ids=None, class_map=None,
                 asc_order=None, attr_hashes=None):
        self.nodes = nodes      # int id -> Node
        self.classes = classes  # tuple of class names, index order
        self._asc_ids = dict(ascendancy_ids or {})  # ascendancy name -> id
        self.class_map = dict(class_map or {})  # ascendancy name -> class name
        # TC-TREE-URL: class name -> its ascendancy names in export order,
        # a placeholder entry (no name) kept as None so positions hold
        self.asc_order = dict(asc_order or {})
        # TC-TREE-URL: "str" / "dex" / "int" -> the export's generic
        # attribute skill override hash (left out unless exactly one)
        self.attr_hashes = dict(attr_hashes or {})

    def ascendancy_id(self, name):
        """The export's ascendancy id (e.g. `Witch1`) for a name, or None."""
        return self._asc_ids.get(name) if isinstance(name, str) else None

    def node(self, node_id):
        nid = _id(node_id)
        return self.nodes.get(nid) if nid is not None else None

    def name(self, node_id):
        n = self.node(node_id)
        return n.name if n else None

    def class_starts(self):
        """{class name: node id} for every class start node."""
        out = {}
        for n in self.nodes.values():
            for cls in n.class_start:
                out.setdefault(cls, n.id)
        return out

    def id_match(self, node_ids):
        """{known, total, ok}: how many of the given ids exist in this tree.
        ok is False when fewer than MIN_ID_MATCH of them do (the ids are not
        export skill ids of this tree); an empty list is ok."""
        ids = [n for n in (_id(r) for r in node_ids or ()) if n is not None]
        known = sum(1 for n in ids if n in self.nodes)
        return {"known": known, "total": len(ids),
                "ok": not ids or known >= MIN_ID_MATCH * len(ids)}

    def resolve(self, node_ids):
        """[{id, name, ascendancy, notable, keystone}] for the given ids;
        an id missing from the tree reads with name None. PoB2 spec node ids
        are export `skill` ids (module docstring), so no mapping applies;
        check `id_match` before trusting the names."""
        out = []
        for raw in node_ids or ():
            nid = _id(raw)
            if nid is None:
                continue
            n = self.nodes.get(nid)
            out.append({"id": nid, "name": n.name if n else None,
                        "ascendancy": n.ascendancy if n else None,
                        "notable": bool(n and n.notable),
                        "keystone": bool(n and n.keystone)})
        return out


def _coord(value):
    """A finite drawing coordinate of the export, or None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if abs(value) < 1e7 else None


def _links(raw, nid):
    """The numeric ids of a node's `out` and `in` lists, each once, in
    export order (the pseudo node "root" and the node itself left out)."""
    out = []
    for field in ("out", "in"):
        seq = raw.get(field)
        for other in seq if isinstance(seq, list) else ():
            oid = _id(other)
            if oid is not None and oid != nid and oid not in out:
                out.append(oid)
    return tuple(out)


def _ascendancy(raw, asc_names):
    """Ascendancy name from `ascendancyId` (the id itself when no class
    lists it), else the legacy `ascendancyName`, else None."""
    aid = _str(raw.get("ascendancyId"))
    if aid:
        return asc_names.get(aid, aid)
    return _str(raw.get("ascendancyName"))


def parse(doc):
    """TreeData from the decoded JSON document. Raises ValueError only when
    the top level is not an object with a `nodes` object."""
    if not isinstance(doc, dict) or not isinstance(doc.get("nodes"), dict):
        raise ValueError("not a passive tree export (no nodes object)")
    classes = []
    asc_names = {}  # ascendancy id -> name
    class_map = {}  # ascendancy name -> class name (TC-ASC-FROM-TREE)
    asc_order = {}  # class name -> ascendancy names in order (TC-TREE-URL)
    for c in doc.get("classes") if isinstance(doc.get("classes"), list) else ():
        cname = _str(c.get("name")) if isinstance(c, dict) else None
        classes.append(cname)
        ascs = c.get("ascendancies") if isinstance(c, dict) else None
        order = []
        for a in ascs if isinstance(ascs, list) else ():
            order.append(_str(a.get("name")) if isinstance(a, dict) else None)
            if not isinstance(a, dict):
                continue
            if _str(a.get("id")) and _str(a.get("name")):
                asc_names.setdefault(a["id"], a["name"])
            if cname and _str(a.get("name")):
                class_map.setdefault(a["name"], cname)
        if cname and cname not in asc_order:
            asc_order[cname] = tuple(order)
    nodes = {}
    for key, raw in doc["nodes"].items():
        if not isinstance(raw, dict):
            continue
        nid = _id(raw.get("skill"))
        if nid is None:
            nid = _id(key)
        if nid is None:
            continue
        stats = raw.get("stats")
        stats = tuple(s for s in stats if isinstance(s, str)) if isinstance(stats, list) else ()
        starts = []
        idx = raw.get("classStartIndex")
        for i in idx if isinstance(idx, list) else (idx,):
            if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(classes):
                if classes[i] and classes[i] not in starts:
                    starts.append(classes[i])
        cs = raw.get("classesStart")
        if isinstance(cs, list):
            starts.extend(s for s in cs if isinstance(s, str) and s and s not in starts)
        nodes[nid] = Node(id=nid, name=_str(raw.get("name")), stats=stats,
                          ascendancy=_ascendancy(raw, asc_names),
                          notable=raw.get("isNotable") is True,
                          keystone=raw.get("isKeystone") is True,
                          jewel_socket=raw.get("isJewelSocket") is True,
                          class_start=tuple(starts), gid=_str(raw.get("id")),
                          asc_start=raw.get("isAscendancyStart") is True,
                          x=_coord(raw.get("x")), y=_coord(raw.get("y")),
                          links=_links(raw, nid),
                          mastery=raw.get("isMastery") is True)
    asc_ids = {}
    for aid, name in asc_names.items():
        asc_ids.setdefault(name, aid)
    return TreeData(nodes, tuple(classes), asc_ids, class_map, asc_order,
                    _attr_hashes(doc.get("skillOverrides")))


# TC-TREE-URL: the export's generic attribute overrides (the choice an
# Attribute node takes), found by the override's own name and id prefix
_ATTR_NAMES = {"Strength": "str", "Dexterity": "dex", "Intelligence": "int"}


def _attr_hashes(raw):
    """{"str"|"dex"|"int": skill hash} from `skillOverrides`; an attribute
    with no entry or more than one candidate is left out (never guessed)."""
    found = {}
    for key, o in raw.items() if isinstance(raw, dict) else ():
        if not isinstance(o, dict):
            continue
        attr = _ATTR_NAMES.get(o.get("name"))
        oid = _str(o.get("id"))
        sid = _id(o.get("skill"))
        if sid is None:
            sid = _id(key)
        if attr and oid and oid.startswith("generic_attribute_") \
                and sid is not None and 0 <= sid <= 0xFFFF:
            found.setdefault(attr, set()).add(sid)
    return {a: next(iter(s)) for a, s in found.items() if len(s) == 1}


_published = {}  # ascendancy name -> class name from the newest good export


def publish(tree):
    """Make `tree`'s class map the one `class_of` reads (None clears it).
    TreeCache.get() calls it on each new good read of the current export."""
    global _published
    _published = dict(tree.class_map) if tree is not None else {}


def class_of(name):
    """The base class of an ascendancy named in the newest good cached tree
    export, or None (an unknown name, a class name, or no export read)."""
    return _published.get(name) if isinstance(name, str) else None


def load(path):
    """TreeData from a cache file. Raises OSError / ValueError."""
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("tree file too large")
    return parse(json.loads(path.read_bytes()))


def default_path(environ=None):
    return paths.sidecar_dir("Cache", environ) / "gamedata" / FILE_NAME


PREV_FILE_SUFFIX = ".prev.json"


def previous_path(path):
    """`skilltree.prev.json` beside `skilltree.json`: the copy snapshot.py
    keeps of the replaced export (DATA-TREE-HOLD)."""
    path = Path(path)
    stem = path.name[:-len(".json")] if path.name.endswith(".json") else path.name
    return path.with_name(stem + PREV_FILE_SUFFIX)


class _FileHolder:
    """Lazy, mtime-checked reader of one tree file; never raises."""

    def __init__(self, path):
        self.path = Path(path)
        self._key = None
        self._data = None
        self.error = None

    def get(self):
        try:
            st = os.stat(self.path)
        except OSError:
            self._key, self._data, self.error = None, None, None
            return None
        key = (st.st_mtime_ns, st.st_size)
        if key != self._key:
            self._key = key
            try:
                self._data, self.error = load(self.path), None
            except (OSError, ValueError) as e:
                self._data, self.error = None, f"{type(e).__name__}: {e}"
        return self._data


def _share(tree, node_ids):
    m = tree.id_match(node_ids)
    return m["known"] / m["total"] if m["total"] else 0.0


class TreeCache:
    """Lazy, mtime-checked holder of the cached tree. `get()` returns the
    TreeData, or None when the file is missing or unreadable (never raises),
    and re-reads only when the file's mtime or size changes.

    DATA-TREE-HOLD: it also watches the previous export kept beside it
    (`skilltree.prev.json`, written by snapshot.keep_previous). `best_for`
    picks, per build, the cached tree whose id_match share for the build's
    node ids is highest; the newest wins a tie, so a build made on the
    previous tree version keeps its names and .build ids after GGG ships a
    new export."""

    def __init__(self, path):
        self._cur = _FileHolder(path)
        self._prev = _FileHolder(previous_path(path))
        self._published = None  # the TreeData this cache last published

    @property
    def path(self):
        return self._cur.path

    @property
    def prev_path(self):
        return self._prev.path

    @property
    def error(self):
        return self._cur.error

    def get(self):
        tree = self._cur.get()
        if tree is not None and tree is not self._published:
            self._published = tree
            publish(tree)
        return tree

    def get_previous(self):
        return self._prev.get()

    def best_for(self, node_ids):
        """The cached TreeData with the highest id_match share for these
        node ids (newest first on a tie), or None when no tree is cached.
        With no node ids the newest readable tree is returned."""
        best, best_share = None, -1.0
        for tree in (self.get(), self.get_previous()):
            if tree is None:
                continue
            share = _share(tree, node_ids)
            if share > best_share:
                best, best_share = tree, share
        return best
