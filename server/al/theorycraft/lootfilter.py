"""UTIL-FILTER: an AshLight-original `ashlight.filter` snippet.

A pure function: the loaded Path of Building build in, filter text out
(decision 0031, adjudicator ruling in research 0022 section 3). The
dashboard offers it as a download on the player's click; the player saves
it into their own filter folder and adds `Import "ashlight.filter"
Optional` to their main filter. AshLight never writes into the game's
documents folder or any game folder: this module writes no file at all,
and the core only returns the text in an HTTP answer.

The text uses GGG's documented filter syntax only (Show blocks with
conditions and actions, `#` comments). It highlights the item bases the
build wears, so a better roll of the same base stands out on the ground.
Nothing from another filter is copied.

Checked against GGG's filter reference (pathofexile.com/item-filter/about,
read 2026-11-17, research 0025; PoE2 uses the same grammar): SetFontSize
1-45, colours 0-255 per channel, PlayEffect / MinimapIcon colour and shape
words, `Import "<file>" Optional`. A Show block without `Continue` stops
matching for the items it catches, so the Import goes near the top. When
the build-time base list is cached (decision 0009) a base name the game
data does not know is left out: such a BaseType value would make the
player's filter fail to load.

UTIL-FILTER-2 (decision 0032): value tiers for uniques and stackables from
the cached poe.ninja prices (ninja.RatesClient.filter_prices: no new
request, web data on only), in Divine Orbs. Conservative: a unique base is
tiered by the CHEAPEST well-listed unique on it (the filter cannot tell
uniques of one base apart), thin markets are left out, and a name the
filter grammar cannot carry as it is is left out rather than changed.
Tiers: top (TOP_DIVINE and up: big text, red beam, star icon), worth
picking up (PICK_DIVINE and up: larger text, white beam), and everything
else gets no block at all, so the player's own filter decides. AshLight
never writes a Hide block.

UTIL-FILTER-MERGE (decision 0033): merge() prepends the same Show blocks,
between two marker comment lines, to a filter the player picked in the
browser. The player's bytes after the section are byte-identical (CRLF and
a leading UTF-8 BOM kept); the only part of their file read beyond the
text checks is an AshLight section from an earlier merge at the very
start, which is replaced. Bytes in, bytes out, in memory: no file, no path.

TC-FILTER-ONE-CONTROL (F-158): the header of the file and of the merged
section carries the day it was made and the league of the prices in it
(the `league` key of filter_prices), so a stale copy shows as stale.
`today` is injected in tests; the core passes nothing and gets today.
"""

import datetime
import re

FILE_NAME = "ashlight.filter"
IMPORT_LINE = f'Import "{FILE_NAME}" Optional'
MAX_BASES = 40
_SAFE = re.compile(r"[^A-Za-z0-9 ',-]")
MAX_TIER_NAMES = 200
TOP_DIVINE = 1.0  # worth a Divine Orb or more
PICK_DIVINE = 0.05  # a twentieth of a Divine Orb or more
TIER_KEYS = ("unique_top", "unique_pick", "stack_top", "stack_pick")
NOTICE = "This product isn't affiliated with or endorsed by Grinding Gear Games in any way."


def _clean(name):
    return " ".join(_SAFE.sub(" ", str(name or "")).split())


def bases(build):
    """The base names the build wears (rare, normal or unique gear; flasks
    and charms out; a magic item's line holds affixes, so it is out too)."""
    out = []
    gear = getattr(build, "gear", None)
    for slot, item in (gear.items() if isinstance(gear, dict) else ()):
        if str(slot).lower().startswith(("flask", "charm")):
            continue
        if (getattr(item, "rarity", None) or "").upper() not in ("RARE", "NORMAL", "UNIQUE"):
            continue
        name = _clean(getattr(item, "base", None))
        if name and name not in out:
            out.append(name)
    return out[:MAX_BASES]


def known(names, base_names):
    """(kept, dropped): the names found in `base_names` ({lower: name},
    basetypes.NamesCache) in the game's spelling; all kept when no list."""
    if not isinstance(base_names, dict) or not base_names:
        return list(names), []
    kept, dropped = [], []
    for n in names:
        real = base_names.get(n.lower())
        if isinstance(real, str) and _clean(real) == real:
            if real not in kept:
                kept.append(real)
        else:
            dropped.append(n)
    return kept, dropped


def tiers(prices, base_names=None):
    """{"unique_top", "unique_pick", "stack_top", "stack_pick": [names]}
    from filter_prices() (values in Divine Orbs); empty lists for None.
    `base_names` (the cached base_items list) checks every tier: it holds
    stackables too (currency, omens, soul cores; AREA-AUDIT P4-2), and a
    BaseType the game does not know makes the whole filter fail to load."""
    out = {k: [] for k in TIER_KEYS}
    if not isinstance(prices, dict):
        return out
    for kind, field in (("unique", "base"), ("stack", "name")):
        rows = prices.get("uniques" if kind == "unique" else "stackables")
        for row in rows if isinstance(rows, list) else ():
            if not isinstance(row, dict):
                continue
            name, value = row.get(field), row.get("value")
            if not isinstance(name, str) or _clean(name) != name or not name \
                    or isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            key = (f"{kind}_top" if value >= TOP_DIVINE
                   else f"{kind}_pick" if value >= PICK_DIVINE else None)
            if key and name not in out[key]:
                out[key].append(name)
    for k in TIER_KEYS:
        out[k] = known(out[k], base_names)[0]
    for k in TIER_KEYS:
        out[k] = sorted(out[k])[:MAX_TIER_NAMES]
    return out


MAX_LEAGUE = 60


def stamp(prices=None, today=None):
    """The one header line: the day the text was made and, when the
    prices name it, their league ("# Made on 2026-11-18 for the Standard
    league."). The league is cut to the filter-safe letters so it can
    never leave its comment line."""
    if not isinstance(today, datetime.date):
        today = datetime.date.today()
    day = f"{today.year:04d}-{today.month:02d}-{today.day:02d}"
    league = prices.get("league") if isinstance(prices, dict) else None
    league = _clean(league)[:MAX_LEAGUE].strip() if isinstance(league, str) else ""
    if league:
        return f"# Made on {day} for the {league} league."
    return f"# Made on {day}."


def _quoted(names):
    return " ".join(f'"{n}"' for n in names)


def _tier_lines(t):
    if not any(t.values()):
        return []
    lines = [f"# Value tiers from poe.ninja prices: {TOP_DIVINE:g} Divine Orb or more, and",
             f"# {PICK_DIVINE:g} Divine Orb or more. Nothing is hidden: cheaper items keep",
             "# the look your own filter gives them."]
    blocks = (("stack_top", None, 45, "255 60 60", "Red", "0 Red Star"),
              ("unique_top", "Unique", 45, "255 60 60", "Red", "0 Red Star"),
              ("stack_pick", None, 40, "255 255 255", "White", "1 White Circle"),
              ("unique_pick", "Unique", 40, "255 255 255", "White", "1 White Circle"))
    for key, rarity, size, colour, effect, icon in blocks:
        if not t[key]:
            continue
        lines.append("Show")
        if rarity:
            lines.append("    Rarity " + rarity)
        lines += ["    BaseType == " + _quoted(t[key]),
                  f"    SetFontSize {size}",
                  "    SetBorderColor " + colour,
                  "    PlayEffect " + effect,
                  "    MinimapIcon " + icon,
                  ""]
    return lines


def generate(build, base_names=None, prices=None, today=None):
    """The filter text (ASCII, LF). With no build, no bases and no prices it
    is a valid filter made of comments only, so an Import of it changes
    nothing. `base_names` (optional, the cached snapshot base list) drops
    names the game data does not know. `prices` (optional,
    ninja.RatesClient.filter_prices) adds the value tiers first. `today`
    (a date, tests only) is the day in the header line."""
    lines = ["# ashlight.filter - made by AshLight from your loaded build.",
             stamp(prices, today),
             "# " + NOTICE,
             "# Save this file in your item filter folder, then add this line",
             "# near the top of your own filter:",
             "#   " + IMPORT_LINE,
             ""]
    return "\n".join(lines + _body_lines(build, base_names, prices)) + "\n"


def _body_lines(build, base_names=None, prices=None):
    """The tier and build blocks with their comments, one string per line,
    no trailing blank line."""
    lines = _tier_lines(tiers(prices, base_names))
    names, dropped = known(bases(build) if build is not None else [], base_names)
    if dropped:
        n = len(dropped)
        lines.append(f"# Left out {n} item base{'s' if n != 1 else ''} that the game data "
                     "does not list.")
    if not names:
        lines += ["# No build loaded, or no gear in it.",
                  "# Load a build in AshLight, then download this again."]
        return lines
    who = " ".join(str(x) for x in (getattr(build, "class_name", None),
                                     getattr(build, "ascendancy", None)) if x)
    if who:
        lines.append("# Build: " + _clean(who))
    lines += ["# Rare items of the bases your build wears show larger:",
              "# check them for an upgrade.",
              "Show",
              "    Rarity Rare",
              "    BaseType == " + " ".join(f'"{n}"' for n in names),
              "    SetFontSize 40",
              "    SetBorderColor 255 190 60",
              "    PlayEffect Yellow",
              "    MinimapIcon 1 Yellow Diamond"]
    return lines


# -- UTIL-FILTER-MERGE (decision 0033)
MAX_MERGE_BYTES = 2 * 1024 * 1024
MERGE_BEGIN = "# ===== AshLight section start ====="
MERGE_END = "# ===== AshLight section end ====="
_BOM = b"\xef\xbb\xbf"
# C0 controls other than tab, LF and CR, and DEL: not in a text filter
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_NAME_SAFE = re.compile(r"[^A-Za-z0-9 ._()-]")
MAX_NAME = 80
REFUSED_TEXT = {
    "empty": "That file is empty. Pick your own .filter file.",
    "too_big": "That file is over 2 MB, so it is not a loot filter. Pick your own .filter file.",
    "not_utf8": "That file is not plain text. Save it as UTF-8 in your editor, then pick "
                "it again.",
    "not_text": "That file has characters a loot filter can't hold. Pick your own .filter "
                "file.",
    # AREA-AUDIT P5-5: a hand-edited file kept the start line but lost the end
    # line; stripping to the end of the file would delete the player's filter
    "no_end": "That filter has the AshLight start line but no end line, so AshLight "
              "can't tell where its part stops. Pick your original filter, or delete "
              "the AshLight lines at the top and pick it again.",
}


class MergeRefused(ValueError):
    """The upload is not a text filter; `reason` is a REFUSED_TEXT key."""

    def __init__(self, reason):
        super().__init__(REFUSED_TEXT[reason])
        self.reason = reason


def check_text(data):
    """The upload without its BOM, after the size and text checks; raises
    MergeRefused. Never echoes the content."""
    if not isinstance(data, (bytes, bytearray)):
        raise MergeRefused("not_text")
    if len(data) > MAX_MERGE_BYTES:
        raise MergeRefused("too_big")
    body = bytes(data[len(_BOM):] if data.startswith(_BOM) else data)
    if not body:
        raise MergeRefused("empty")
    if b"\x00" in body:
        raise MergeRefused("not_utf8" if body[:2] in (b"\xff\xfe", b"\xfe\xff")
                           else "not_text")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise MergeRefused("not_utf8") from None
    if _CONTROL.search(text):
        raise MergeRefused("not_text")
    return body


def _strip_old_section(body):
    """An AshLight section from an earlier merge, at the very start only,
    is AshLight's own text: drop it (through the end marker's line)."""
    begin, end = MERGE_BEGIN.encode("ascii"), MERGE_END.encode("ascii")
    if not body.startswith(begin):
        return body
    i = body.find(b"\n" + end)
    if i < 0:
        raise MergeRefused("no_end")  # AREA-AUDIT P5-5: never stack a second one
    j = body.find(b"\n", i + 1 + len(end))
    return b"" if j < 0 else body[j + 1:]


def merge(data, build, base_names=None, prices=None, today=None):
    """The player's filter bytes with AshLight's Show blocks prepended in a
    marked section. A leading BOM stays first; the section uses CRLF when
    the file does; everything after it is the player's bytes unchanged.
    The section's second line is stamp(): the day and the prices' league."""
    body = _strip_old_section(check_text(data))
    bom = _BOM if data.startswith(_BOM) else b""
    nl = "\r\n" if b"\r\n" in body else "\n"
    lines = [MERGE_BEGIN,
             stamp(prices, today),
             "# Added by AshLight: Show blocks only, nothing is hidden. Your own",
             "# filter follows the end line below, unchanged. To undo, delete",
             "# everything from the start line to the end line.",
             "# " + NOTICE,
             ""]
    lines += _body_lines(build, base_names, prices)
    lines += ["", MERGE_END, ""]
    return bom + nl.join(lines).encode("ascii") + body


def out_name(name):
    """The download name: the picked file's own name (no folders; ASCII
    letters, digits, space . _ ( ) - only) plus "-ashlight.filter"."""
    base = str(name or "").replace("\\", "/").rsplit("/", 1)[-1]
    if base.lower().endswith(".filter"):
        base = base[:-len(".filter")]
    if base.lower().endswith("-ashlight"):
        base = base[:-len("-ashlight")]
    base = " ".join(_NAME_SAFE.sub("", base).split()).strip(" .")[:MAX_NAME].strip(" .")
    return (base or "filter") + "-ashlight.filter"
