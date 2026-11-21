"""TC-PRESS-SAMPLES: list, check and promote item-press fixture candidates.

The candidates are the sanitized item texts the dev-host switch
"dev_press_samples" (gitignored config/local.json, decision 0045
amendment 2026-11-18) saves under <sidecar>/Scratch/press-samples/
(server/al/theorycraft/cardparts/sample.py).

    press_samples.py list    [--folder DIR]
    press_samples.py check   [--folder DIR]
    press_samples.py promote NAME [--folder DIR] [--dest DIR]

list: one line per candidate (name, lines, characters) and the count
against the cap. check: one line per candidate, "ok" or the mask patterns
it still matches; exit 1 when any candidate leaks. promote: after the
developer has read the candidate, writes its REWRITTEN form to
tests/fixtures/press_samples/<NAME>.txt (or --dest): the item name and base
type lines become invented names, every word of the other lines that is
not on the structural word list (property keys, rarity, mod markers,
price form) becomes an invented word of the same case, numbers and
punctuation stay, so the fixture keeps the shape and never the text.
promote refuses a candidate that still matches a mask pattern, a rewrite
that would equal the candidate (a verbatim copy, decision 0009), a
rewrite that leaks, and an existing fixture file. Non-ASCII characters
become ASCII (an em dash a hyphen). No request, no clipboard, no game
file; stdlib only.
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al.theorycraft.cardparts import sample  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "press_samples"
SEPARATOR = "--------"
_NAME = re.compile(r"^[0-9A-Za-z_-]{1,64}$")
_WORD = re.compile(r"[A-Za-z]+")
# Words a fixture keeps: item text structure, never item or mod names.
STRUCTURAL = frozenset(w.lower() for w in """
Item Class Rarity Normal Magic Rare Unique Currency Gem Quality Requirements
Requires Level Str Dex Int Sockets Corrupted Unidentified Mirrored Note price
b o implicit rune augmented unmet enchant crafted desecrated fractured Prefix
Suffix Implicit Modifier Tier masked name From To Armour Evasion Rating
Energy Shield Stack Size Spirit Waystone exalted chaos divine regal alchemy
""".split())
_SYLL = ("ka", "lo", "mi", "ne", "ru", "sa", "to", "vi", "zu", "be", "da", "fo",
         "gi", "ha", "ju", "pe")


class PromoteError(ValueError):
    pass


def _invent(word):
    """A deterministic invented word for `word`, of the same case shape."""
    digest = hashlib.sha256(word.lower().encode("ascii", "replace")).digest()
    n = max(1, min(4, (len(word) + 1) // 2))
    out = "".join(_SYLL[b % len(_SYLL)] for b in digest[:n])
    if word.isupper() and len(word) > 1:
        return out.upper()
    if word[:1].isupper():
        return out.capitalize()
    return out


def _ascii(text):
    return "".join(c if ord(c) < 128 else "-" for c in text)


def _rewrite_line(line):
    return _WORD.sub(lambda m: m.group(0) if m.group(0).lower() in STRUCTURAL
                     else _invent(m.group(0)), line)


def rewrite(text):
    """The fixture form of a candidate: invented name and base lines, other
    lines word-rewritten, the shape kept."""
    lines = _ascii(text).split("\n")
    out = []
    header = True
    names = 0
    for line in lines:
        if line == SEPARATOR:
            header = False
            out.append(line)
            continue
        if header and line.startswith(("Item Class:", "Rarity:")):
            out.append(line)
            continue
        if header and line.strip():
            names += 1
            out.append("Invented Name" if names == 1 else f"Invented Base {names - 1}")
            continue
        if line.startswith("Note:"):
            out.append(line)  # the sanitized price form or the mask only
            continue
        out.append(_rewrite_line(line))
    return "\n".join(out)


def _folder(arg):
    if arg:
        return Path(arg)
    return sample.sample_dir()


def _candidate(folder, name):
    if not _NAME.match(name or ""):
        raise PromoteError("a candidate name is letters, digits, - or _ only")
    path = folder / (name + sample.SUFFIX)
    if not path.is_file():
        raise PromoteError(f"no candidate {name}")
    return path


def promote(name, folder, dest=None):
    """Write the rewritten candidate `name` of `folder` into `dest` (default
    tests/fixtures/press_samples). Returns the path written."""
    text = _candidate(folder, name).read_text(encoding="utf-8")
    found = sample.leaks(text)
    if found:
        raise PromoteError(f"candidate {name} still matches: {', '.join(found)}")
    fixture = rewrite(text)
    if fixture == text or fixture == _ascii(text):
        raise PromoteError(f"candidate {name} would be copied verbatim")
    if sample.leaks(fixture):
        raise PromoteError(f"the rewrite of {name} leaks")
    dest = Path(dest) if dest else FIXTURES
    target = dest / (name + sample.SUFFIX)
    if target.exists():
        raise PromoteError(f"fixture {name} exists")
    dest.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="ascii", newline="\n") as fh:
        fh.write(fixture)
    return target


def cmd_list(folder, out):
    files = sample.candidates(folder)
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        out.write(f"{p.stem}: {text.count(chr(10))} lines, {len(text)} characters\n")
    out.write(f"candidates: {len(files)} of {sample.MAX_FILES}\n")
    return 0


def cmd_check(folder, out):
    bad = 0
    for p in sample.candidates(folder):
        found = sample.leaks(p.read_text(encoding="utf-8", errors="replace"))
        bad += bool(found)
        out.write(f"{p.stem}: {'leaks ' + ', '.join(found) if found else 'ok'}\n")
    out.write(f"leaking: {bad}\n")
    return 1 if bad else 0


def main(argv=None, out=None):
    out = out or sys.stdout
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=("list", "check", "promote"))
    ap.add_argument("name", nargs="?")
    ap.add_argument("--folder", help="the candidate folder (default: the sidecar's)")
    ap.add_argument("--dest", help="the fixture folder (default tests/fixtures/press_samples)")
    args = ap.parse_args(argv)
    try:
        folder = _folder(args.folder)
    except ValueError:
        out.write("no candidate folder in an installed copy\n")
        return 2
    if args.command == "list":
        return cmd_list(folder, out)
    if args.command == "check":
        return cmd_check(folder, out)
    try:
        target = promote(args.name, folder, args.dest)
    except PromoteError as exc:
        out.write(f"refused: {exc}\n")
        return 1
    try:
        shown = target.relative_to(ROOT).as_posix()
    except ValueError:
        shown = target.name
    out.write(f"promoted: {shown}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
