"""Reader for the cached GGG PoE2 passive tree export (ROADMAP DATA-TREE-SRC).

The file is GGG's own `data.json` from the public poe2-skilltree-export
repository, fetched at build time by `snapshot.py` into
`<sidecar>\\Cache\\gamedata\\skilltree.json` (decision 0009 item 3 as
amended: fetch-only, never bundled). This module only READS that cache; it
never fetches, and the core works the same when the file is missing (every
lookup then returns None and `TreeCache.get()` returns None).

Shape assumption, UNVERIFIED against the live PoE2 file (no web access when
written; modelled on the PoE1 skilltree-export layout; ROADMAP review row
DATA-TREE-SHAPE confirms it):
- top level: an object with `nodes` (object keyed by the node id as a
  string) and `classes` (list of objects with `name` and an optional
  `ascendancies` list of objects with `id` / `name`);
- a node: `skill` (int id, optional; the key is used when missing), `name`,
  `stats` (list of strings), `ascendancyName` (string, ascendancy nodes
  only), `isNotable` / `isKeystone` / `isJewelSocket` (bools), and for a
  class start either `classStartIndex` (int into `classes`) or
  `classesStart` (list of class names).
Unknown fields are ignored; a malformed node is skipped, never an error.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .. import paths

FILE_NAME = "skilltree.json"
MAX_BYTES = 256 * 1024 * 1024


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
    def is_ascendancy(self):
        return bool(self.ascendancy)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "stats": list(self.stats),
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

    def resolve(self, node_ids):
        """[{id, name, ascendancy, notable, keystone}] for the given ids;
        an id missing from the tree reads with name None."""
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


def parse(doc):
    """TreeData from the decoded JSON document. Raises ValueError only when
    the top level is not an object with a `nodes` object."""
    if not isinstance(doc, dict) or not isinstance(doc.get("nodes"), dict):
        raise ValueError("not a passive tree export (no nodes object)")
    classes = []
    for c in doc.get("classes") if isinstance(doc.get("classes"), list) else ():
        classes.append(_str(c.get("name")) if isinstance(c, dict) else None)
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
        if isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < len(classes):
            if classes[idx]:
                starts.append(classes[idx])
        cs = raw.get("classesStart")
        if isinstance(cs, list):
            starts.extend(s for s in cs if isinstance(s, str) and s and s not in starts)
        nodes[nid] = Node(id=nid, name=_str(raw.get("name")), stats=stats,
                          ascendancy=_str(raw.get("ascendancyName")),
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
