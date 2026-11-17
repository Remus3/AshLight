"""LANG-GUARD (research 0032 section 4, ruling K, decision 0040): notice a
non-English game client from Client.txt alone and say plainly which
features need the English game text. Never guess-translates a line.

PoE2 never writes `You have entered <zone>` (research 0002, live log), so
the row's first signal is replaced by two (decision 0040):

- a "comparable load": an `area_generated` id that the build-time English
  zone table knows (decision 0020), then the next real `[SCENE]` name. The
  English name -> English evidence; another name -> one strike.
- a system line (": " body, never chat, whisper or NPC text): one AshLight
  matched in English (level-up, death, AFK / DND, joined / left, trade
  accepted / cancelled) -> English evidence; an unmatched one holding a
  non-ASCII letter -> one strike.

STRIKES strikes in a row with no English evidence between them show the
notice; English evidence clears it and resets the count. The counter lives
in memory only (ruling K); the notice never says the client is broken.
"""

STRIKES = 3

ENGLISH, NON_ENGLISH, UNKNOWN = "english", "non_english", "unknown"

# The one wording (ruling K: AshLight-authored, never "broken"); item.py's
# non-English item warning and the DIAG-SELF check reuse it.
NEEDS = "level, deaths, whispers, trade requests and the item check"
WORKS = "zone, act and map times"
NOTICE = ("Your game seems to use a language other than English. AshLight reads "
          "only the English game text. " + NEEDS[0].upper() + NEEDS[1:]
          + " stay empty. " + WORKS[0].upper() + WORKS[1:] + " still work.")
ITEM_HINT = "Item check reads only the English game text."

ENGLISH_EVENTS = frozenset(("level_up", "death", "afk_changed", "dnd_changed",
                            "player_joined_area", "player_left_area",
                            "trade_accepted", "trade_cancelled"))


def _foreign_letters(text):
    """True when `text` holds a letter outside ASCII (Cyrillic, Hangul,
    kana, Thai, accented Latin)."""
    return isinstance(text, str) and any(ord(c) > 127 and c.isalpha() for c in text)


def english_names(table):
    """{area id: lower-case English name} from an acts.load_table() table."""
    out = {}
    for rows in (table or {}).values():
        for r in rows or ():
            if isinstance(r, dict) and isinstance(r.get("id"), str) \
                    and isinstance(r.get("name"), str) and r["name"].strip():
                out[r["id"]] = r["name"].strip().lower()
    return out


class LangGuard:
    def __init__(self):
        self.names = {}
        self.strikes = 0
        self.evidence = False  # any English evidence seen
        self.notice = False
        self.since = None
        self._pending = None  # the English name the next real scene should carry

    def set_table(self, table):
        self.names = english_names(table)

    def _strike(self, now):
        self.strikes += 1
        if self.strikes >= STRIKES and not self.notice:
            self.notice = True
            self.since = now
            return True
        return False

    def _english(self):
        changed = self.notice or not self.evidence
        self.strikes = 0
        self.evidence = True
        self.notice = False
        self.since = None
        return changed

    def feed(self, ev, now=None):
        """Fold one parsed event in; True when the verdict changed."""
        t = ev.get("type")
        if t == "area_generated":
            self._pending = self.names.get(ev.get("area_id"))
            return False
        if t == "scene_changed":
            if ev.get("is_null") or ev.get("is_transient") or not ev.get("scene"):
                return False
            want, self._pending = self._pending, None
            if want is None:
                return False
            if ev["scene"].strip().lower() == want:
                return self._english()
            return self._strike(now)
        if t in ENGLISH_EVENTS:
            return self._english()
        if t == "unknown_system_line" and _foreign_letters(ev.get("body")):
            return self._strike(now)
        return False

    def verdict(self):
        if self.notice:
            return NON_ENGLISH
        return ENGLISH if self.evidence else UNKNOWN

    def view(self):
        v = self.verdict()
        return {"verdict": v, "since": self.since,
                "text": NOTICE if v == NON_ENGLISH else None,
                "needs": NEEDS, "works": WORKS}
