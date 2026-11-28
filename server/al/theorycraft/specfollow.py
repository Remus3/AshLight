"""TC-SPEC-FOLLOW (research 0064 G1, decision 0089): the loaded build's
tree spec follows the character's level.

A pasted PoB build may carry several tree specs, and guide exports title
them by level ("Level 1-30", "lvl 70+", "Level 45"). title_band() reads
one level band from a spec title by a fixed text rule; a title with no
level, two levels, or a level outside 1 to 100 gives None (never a guess).
pick() takes the spec whose band holds the character level (decision 0038)
with the highest start; no match, an unknown level, or a tie that does not
hold PoB's own active spec keeps PoB's active spec.

follow() returns the build as the tree view, the tree link, the .build
download and the calc read it: the picked spec is the active spec and the
XML's <Tree activeSpec> attribute names it, so PoB's own unmodified load
(TreeTab:Load, SetActiveSpec) selects the same spec in the bridge with no
new bridge command. The player's pasted XML is kept for the share code.
Nothing is fetched and nothing is run.
"""

import dataclasses
import re

from . import model

MIN_LEVEL = 1
MAX_LEVEL = 100

_N = r"(\d{1,3})"
_LV = r"(?:level|lvl|lv)\.?\s*"
# "Level 30", "lvl 1-30", "Lv. 31 to 60", "level 70+", "lvl 1 - lvl 30"
_WORD = re.compile(r"(?<![A-Za-z0-9])" + _LV + _N
                   + r"(?:\s*(?:-|to)\s*(?:" + _LV + r")?" + _N + r"|\s*(\+))?(?![A-Za-z0-9])",
                   re.IGNORECASE)
# a title that is only a number or a band: "30", "1-30", "70+"
_BARE = re.compile(r"\s*" + _N + r"(?:\s*-\s*" + _N + r"|\s*(\+))?\s*")
_TREE_TAG = re.compile(r"<Tree(?=[\s/>])[^>]*>")
_ACTIVE_ATTR = re.compile(r"(\sactiveSpec\s*=\s*)(\"[^\"]*\"|'[^']*')")


def _band(lo, hi):
    lo = int(lo)
    hi = None if hi is None else int(hi)
    if not MIN_LEVEL <= lo <= MAX_LEVEL:
        return None
    if hi is not None and not lo <= hi <= MAX_LEVEL:
        return None
    return (lo, hi)


def title_band(title):
    """(low, high) from a spec title, high None for an open band ("Level
    30", "70+"); None when the title names no level or more than one."""
    if not isinstance(title, str) or not title.strip():
        return None
    found = _WORD.findall(title)
    if len(found) > 1:
        return None
    if found:
        lo, hi, _plus = found[0]
        return _band(lo, hi or None)
    m = _BARE.fullmatch(title)
    if m:
        return _band(m.group(1), m.group(2))
    return None


def pick(specs, active_index, level):
    """(index, by_level): the spec index to use. by_level is True when a
    title band held `level`; else `active_index` (PoB's active spec)."""
    if (not isinstance(level, int) or isinstance(level, bool)
            or not MIN_LEVEL <= level <= MAX_LEVEL or not specs):
        return active_index, False
    held = []
    for i, spec in enumerate(specs):
        band = title_band(getattr(spec, "title", None))
        if band is None:
            continue
        lo, hi = band
        if lo <= level and (hi is None or level <= hi):
            held.append((lo, i))
    if not held:
        return active_index, False
    best = max(lo for lo, _ in held)
    top = [i for lo, i in held if lo == best]
    if len(top) == 1:
        return top[0], True
    if active_index in top:
        return active_index, True
    return active_index, False  # two specs claim the level: no guess


def set_active_spec(xml, number):
    """The XML with its one <Tree> tag's activeSpec set to `number`
    (1-based), every other byte kept; None when the tag is not found
    exactly once."""
    tags = list(_TREE_TAG.finditer(xml))
    if len(tags) != 1:
        return None
    tag = tags[0]
    text = tag.group(0)
    value = '"%d"' % number
    attrs = list(_ACTIVE_ATTR.finditer(text))
    if len(attrs) > 1:
        return None
    if attrs:
        a = attrs[0]
        text = text[:a.start(2)] + value + text[a.end(2):]
    else:
        text = "<Tree activeSpec=" + value + text[len("<Tree"):]
    return xml[:tag.start()] + text + xml[tag.end():]


def follow(build, level):
    """The build with its tree spec picked for `level`. A build already on
    the picked spec, or one whose XML cannot be pointed at it (checked by a
    fresh parse), comes back with only the follow fields set."""
    if build is None:
        return None
    base_xml = build.pasted_xml if build.pasted_xml is not None else build.raw_xml
    pob_index = build.pob_spec_index
    idx, by_level = pick(build.specs, pob_index, level)
    lvl = level if isinstance(level, int) and not isinstance(level, bool) else None

    def pasted(matched):
        return dataclasses.replace(build, raw_xml=base_xml, active_spec_index=pob_index,
                                   pasted_xml=None, pasted_spec_index=None,
                                   spec_by_level=matched, follow_level=lvl)

    if idx is None or idx == pob_index:
        return pasted(bool(by_level and idx is not None))
    if idx == build.active_spec_index and build.pasted_xml is not None:
        return dataclasses.replace(build, follow_level=lvl)  # already on it
    new_xml = set_active_spec(base_xml, idx + 1)
    if new_xml is None:
        return pasted(False)
    try:
        check = model.parse(new_xml)
    except model.BuildError:
        return pasted(False)
    if check.active_spec_index != idx or check.specs != build.specs:
        return pasted(False)
    return dataclasses.replace(build, raw_xml=new_xml, active_spec_index=idx,
                               pasted_xml=base_xml, pasted_spec_index=pob_index,
                               spec_by_level=True, follow_level=lvl)
