"""RUN-LEDGER-CORE: the parse ledger (research 0051 section 'Design: the
parse ledger', finding F-061; drift counter research 0050 R11, test C26).

A pure module: it never opens a file, a socket or Client.txt. The caller
(RUN-LEDGER-WIRE, at Core.feed_line) hands it each tailed line together
with the event parser.parse_line already made of it, and writes
Ledger.dumps() to ops/runtime/logshapes.json at most once a minute while
the separate ledger consent is on.

Four parts:

1. Hit ledger (no content). Each parsed event counts one or more pattern
   ids (pattern_ids below: the event type plus its sub-kind, the class of
   an area id and its act key) with the first and last sighting. Up to
   100 area ids of class "other" are kept verbatim when they are plain
   identifier characters (area ids are engine constants).
2. Shape ledger (masked). A line that made no event, an unknown system
   line, or a trade near-miss whisper is put in a class (classify below).
   Chat-like, speech-like, long and unprefixed lines are only counted;
   tag lines count their tag only; unknown system lines and plain lines
   are stored as a masked shape. A speech-like line is any unparsed,
   untagged body holding a colon anywhere: so a speaker part over 48
   characters or a colon with no space after it can never reach a shape.
3. Class counters (Counters): in-memory counts per class, no content.
   They run under the existing Client.txt consent; parts 1 and 2 run only
   while the ledger consent is on (the caller's check).
4. Drift counter (Drift): prefixed lines that carry a known anchor
   ("Generating level", "[SCENE]", "is now level", "has been slain") but
   match no pattern; DRIFT_NOTE_AT of them in one game run is the caller's
   cue for one Checks note. Counts only.

The mask is an allow-list, never a scrubber. The text is split on white
space (MAX_TOKENS tokens at most). A token survives only when its
lower-case form is an ALLOW word; every other token becomes a placeholder
by form (<n> number, <addr> address or mail, <path> path, <host> host,
<hex> hex run, <w> any other word); equal neighbours collapse. Before
that, the name slots of the known templates (death, suicide, level-up,
join, leave, the AFK / DND autoreply) are place-held, so a character
named like an allow word ("Trade") is stored as <name>, never as "trade".
Every stored token is an allow word, a placeholder or ASCII punctuation;
no raw line text is ever stored. A trade near-miss masks only the whisper
text (never the sender) against TEMPLATE_WORDS, the fixed words of the
three trade templates.

Bounds: MAX_SHAPES shapes (least recently seen goes first, counted in
"evicted"), MAX_TAGS tags, MAX_AREA_IDS area ids, the JSON text under
MAX_BYTES, times kept to the UTC hour. A shape is "ok" (may enter a
report) only after two sightings at least CONFIRM_S seconds apart.
"""

import json
import re
import time

from . import acts, parser

SCHEMA = 1
MAX_SHAPES = 200
MAX_TAGS = 64
MAX_AREA_IDS = 100
MAX_TOKENS = 24
MAX_SHAPE_CHARS = 160
MAX_PUNCT = 3              # kept punctuation characters on each side of a token
LONG_LINE = 512            # longer lines are only counted
MAX_BYTES = 64 * 1024      # dumps() stays under this
CONFIRM_S = 60             # two sightings at least this far apart
DRIFT_NOTE_AT = 3          # anchored misses in one game run

# Function and system words that may survive the mask (about 80; English).
ALLOW = frozenset("""
you your i me my we it its this that there here
a an the to of in on at for from with by into out up as
and or but not no all any some more too many
is are was were be been has have had do does did can can't cannot could
will would should may must
now again already until while after before when then
level area zone instance server party guild trade whisper whispers message
chat channel joined left entered slain committed suicide accepted cancelled
declined afk dnd mode autoreply off player character account online offline
send sent received request invite kicked game logged connected generating
generation seed item items stash reward quest map waypoint hideout town act
failed error unable full found
""".split())

# The fixed words of the three trade whisper templates (parser.TRADE_*),
# the only words a trade near-miss shape may keep.
TEMPLATE_WORDS = frozenset("""
hi i i'd would like to buy your listed for in my stash tab position left top
""".split())

PLACEHOLDERS = frozenset((
    "<n>", "<addr>", "<path>", "<host>", "<hex>", "<w>",
    "<name>", "<class>", "<text>", "<more>"))

PUNCT = frozenset(".,;:!?()[]{}\"'-")

# The two openings of the trade templates (parser.TRADE_*).
TRADE_OPENINGS = ("Hi, I would like to buy your ", "Hi, I'd like to buy your ")

# Chat channel and whisper marks (parser.CHANNELS, @From / @To).
CHAT_MARKS = frozenset("#$%&@")

# Shape kinds as stored.
KIND_SYSTEM = "sys"
KIND_PLAIN = "plain"
KIND_NEAR = "near"

# Line classes (classify).
CLASSES = ("event", "system", "near_miss", "chat_like", "speech_like", "tag",
           "tag_other", "plain", "long", "no_prefix", "blank")

# LIVE-1 items (the LIVE-1-<ITEM> rows) and the pattern ids whose first
# live hit verifies each (RUN-LEDGER-REPORT, AUTO-18).
LIVE1_ITEMS = {
    "DEATH": ("death",),
    "WHISPER": ("whisper_in", "whisper_in.guild"),
    "TRADE": ("trade.priced", "trade.unpriced", "trade.exchange"),
    "PARTY": ("chat.party",),
    "GUILD": ("chat.guild",),
    "AFK": ("afk.on", "afk.off"),
    "JOINED": ("joined", "left"),
    "ACCEPTED": ("trade_accepted",),
    "HIDEOUT": ("area.hideout",),
    "CRUEL": ("area.cruel",),
    "MAP": ("area.map",),
}

# F-082 (Client.txt half, LE-35): every pattern server/al/parser.py marks
# UNVERIFIED, as the ledger pattern id whose first live hit confirms it.
UNVERIFIED = {
    "scene.load": "SCENE (Load Source)",
    "session_connect": "INSTANCE",
    "area_entered": "ENTERED",
    "death": "DEATH (has been slain)",
    "death.suicide": "DEATH (has committed suicide)",
    "dnd.on": "DND",
    "dnd.off": "DND",
    "afk.off": "AFK (OFF form)",
    "joined": "JOINED",
    "left": "LEFT",
    "trade.priced": "TRADE_PRICED",
    "trade.unpriced": "TRADE_UNPRICED",
    "trade.exchange": "TRADE_EXCHANGE",
    "scene.hideout_word": "HIDEOUT_WORD",
}

_TAG = re.compile(r"^\[([^\]\s]{1,32})\]")
_TAG_OK = re.compile(r"^[A-Z][A-Z_]{1,15}$")
_AREA_ID_OK = re.compile(r"^[A-Za-z0-9_]{1,48}$")
_HOUR_OK = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}$")
_PATTERN_OK = re.compile(r"^[a-z_]+(?:\.[A-Za-z0-9_]+)*$")

_NUM = re.compile(r"^[+-]?\d+(?:[.,]\d+)*%?$")
_IPV4 = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?$")
_IPV6 = re.compile(r"^[0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7}$")
_HEX = re.compile(r"^(?:0[xX])?[0-9A-Fa-f]{8,}$")
_HOST = re.compile(r"^[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?::\d+)?$")
_DRIVE = re.compile(r"^[A-Za-z]:")

# Name slots of the known templates (parser.LEVEL_UP, DEATH, JOINED, LEFT,
# AFK, DND), matched on a body of at most LONG_LINE characters.
_SLOTS = (
    (re.compile(r"^.* \([^()]*\) is now level\b"), "<name> (<class>) is now level"),
    (re.compile(r"^.+? is now level\b"), "<name> is now level"),
    (re.compile(r"^.+? has been slain\b"), "<name> has been slain"),
    (re.compile(r"^.+? has committed suicide\b"), "<name> has committed suicide"),
    (re.compile(r"^.+? has joined the area\b"), "<name> has joined the area"),
    (re.compile(r"^.+? has left the area\b"), "<name> has left the area"),
)
_MODE = re.compile(r"^((?:AFK|DND) mode is now (?:ON|OFF)\b\.?)(.*)$")

# Drift anchors (research 0050 R11): body starts, and system-line phrases.
_ANCHOR_STARTS = ("Generating level", "[SCENE]")
_ANCHOR_SYSTEM = (" is now level", " has been slain")


# -- the mask -----------------------------------------------------------

def _form(core):
    """The placeholder for a token core that is not an allowed word."""
    if core in PLACEHOLDERS:
        return core
    if "/" in core or "\\" in core or _DRIVE.match(core):
        return "<path>"
    if "@" in core or _IPV4.match(core) or (":" in core and _IPV6.match(core)):
        return "<addr>"
    if _NUM.match(core):
        return "<n>"
    if _HEX.match(core):
        return "<hex>"
    if _HOST.match(core) and any(c.isalpha() for c in core):
        return "<host>"
    return "<w>"


def _split_punct(tok):
    i, n = 0, len(tok)
    while i < n and tok[i] in PUNCT:
        i += 1
    j = n
    while j > i and tok[j - 1] in PUNCT:
        j -= 1
    return tok[:i], tok[i:j], tok[j:]


def mask_token(tok, allow=ALLOW):
    lead, core, trail = _split_punct(tok)
    if not core:
        return tok[:MAX_PUNCT]
    low = core.lower()
    word = low if low in allow else _form(core)
    return lead[-MAX_PUNCT:] + word + trail[:MAX_PUNCT]


def _slot(text):
    m = _MODE.match(text)
    if m:
        return m.group(1) + (" <text>" if m.group(2).strip() else "")
    for rx, repl in _SLOTS:
        m = rx.match(text)
        if m:
            return repl + text[m.end():]
    return text


def mask(text, allow=ALLOW):
    """The masked shape of one line body (or whisper text)."""
    if allow is ALLOW:
        text = _slot(text)
    tokens = text.split()
    more = len(tokens) > MAX_TOKENS
    out = []
    for tok in tokens[:MAX_TOKENS]:
        t = mask_token(tok, allow)
        if not out or out[-1] != t:
            out.append(t)
    while out and len(" ".join(out)) + (7 if more else 0) > MAX_SHAPE_CHARS:
        out.pop()
        more = True
    if more:
        out.append("<more>")
    return " ".join(out)


def is_safe_token(tok, allow=ALLOW | TEMPLATE_WORDS):
    """True when a stored token is an allowed word, a placeholder or
    ASCII punctuation (the mask's contract)."""
    lead, core, trail = _split_punct(tok)
    if len(lead) > MAX_PUNCT or len(trail) > MAX_PUNCT:
        return False
    if not core:
        return 0 < len(tok) <= MAX_PUNCT
    return core in allow or core in PLACEHOLDERS


def is_safe_shape(shape):
    return (isinstance(shape, str) and 0 < len(shape) <= MAX_SHAPE_CHARS
            and shape.isascii() and all(is_safe_token(t) for t in shape.split(" ")))


# -- classes and pattern ids ---------------------------------------------

def _near_miss(ev):
    if ev.get("trade"):
        return None
    text = ev.get("text")
    if isinstance(text, str) and text.startswith(TRADE_OPENINGS):
        return text
    return None


def classify(line, ev):
    """(class, detail) for one tailed line and the event parse_line made of
    it (None for no event). detail is the text to mask for "system",
    "plain" and "near_miss", the tag for "tag", else None."""
    if ev is not None:
        t = ev.get("type")
        if t == "unknown_system_line":
            body = ev.get("body") or ""
            return ("long", None) if len(body) > LONG_LINE else ("system", body)
        if t == "whisper_in":
            text = _near_miss(ev)
            if text is not None:
                return ("long", None) if len(text) > LONG_LINE else ("near_miss", text)
        return "event", None
    text = line.rstrip("\r\n")
    if not text.strip():
        return "blank", None
    if len(text) > LONG_LINE:
        return "long", None
    m = parser.PREFIX.match(text)
    if not m:
        return "no_prefix", None
    body = m.group(9)
    if body[:1] in CHAT_MARKS:
        return "chat_like", None
    tm = _TAG.match(body)
    if tm:
        tag = tm.group(1)
        return ("tag", tag) if _TAG_OK.match(tag) else ("tag_other", None)
    if ":" in body:
        return "speech_like", None
    return "plain", body


def area_class(area_id):
    """campaign, cruel, interlude, map, hideout or other."""
    if parser.is_hideout_area(area_id):
        return "hideout"
    if acts.is_endgame(area_id):
        return "map"
    act = acts.act_of(area_id)
    if act:
        return {"G": "campaign", "C": "cruel", "P": "interlude"}[act["key"][0]]
    return "other"


def _scene_ids(ev):
    ids = ["scene.load" if ev.get("scene_op") == "load" else "scene.set"]
    if ev.get("is_null"):
        ids.append("scene.null")
    elif ev.get("scene") is None:
        ids.append("scene.unknown")
    elif ev.get("is_transient"):
        ids.append("scene.act")
    elif ev.get("is_hideout"):
        ids.append("scene.hideout_word")
    else:
        ids.append("scene.zone")
    return ids


def pattern_ids(ev):
    """The hit-ledger pattern ids of one event (no content)."""
    t = ev.get("type")
    if t == "scene_changed":
        return _scene_ids(ev)
    if t == "area_generated":
        aid = ev.get("area_id")
        ids = ["area." + area_class(aid)]
        act = acts.act_of(aid)
        if act:
            ids.append("area.act." + act["key"])
        return ids
    if t == "death":
        return ["death.suicide" if ev.get("suicide") else "death"]
    if t in ("afk_changed", "dnd_changed"):
        return [t[:3] + (".on" if ev.get("on") else ".off")]
    if t == "chat":
        ch = ev.get("channel")
        return ["chat." + ch if ch in parser.CHANNELS.values() else "chat.other"]
    if t == "whisper_in":
        ids = ["whisper_in.guild" if ev.get("guild_tag") else "whisper_in"]
        tr = ev.get("trade")
        if tr:
            kind = tr.get("template")
            ids.append("trade." + (kind if kind in parser.TRADE_TEMPLATES else "other"))
        return ids
    return [_SIMPLE.get(t, "other")]


_SIMPLE = {
    "log_opened": "log_opened", "level_up": "level_up",
    "area_entered": "area_entered", "player_joined_area": "joined",
    "player_left_area": "left", "trade_accepted": "trade_accepted",
    "trade_cancelled": "trade_cancelled", "unknown_system_line": "system.unknown",
    "whisper_out": "whisper_out", "session_connect": "session_connect",
}


# -- in-memory parts (existing consent) ----------------------------------

class Counters:
    """Per-class line counts, in memory only (no content)."""

    def __init__(self):
        self.counts = dict.fromkeys(CLASSES, 0)

    def observe(self, line, ev, split=None):
        cls = (split or classify(line, ev))[0]
        self.counts[cls] += 1
        return cls

    def snapshot(self):
        return dict(self.counts)


class Drift:
    """Anchored lines that match no pattern (research 0050 R11, C26).

    `run` counts since the last game start (log_opened), `total` since
    construction; `due` is True once DRIFT_NOTE_AT misses fell in one run.
    Only system lines carry the phrase anchors, so chat cannot trip it."""

    def __init__(self):
        self.run = 0
        self.total = 0

    @property
    def due(self):
        return self.run >= DRIFT_NOTE_AT

    def observe(self, line, ev):
        """True when this line is an anchored miss."""
        if ev is not None:
            t = ev.get("type")
            if t == "log_opened":
                self.run = 0
                return False
            if t != "unknown_system_line":
                return False
            body = ": " + (ev.get("body") or "")
        else:
            if len(line) > parser.MAX_LINE_CHARS + 2:
                return False
            m = parser.PREFIX.match(line.rstrip("\r\n"))
            if not m:
                return False
            body = m.group(9)
        if not is_anchored(body):
            return False
        self.run += 1
        self.total += 1
        return True


def is_anchored(body):
    if body.startswith(_ANCHOR_STARTS):
        return True
    return body.startswith(": ") and any(a in body for a in _ANCHOR_SYSTEM)


# -- the persisted ledger (ledger consent) -------------------------------

def hour_of(now):
    return time.strftime("%Y-%m-%dT%H", time.gmtime(now))


class Ledger:
    """Hit ledger plus masked shape ledger; to_dict() / dumps() give the
    file content, from_dict() takes it back (re-checked token by token).

    `dirty` is set when a key is new, a sighting moves an hour stamp, a
    shape is confirmed or evicted; bare count increments ride along with
    the next such write. The writer clears it after a write."""

    def __init__(self):
        self.hits = {}          # pattern id -> [n, first, last]
        self.area_ids = {}      # area id of class other -> [n, first, last]
        self.area_ids_dropped = 0
        self.tags = {}          # tag -> n
        self.tags_dropped = 0
        self.counts = dict.fromkeys(CLASSES, 0)
        self.shapes = {}        # (kind, shape) -> [n, first, last, ok]; LRU order
        self.evicted = 0
        self.dirty = False
        self._first_s = {}      # (kind, shape) -> exact first sighting (memory)
        self._h = None
        self._htxt = ""

    def _hour(self, now):
        h = int(now // 3600)
        if h != self._h:
            self._h = h
            self._htxt = hour_of(h * 3600)
        return self._htxt

    def _count(self, table, key, hour):
        rec = table.get(key)
        if rec is None:
            table[key] = [1, hour, hour]
            self.dirty = True
            return
        rec[0] += 1
        if rec[2] != hour:
            rec[2] = hour
            self.dirty = True

    def observe(self, line, ev, now=None, split=None):
        """Record one tailed line; returns its class."""
        if now is None:
            now = time.time()
        cls, detail = split or classify(line, ev)
        hour = self._hour(now)
        if ev is not None:
            for pid in pattern_ids(ev):
                self._count(self.hits, pid, hour)
            if ev.get("type") == "area_generated":
                self._area_id(ev.get("area_id"), hour)
        self.counts[cls] += 1
        if cls == "tag":
            self._tag(detail)
        elif cls == "system":
            self._shape(KIND_SYSTEM, mask(detail), hour, now)
        elif cls == "plain":
            self._shape(KIND_PLAIN, mask(detail), hour, now)
        elif cls == "near_miss":
            self._shape(KIND_NEAR, mask(detail, TEMPLATE_WORDS), hour, now)
        return cls

    def _area_id(self, aid, hour):
        if area_class(aid) != "other":
            return
        if not isinstance(aid, str) or not _AREA_ID_OK.match(aid):
            self.area_ids_dropped += 1
            return
        if aid not in self.area_ids and len(self.area_ids) >= MAX_AREA_IDS:
            self.area_ids_dropped += 1
            return
        self._count(self.area_ids, aid, hour)

    def _tag(self, tag):
        n = self.tags.get(tag)
        if n is None:
            if len(self.tags) >= MAX_TAGS:
                self.tags_dropped += 1
                return
            self.dirty = True
            n = 0
        self.tags[tag] = n + 1

    def _shape(self, kind, shape, hour, now):
        if not shape:
            return
        key = (kind, shape)
        rec = self.shapes.pop(key, None)
        if rec is None:
            while len(self.shapes) >= MAX_SHAPES:
                self._evict()
            rec = [0, hour, hour, False]
            self._first_s[key] = now
            self.dirty = True
        rec[0] += 1
        if rec[2] != hour:
            rec[2] = hour
            self.dirty = True
        if not rec[3]:
            first = self._first_s.get(key)
            if first is None:  # loaded from a file: re-arm in this run
                self._first_s[key] = now
            elif now - first >= CONFIRM_S:
                rec[3] = True
                self.dirty = True
        self.shapes[key] = rec

    def _evict(self):
        key = next(iter(self.shapes))
        del self.shapes[key]
        self._first_s.pop(key, None)
        self.evicted += 1
        self.dirty = True

    def confirmed(self):
        """[(kind, shape)] that passed the two-sighting rule."""
        return [k for k, r in self.shapes.items() if r[3]]

    def to_dict(self):
        return {
            "schema": SCHEMA,
            "hits": {k: list(v) for k, v in self.hits.items()},
            "area_ids": {k: list(v) for k, v in self.area_ids.items()},
            "area_ids_dropped": self.area_ids_dropped,
            "tags": dict(self.tags),
            "tags_dropped": self.tags_dropped,
            "counts": dict(self.counts),
            "shapes": [[k[0], k[1]] + r for k, r in self.shapes.items()],
            "evicted": self.evicted,
        }

    def dumps(self):
        """The file text: ASCII JSON under MAX_BYTES (least recently seen
        shapes are evicted until it fits)."""
        while True:
            text = json.dumps(self.to_dict(), separators=(",", ":"))
            if len(text) < MAX_BYTES or not self.shapes:
                return text
            self._evict()

    @classmethod
    def from_dict(cls, data):
        """A ledger from file content; anything malformed or unsafe is
        dropped, so a tampered file cannot carry raw text back in."""
        led = cls()
        if not isinstance(data, dict) or data.get("schema") != SCHEMA:
            return led

        def rec3(v):
            return (isinstance(v, list) and len(v) == 3 and _count_ok(v[0])
                    and all(isinstance(h, str) and _HOUR_OK.match(h) for h in v[1:]))

        for k, v in _items(data.get("hits")):
            if _PATTERN_OK.match(k) and rec3(v):
                led.hits[k] = list(v)
        for k, v in _items(data.get("area_ids")):
            if len(led.area_ids) < MAX_AREA_IDS and _AREA_ID_OK.match(k) and rec3(v):
                led.area_ids[k] = list(v)
        for k, v in _items(data.get("tags")):
            if len(led.tags) < MAX_TAGS and _TAG_OK.match(k) and _count_ok(v):
                led.tags[k] = v
        for k, v in _items(data.get("counts")):
            if k in led.counts and _count_ok(v):
                led.counts[k] = v
        for name in ("area_ids_dropped", "tags_dropped", "evicted"):
            if _count_ok(data.get(name)):
                setattr(led, name, data[name])
        shapes = data.get("shapes")
        for row in shapes if isinstance(shapes, list) else ():
            if (isinstance(row, list) and len(row) == 6
                    and row[0] in (KIND_SYSTEM, KIND_PLAIN, KIND_NEAR)
                    and is_safe_shape(row[1]) and rec3(row[2:5])
                    and isinstance(row[5], bool)):
                if len(led.shapes) >= MAX_SHAPES:
                    led.shapes.pop(next(iter(led.shapes)))
                led.shapes[(row[0], row[1])] = list(row[2:])
        return led


def _items(d):
    return [(k, v) for k, v in d.items() if isinstance(k, str)] if isinstance(d, dict) else []


def _count_ok(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0
