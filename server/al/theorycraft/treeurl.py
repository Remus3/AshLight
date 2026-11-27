"""The loaded build as an official passive tree viewer link (TC-TREE-URL).

GGG's API Reference ("Passive Skill Tree URLs", research 0035 F10 and R7)
documents the link: base64url (RFC 4648 section 5) of a big-endian stream.
PoE2 uses version 7:

    uint32 version (7), uint8 class, uint8 ascendancy, uint16 count,
    then per node: uint16 hash, uint16 flags,
    uint8 weapon set        when flags bit 0 is set,
    uint16 override hash    when flags bit 1 is set.

This module only BUILDS the text of a link (decision 0017 pattern): it
makes no request, reads no file and the player opens the link in their own
browser. The class and ascendancy bytes are not listed by GGG; they are
read from the cached tree export (decision 0009) and never guessed:
- class: the 0-based index of the build's class in the export's `classes`;
- ascendancy: 0 for none, else 1 + the 0-based position of the build's
  ascendancy in that class's `ascendancies` list (placeholders kept), the
  version 6 convention (adjudicator ruling 2026-11-24, recorded in the
  TC-TREE-URL commit). An unknown class or ascendancy gives no link.
Node hashes are PoB2 spec node ids, which are export `skill` ids (treedata
module docstring); class and ascendancy start nodes are left out (the
example lists none), as are ids the export does not hold.
"""

import base64
import binascii
import struct

VERSION = 7
BASE = "https://pathofexile2.com/game/passive-skill-tree/"
FLAG_WEAPON_SET = 0x01
FLAG_OVERRIDE = 0x02
MAX_NODES = 0xFFFF
_KNOWN_FLAGS = FLAG_WEAPON_SET | FLAG_OVERRIDE


class TreeUrlError(ValueError):
    """The text is not a version 7 passive tree link."""


def decode(text):
    """{"version", "class_id", "ascendancy", "nodes": [{"hash", "flags",
    "weapon_set", "override"}]} from a link or its bare base64url tail.
    Raises TreeUrlError on a bad stream, another version or bytes left."""
    if not isinstance(text, str) or not text.strip():
        raise TreeUrlError("no tree link")
    tail = text.strip().rsplit("/", 1)[-1]
    # padding only at the end: Python 3.11's decoder stops at the first '='
    # and drops what follows, so bytes after it would pass unseen
    if "=" in tail.rstrip("="):
        raise TreeUrlError("not base64url")
    try:
        raw = base64.urlsafe_b64decode(tail + "=" * (-len(tail) % 4))
    except (binascii.Error, ValueError) as e:
        raise TreeUrlError("not base64url") from e
    if len(raw) < 8:
        raise TreeUrlError("too short")
    version, cls, asc, count = struct.unpack_from(">IBBH", raw, 0)
    if version != VERSION:
        raise TreeUrlError(f"version {version}, not {VERSION}")
    pos, nodes = 8, []
    for _ in range(count):
        if pos + 4 > len(raw):
            raise TreeUrlError("ends inside a node")
        h, flags = struct.unpack_from(">HH", raw, pos)
        pos += 4
        ws = ov = None
        if flags & FLAG_WEAPON_SET:
            if pos + 1 > len(raw):
                raise TreeUrlError("ends inside a weapon set")
            ws = raw[pos]
            pos += 1
        if flags & FLAG_OVERRIDE:
            if pos + 2 > len(raw):
                raise TreeUrlError("ends inside an override")
            (ov,) = struct.unpack_from(">H", raw, pos)
            pos += 2
        nodes.append({"hash": h, "flags": flags, "weapon_set": ws, "override": ov})
    if pos != len(raw):
        raise TreeUrlError(f"{len(raw) - pos} bytes left")
    return {"version": version, "class_id": cls, "ascendancy": asc, "nodes": nodes}


def _u(value, top):
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= top


def encode(doc, base=BASE):
    """The link for a decode()-shaped dict. A node's flags are kept as
    given, with bit 0 / bit 1 forced to match weapon_set / override.
    Raises TreeUrlError on an out-of-range value."""
    if not isinstance(doc, dict):
        raise TreeUrlError("not a tree document")
    cls, asc, nodes = doc.get("class_id"), doc.get("ascendancy"), doc.get("nodes") or []
    if not (_u(cls, 0xFF) and _u(asc, 0xFF)) or len(nodes) > MAX_NODES:
        raise TreeUrlError("class, ascendancy or count out of range")
    out = bytearray(struct.pack(">IBBH", VERSION, cls, asc, len(nodes)))
    for n in nodes:
        h, ws, ov = n.get("hash"), n.get("weapon_set"), n.get("override")
        flags = n.get("flags") or 0
        if not (_u(h, 0xFFFF) and _u(flags, 0xFFFF)):
            raise TreeUrlError("node hash or flags out of range")
        if ws is not None and not _u(ws, 0xFF):
            raise TreeUrlError("weapon set out of range")
        if ov is not None and not _u(ov, 0xFFFF):
            raise TreeUrlError("override out of range")
        flags = (flags & ~_KNOWN_FLAGS) | (FLAG_WEAPON_SET if ws is not None else 0) \
            | (FLAG_OVERRIDE if ov is not None else 0)
        out += struct.pack(">HH", h, flags)
        if ws is not None:
            out.append(ws)
        if ov is not None:
            out += struct.pack(">H", ov)
    return base + base64.urlsafe_b64encode(bytes(out)).decode("ascii")


def class_bytes(tree, class_name, ascendancy):
    """(class byte, ascendancy byte) from the cached export, or None when
    the class, or a named ascendancy, is not in it."""
    classes = getattr(tree, "classes", None) or ()
    if not isinstance(class_name, str) or class_name not in classes:
        return None
    cls = classes.index(class_name)
    if not ascendancy:
        return cls, 0
    order = (getattr(tree, "asc_order", None) or {}).get(class_name) or ()
    if ascendancy not in order:
        return None
    return cls, 1 + order.index(ascendancy)


def from_build(build, tree):
    """The link for a model.Build against a treedata.TreeData, or None
    without a build, tree, active spec, known class / ascendancy, or when
    the spec's ids miss the tree (treedata id_match not ok)."""
    if build is None or tree is None:
        return None
    spec = getattr(build, "active_spec", None)
    if spec is None:
        return None
    cb = class_bytes(tree, build.class_name, build.ascendancy)
    if cb is None or not tree.id_match(spec.nodes)["ok"]:
        return None
    attr_hashes = getattr(tree, "attr_hashes", None) or {}
    nodes, seen = [], set()
    for nid in spec.nodes:
        n = tree.node(nid)
        if n is None or nid in seen or not _u(nid, 0xFFFF) or n.class_start \
                or getattr(n, "asc_start", False):
            continue
        seen.add(nid)
        ws = spec.weapon_sets.get(nid)
        ov = attr_hashes.get(spec.attr_overrides.get(nid))
        nodes.append({"hash": nid, "flags": 0,
                      "weapon_set": ws if ws in (1, 2) else None, "override": ov})
    if len(nodes) > MAX_NODES:
        return None
    return encode({"class_id": cb[0], "ascendancy": cb[1], "nodes": nodes})
