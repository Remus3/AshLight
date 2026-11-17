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

Id space (DATA-TREE-IDS, research 0015): a PoB2 build's Spec `nodes`
attribute holds PoB2 tree node ids, and PoB2 sets each node's id from its
`skill` field; PoB2's own GGG converter keeps the export's `skill` ids
unchanged, and PoB2's 0_5 tree ids were all found in the GGG export with the
same names. So spec node ids ARE export `skill` ids and `resolve` maps them
1:1 with no table. `id_match` is the guard: a spec whose ids mostly miss the
loaded tree (a different id space, or a far-off tree version) reads as not
ok, and the build view then shows no names rather than wrong ones.
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
    def __init__(self, nodes, classes):
        self.nodes = nodes      # int id -> Node
        self.classes = classes  # tuple of class names, index order

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
    for c in doc.get("classes") if isinstance(doc.get("classes"), list) else ():
        classes.append(_str(c.get("name")) if isinstance(c, dict) else None)
        ascs = c.get("ascendancies") if isinstance(c, dict) else None
        for a in ascs if isinstance(ascs, list) else ():
            if isinstance(a, dict) and _str(a.get("id")) and _str(a.get("name")):
                asc_names.setdefault(a["id"], a["name"])
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
                          class_start=tuple(starts))
    return TreeData(nodes, tuple(classes))


def load(path):
    """TreeData from a cache file. Raises OSError / ValueError."""
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("tree file too large")
    return parse(json.loads(path.read_bytes()))


def default_path(environ=None):
    return paths.sidecar_dir("Cache", environ) / "gamedata" / FILE_NAME


class TreeCache:
    """Lazy, mtime-checked holder of the cached tree. `get()` returns the
    TreeData, or None when the file is missing or unreadable (never raises),
    and re-reads only when the file's mtime or size changes."""

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
