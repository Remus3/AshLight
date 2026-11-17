"""TEST-E2E: a realistic synthetic Path of Exile 2 Client.txt generator.

Stdlib only, deterministic from a seed. Line shapes follow the verified live
fixture (tests/fixtures/client_live_shapes.txt, research 0002 section 7) and
the sample fixture (tests/fixtures/client_sample.txt). Used by
tests/test_e2e_replay.py to drive a running core end to end; also a CLI:

    python tools/synth_client.py OUT [--seed N] [--pad-mb M]

writes one generated session to OUT (optionally padded at the front with
engine noise to about M MB, for resume-cap checks). No game data, no network.
"""

import argparse
import random
import sys
from pathlib import Path

CRLF = "\r\n"
MARKER = "***** LOG FILE OPENING *****"
ZONES = [("G1_1", 1, "The Riverbank"), ("G1_town", 15, "Clearfell Encampment"),
         ("G1_2", 2, "Clearfell"), ("G1_3", 3, "Mud Burrow"), ("G1_4", 4, "The Grelwood")]
NOISE = "[ENGINE] synthetic engine noise line"


class Session:
    """Builds Client.txt lines with a running clock and the game's prefix
    `YYYY/MM/DD HH:MM:SS <ms> <hash> [LEVEL Client <pid>] <body>`."""

    def __init__(self, seed=1, character="Cinderwisp", klass="Sorceress", pid=5150,
                 start=(2026, 11, 16, 21, 0, 0)):
        self.rng = random.Random(seed)
        self.character = character
        self.klass = klass
        self.pid = pid
        y, mo, d, h, mi, s = start
        self._date = (y, mo, d)
        self._t = h * 3600 + mi * 60 + s
        self._ms = 1000
        self._hash = "1f2e3d4c"
        self.level = 1
        self.deaths = 0
        self.whispers_in = 0
        self.trade_requests = 0
        self.zone = None
        self.area_id = None
        self.lines = []

    # -- prefix
    def _stamp(self, step=1):
        self._t += step
        self._ms += step * 1000 + self.rng.randrange(0, 900)
        h, rem = divmod(self._t % 86400, 3600)
        mi, s = divmod(rem, 60)
        y, mo, d = self._date
        return f"{y:04d}/{mo:02d}/{d:02d} {h:02d}:{mi:02d}:{s:02d} {self._ms}"

    def raw(self, body, level="INFO", step=1):
        line = f"{self._stamp(step)} {self._hash} [{level} Client {self.pid}] {body}"
        self.lines.append(line)
        return line

    def marker(self):
        line = f"{self._stamp()} {MARKER}"
        self.lines.append(line)
        return line

    # -- events
    def zone_change(self, area_id, area_level, name):
        self.raw(f"Connecting to instance server at 192.0.2.{self.rng.randrange(2, 250)}:21360")
        self._hash = f"{self.rng.getrandbits(32):08x}"
        self.raw(f'Generating level {area_level} area "{area_id}" with seed '
                 f"{self.rng.randrange(1, 10 ** 9)}", level="DEBUG")
        self.raw("[SCENE] Set Source [(null)]")
        self.raw(f"[SCENE] Set Source [{name}]")
        self.zone, self.area_id = name, area_id

    def level_up(self):
        self.level += 1
        self.raw(f": {self.character} ({self.klass}) is now level {self.level}")

    def death(self):
        self.deaths += 1
        self.raw(f": {self.character} has been slain.")

    def whisper(self, who, text, guild=None):
        self.whispers_in += 1
        tag = f"<{guild}> " if guild else ""
        self.raw(f"@From {tag}{who}: {text}")

    def trade_whisper(self, who, item, amount, currency, league="Standard"):
        self.trade_requests += 1
        self.whisper(who, f"Hi, I would like to buy your {item} listed for {amount} "
                          f"{currency} in {league} (stash tab \"Sale\"; position: left "
                          f"{self.rng.randrange(1, 12)}, top {self.rng.randrange(1, 12)})")

    def trade_accepted(self):
        self.raw(": Trade accepted.")

    def chat(self, channel, who, text):
        self.raw(f"{channel}{who}: {text}")

    def noise(self, n=1):
        for _ in range(n):
            self.raw(NOISE, step=0)

    def text(self):
        return "".join(line + CRLF for line in self.lines)


def standard_session(seed=1, character="Cinderwisp", klass="Sorceress"):
    """One leveling session: marker, zones, level-ups, deaths, whispers
    (non-ASCII names included), a trade request and its acceptance, chat and
    engine noise. Returns the Session (its counters are the expected state)."""
    s = Session(seed=seed, character=character, klass=klass)
    s.marker()
    s.raw("[WINDOW] Gained focus")
    for area_id, lvl, name in ZONES[:3]:
        s.zone_change(area_id, lvl, name)
        s.noise(3)
        s.level_up()
        s.chat("#", "Chatterbox", "anyone know a good leveling build")
    s.death()
    s.whisper("Ma\u00eblle", "salut, tu vends l'anneau ?")
    s.whisper("\u30b5\u30af\u30e9", "hello")
    s.trade_whisper("Tradewind", "Grim Bane Ruby Ring", 5, "exalted")
    s.trade_accepted()
    s.zone_change(*ZONES[3])
    s.level_up()
    s.death()
    return s


def play(s, minutes, rng=None):
    """TEST-SOAK: append about `minutes` of simulated play to Session s, in
    five-minute rounds of game time (zone change, engine noise, chat, and by
    chance a level-up (capped at 100), a death, a whisper, a trade request
    and its outcome, a party member, a game restart marker). Returns the
    number of lines added. Deterministic from the session's seed."""
    rng = rng or s.rng
    start = len(s.lines)
    for _ in range(max(1, int(minutes // 5))):
        s.zone_change(*rng.choice(ZONES))
        s.noise(rng.randrange(1, 6))
        s.chat(rng.choice("#$%&"), f"Player{rng.randrange(1000)}", "wts some stuff")
        if s.level < 100 and rng.random() < 0.3:
            s.level_up()
        if rng.random() < 0.15:
            s.death()
        if rng.random() < 0.3:
            s.whisper(f"Friend{rng.randrange(50)}", "\u00e7a va ? " * rng.randrange(1, 4))
        if rng.random() < 0.25:
            s.trade_whisper(f"Buyer{rng.randrange(500)}", "Grim Bane Ruby Ring",
                            rng.randrange(1, 50), "exalted")
            s.raw(rng.choice([": Trade accepted.", ": Trade cancelled."]), step=20)
        if rng.random() < 0.1:
            s.raw(f": Ally{rng.randrange(9)} has joined the area.")
        if rng.random() < 0.02:
            s.marker()
        s.raw("[WINDOW] Gained focus", step=300 - 10)  # the rest of the round
    return len(s.lines) - start


def pad_noise(size, line=None):
    """Bytes of engine noise lines totalling at least size bytes."""
    one = ((line or "2026/11/16 20:00:01 1100 1a2b3c4d [INFO Client 4242] " + NOISE)
           + CRLF).encode("ascii")
    return one * (size // len(one) + 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--pad-mb", type=float, default=0.0)
    args = ap.parse_args(argv)
    s = standard_session(args.seed)
    with open(args.out, "wb") as fh:
        if args.pad_mb > 0:
            fh.write(pad_noise(int(args.pad_mb * 1024 * 1024)))
        fh.write(s.text().encode("utf-8"))
    print(f"wrote {Path(args.out).name}: {len(s.lines)} session lines, level {s.level}, "
          f"deaths {s.deaths}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
