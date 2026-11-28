"""The loaded build, kept across restarts (TC-CODE ZERO-CLICK), one per
character (BUILD-LIVE, decision 0045).

Without a character (`per_character=False`, the legacy and test form) the
last good share code is ops/runtime/build/last-code.txt (gitignored
per-host state, `paths.runtime_dir()`), reloaded when the store is made.

With `per_character=True` (the core) each character the player's own
Client.txt names (decision 0038) has its own file under build/chars/, and
`sync()` (the core loop tick) swaps the loaded build to the character being
played, with no click: the build view, the weights PoB measured for it and
the item check card all follow through the listeners. The old single
last-code.txt moves to the first character known (once; the old file is
renamed, never deleted). A paste goes to the character being played (to
last-code.txt while none is known yet). `sync()` also re-reads the active
file when its mtime / size / bytes change (hot reload), so a new paste in
another tab or a dropped file applies live. A bad code never replaces a
good one; a character with no file has no build.

TC-PRESS-BUILD: a load that replaces a build file keeps the replaced bytes
as `<stem>.undo` beside it (one copy per character, overwritten by the next
replacing load, at most MAX_FILE_BYTES; never listed as a character).

Character names stay on this computer (file names under the runtime dir).
"""

import hashlib
import logging
import os
import re
import threading
import time
from pathlib import Path

from .. import jsonfile
from . import (buildfile, codec, health, model, paste, providers, searchstr, skillsplit,
               specfollow, treeurl)

log = logging.getLogger("al.theorycraft")

CHARS_DIR = "chars"
ACTIVE_FILE = "active-character.txt"
MIGRATED_SUFFIX = ".migrated"
UNDO_SUFFIX = ".undo"  # TC-PRESS-BUILD: the one copy of a replaced build file
MAX_FILE_BYTES = 4 * 1024 * 1024  # a code or a character JSON (charjson caps 2 MB)
MAX_LISTED = 64  # characters with a saved build, listed in the snapshot
# AREA-AUDIT P5-4 (as core._config): a coarse mtime can hide a same-size
# rewrite, so a file whose mtime is this fresh has its bytes re-checked
COARSE_S = 2.5
_PLAIN = re.compile(r"[A-Za-z0-9_]{1,48}")
_UNSET = object()


def default_path(runtime_dir):
    return Path(runtime_dir) / "build" / "last-code.txt"


def slug(name):
    """The file stem for a character name: readable for plain names, with a
    hash so names differing only in case stay apart on Windows; hex for any
    other name. Reversible with name_of()."""
    raw = name.encode("utf-8")
    if _PLAIN.fullmatch(name):
        return "c-" + name + "-" + hashlib.sha1(raw).hexdigest()[:8]
    return "x-" + raw.hex()[:200]


def name_of(stem):
    """slug() reversed, or None for a stem it did not make."""
    try:
        if stem.startswith("c-"):
            name = stem[2:].rpartition("-")[0]
            return name if _PLAIN.fullmatch(name) and slug(name) == stem else None
        if stem.startswith("x-"):
            name = bytes.fromhex(stem[2:]).decode("utf-8")
            return name if name and slug(name) == stem else None
    except ValueError:
        return None
    return None


class BuildStore:
    def __init__(self, path, tree=None, per_character=False, provider_list=None):
        """`tree`: optional treedata.TreeCache (DATA-TREE-SRC); when its
        cache file exists the snapshot names the tree nodes.
        `per_character`: one build per character (BUILD-LIVE); `path` is
        then the legacy last-code.txt the first character inherits."""
        self.path = Path(path)
        self.tree = tree
        self.per_character = bool(per_character)
        self.chars_dir = self.path.parent / CHARS_DIR
        self.providers = list(provider_list or providers.default_providers())
        # BUILD-LIVE: callable() -> the character being played (state), or
        # None; sync() follows it
        self.character_of = None
        # TC-SPEC-FOLLOW (decision 0089): callable() -> the character level
        # (state, decision 0038), or None; the tree spec follows it
        self.level_of = None
        self.character = None
        self.source = None  # the provider name of the loaded build
        # MATH-NEXT-LOOK: callable(build, slot) -> {stat key: weight} that
        # PoB measured for this build (core sets the MATH-WEIGHTS cache's
        # fallback); None uses the health gaps only
        self.weights_for = None
        # TC-UPGRADE-PER-SLOT: callable(base, slot, weights) -> the offline
        # trade-search link doc for a "look for next" row (core binds
        # upgrade.slot_link to the league and the trade id index); None
        # leaves the rows without a link
        self.link_for = None
        # MATH-SKILL-SPLIT / MATH-DEF-BREAKDOWN: callable(build) -> PoB's
        # output table for the loaded build when the optional calc is on
        # and has answered (pobout.OutputsCache.get), else None
        self.calc_outputs = None
        # AREA-AUDIT P7-5: callable() -> whether the calc is on (its first
        # answer may still be pending; pobout.OutputsCache.active)
        self.calc_active = None
        self.build = None
        self.load_error = None
        self.loaded_at = None
        # TC-PRESS-BUILD: whether the last load_code replaced another build
        # (its bytes are the undo copy)
        self.replaced = False
        self._file_key = None
        self._lock = threading.RLock()
        self._listeners = []
        if self.per_character:
            # the character played last, so its build is back before the
            # log names anyone (no flash of "no build" on start)
            self.character = self._read_active()
        self._reload()

    # -- files
    def active_path(self):
        """The file of the character being played (the legacy file while
        none is known)."""
        if not self.per_character or not self.character:
            return self.path
        return self.chars_dir / (slug(self.character) + ".txt")

    def _read_active(self):
        try:
            stem = (self.path.parent / ACTIVE_FILE).read_text(encoding="ascii").strip()
        except (OSError, ValueError):
            return None
        return name_of(stem)

    def _write_active(self):
        if not self.character:
            return
        try:
            jsonfile.write_text(self.path.parent / ACTIVE_FILE, slug(self.character) + "\n")
        except OSError:
            log.warning("active character not saved")

    def characters_with_builds(self):
        """Names with a saved build file (at most MAX_LISTED)."""
        out = []
        try:
            entries = sorted(os.scandir(self.chars_dir), key=lambda e: e.name)
        except OSError:
            return out
        for e in entries:
            if len(out) >= MAX_LISTED:
                break
            if e.name.endswith(".txt"):
                name = name_of(e.name[:-4])
                if name:
                    out.append(name)
        return out

    def _migrate(self):
        """Move the single legacy last-code.txt to the current character
        when that character has no build of its own (once: the legacy file
        is renamed to last-code.txt.migrated, never deleted). Caller holds
        the lock."""
        target = self.active_path()
        if target == self.path or target.exists() or not self.path.exists():
            return False
        try:
            data = self.path.read_bytes()
            if len(data) > MAX_FILE_BYTES:
                return False
            jsonfile.write_bytes(target, data)
            os.replace(self.path, self.path.with_name(self.path.name + MIGRATED_SUFFIX))
        except OSError:
            log.warning("legacy build not moved to the current character")
            return False
        log.info("legacy build moved to the current character")
        return True

    @staticmethod
    def _stat_key(path):
        try:
            st = path.stat()
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def _read_file(self, path):
        """(build, error, (stat key, sha1) or None). No file: (None, None,
        None); an empty file is no build."""
        key = self._stat_key(path)
        if key is None:
            return None, None, None
        if key[1] > MAX_FILE_BYTES:
            return None, "build file too large", (key, None)
        try:
            data = path.read_bytes()
            text = data.decode("ascii").strip()
        except (OSError, ValueError) as e:
            return None, f"unreadable: {type(e).__name__}", (key, None)
        digest = hashlib.sha1(data).hexdigest()
        if not text:
            return None, None, (key, digest)
        try:
            return paste.parse(text), None, (key, digest)
        except (codec.CodeError, model.BuildError) as e:
            return None, str(e), (key, digest)

    def _reload(self):
        build, err, key = self._read_file(self.active_path())
        self._file_key = key
        self.build = self._follow(build)
        self.load_error = err
        self.source = "paste" if build is not None else None
        self.loaded_at = time.time() if build is not None else None
        if err:
            log.warning("last build not reloaded: %s", err)

    # -- live
    def add_listener(self, fn):
        self._listeners.append(fn)

    def _level(self):
        """The character level for the spec pick (level_of(), decision
        0038), or None: an int from 1 to 100 only."""
        if not callable(self.level_of):
            return None
        try:
            level = self.level_of()
        except Exception:  # noqa: BLE001 - the tick must go on
            return None
        if isinstance(level, bool) or not isinstance(level, int):
            return None
        return level if specfollow.MIN_LEVEL <= level <= specfollow.MAX_LEVEL else None

    def _follow(self, build, level=_UNSET):
        """TC-SPEC-FOLLOW: `build` with its tree spec picked for the
        character level (specfollow.follow); a failure keeps PoB's spec."""
        if build is None:
            return None
        if level is _UNSET:
            level = self._level()
        try:
            return specfollow.follow(build, level)
        except Exception:  # must never cost the loaded build
            log.exception("tree spec follow failed")
            return build

    def _fire(self, build):
        for fn in list(self._listeners):
            try:
                fn(build)
            except Exception:  # a listener must not undo a good load
                log.exception("build listener failed")

    def sync(self, name=None):
        """BUILD-LIVE (core loop tick): follow the character being played
        (`name`, else character_of()) and re-read the active build file
        when it changed on disk. An unknown character (None) keeps the
        current build. TC-SPEC-FOLLOW: a new character level (level_of())
        re-picks the tree spec; a different spec is "spec". Returns
        "switch", "reload", "spec" or None; the listeners fire on each."""
        if name is None and callable(self.character_of):
            try:
                name = self.character_of()
            except Exception:  # noqa: BLE001 - the tick must go on
                name = None
        what = None
        with self._lock:
            if self.per_character and name and name != self.character:
                self.character = name
                self._migrate()
                self._write_active()
                self._reload()
                what = "switch"
            elif self._changed_on_disk():
                what = self._hot_reload()
            if not what and self.build is not None:
                level = self._level()
                if level != self.build.follow_level:
                    old = self.build.active_spec_index
                    self.build = self._follow(self.build, level)
                    if self.build.active_spec_index != old:
                        log.info("tree spec follows the character level")
                        what = "spec"
            build = self.build
        if what:
            self._fire(build)
        return what

    def _changed_on_disk(self):
        key = self._stat_key(self.active_path())
        old = self._file_key
        if key is None or old is None:
            return (key is None) != (old is None)
        if key != old[0]:
            return True
        # same (mtime, size): re-check the bytes only while the mtime is
        # too fresh to trust (a same-size rewrite within one mtime tick)
        return time.time() - key[0] / 1e9 <= COARSE_S

    def _hot_reload(self):
        """Caller holds the lock. A bad or missing file never replaces a
        good build (the error shows); a new good one swaps in."""
        old_digest = self._file_key[1] if self._file_key else None
        build, err, key = self._read_file(self.active_path())
        self._file_key = key
        if key is not None and key[1] is not None and key[1] == old_digest:
            return None  # same bytes, new mtime: nothing to do
        if build is None:
            if err and self.load_error != err:
                self.load_error = err
                log.warning("changed build file not loaded: %s", err)
            return None
        self.build = self._follow(build)
        self.load_error = None
        self.source = "paste"
        self.loaded_at = time.time()
        log.info("build file changed on disk: reloaded")
        return "reload"

    def load_code(self, text, source="paste"):
        """Decode, parse, persist and publish any pasted format (PoB code or
        character JSON, auto-detected; TC-JSON) for the character being
        played (BUILD-LIVE). Raises codec.CodeError (ShareUrlError
        included) or model.BuildError; the previous build stays on error. A
        JSON paste persists as its PoB share code. TC-PRESS-BUILD: the file
        it replaces is kept as one undo copy (undo_path)."""
        self.sync()
        build = paste.parse(text)
        code = build.to_code() if paste.detect(text) != "code" else "".join(text.split())
        data = (code + "\n").encode("ascii")
        with self._lock:
            path = self.active_path()
            replaced = self._keep_undo(path, data)
            jsonfile.write_bytes(path, data)
            self.replaced = replaced
            self._file_key = self._read_key(path)
            self.build = build = self._follow(build)
            self.load_error = None
            self.source = source
            self.loaded_at = time.time()
        self._fire(build)
        return build

    @staticmethod
    def undo_path(path):
        """The undo copy of a build file: `<stem>.undo` beside it."""
        return Path(path).with_suffix(UNDO_SUFFIX)

    def _keep_undo(self, path, data):
        """TC-PRESS-BUILD: before `path` is replaced by `data`, copy its
        bytes to undo_path(path) (one per character). No file, an empty or
        too large one, or the same bytes keep the undo copy as it was.
        Caller holds the lock; a failed copy never stops the load."""
        key = self._stat_key(path)
        if key is None or key[1] > MAX_FILE_BYTES:
            return False
        try:
            old = path.read_bytes()
        except OSError:
            return False
        if not old.strip() or old == data:
            return False
        try:
            jsonfile.write_bytes(self.undo_path(path), old)
        except OSError:
            log.warning("replaced build not kept as an undo copy")
            return False
        return True

    def _read_key(self, path):
        key = self._stat_key(path)
        if key is None:
            return None
        try:
            return (key, hashlib.sha1(path.read_bytes()).hexdigest())
        except OSError:
            return (key, None)

    def provider(self, name):
        for p in self.providers:
            if p.name == name:
                return p
        return None

    def import_from(self, name):
        """Load the current character's build from a provider (BUILD-LIVE
        item 4). Raises providers.NotConfigured for an unknown or unset
        provider (the ggg_api stub always does; no request is made)."""
        p = self.provider(name)
        if p is None:
            raise providers.NotConfigured(f"unknown build source {name!r}")
        text = p.fetch(self.character)
        return self.load_code(text, source=p.name)

    def _tree_data(self, b):
        if b is None or self.tree is None:
            return None
        try:
            # DATA-TREE-HOLD: the cached tree (newest or the kept previous
            # one) that best matches this build's active spec nodes
            best_for = getattr(self.tree, "best_for", None)
            if callable(best_for):
                spec = b.active_spec
                return best_for(spec.nodes if spec is not None else ())
            return self.tree.get()
        except Exception:  # optional data must never break the view
            log.exception("tree data unavailable")
            return None

    def file_export(self):
        """TC-BUILDFILE: buildfile.export of the loaded build, or None."""
        b = self.build
        return build_file(b, self._tree_data(b))

    def snapshot(self):
        b = self.build
        tree_data = self._tree_data(b)
        calc_out = _safe(self.calc_outputs, b) if callable(self.calc_outputs) and b else None
        calc_active = bool(_safe(self.calc_active)) if callable(self.calc_active) else False
        return {"loaded": b is not None,
                # BUILD-LIVE (decision 0045): whose build this is, where it
                # came from, and the build sources a later import can use
                "character": self.character, "source": self.source if b else None,
                "loaded_at": self.loaded_at if b else None,
                "providers": [p.status() for p in self.providers],
                "characters_with_builds": (self.characters_with_builds()
                                           if self.per_character else []),
                "build": b.to_dict(tree_data) if b else None,
                "code": b.to_code() if b else None, "load_error": self.load_error,
                # UTIL-SEARCHSTR (decision 0030): copied only on a click
                "search_strings": searchstr.strings(b),
                # MATH-BUILD-HEALTH / MATH-NEXT-LOOK: PoB's own numbers only
                # (decision 0004); rebuilt on every read, so a new build or a
                # new PoB weight shows with no click
                "health": _safe(health.health, b, calc_out, calc_active,
                                fallback=health.health(None)),
                # MATH-SKILL-SPLIT: PoB's per-skill and ailment DPS (saved in
                # every build XML; the calc's values win when it is on)
                "skill_split": _safe(skillsplit.split, b, calc_out,
                                     fallback=skillsplit.split(None)),
                "next_look": _safe(health.next_look, b, self.weights_for, self.link_for,
                                   fallback={"slots": [], "pob_weights": False}),
                # TC-BUILDFILE (decision 0034): what the .build download
                # holds; the text itself comes from GET /api/buildfile
                "build_file": build_file_summary(b, tree_data),
                # TC-TREE-URL (research 0035 R7): the official viewer link,
                # only built here; the player opens it (no request is made)
                "tree_url": _safe(treeurl.from_build, b, tree_data)}


def _safe(fn, *args, fallback=None):
    """fn(*args), or `fallback` when it fails (it must never break the view)."""
    try:
        return fn(*args)
    except Exception:
        log.exception("%s failed", getattr(fn, "__name__", "view"))
        return fallback


def build_file(b, tree_data):
    """TC-BUILDFILE: buildfile.export for a build, or None without a build
    or when the export fails (it must never break the view)."""
    if b is None:
        return None
    try:
        return buildfile.export(b, tree_data)
    except Exception:
        log.exception("build file export failed")
        return None


def build_file_summary(b, tree_data):
    out = build_file(b, tree_data)
    if out is None:
        return None
    doc = out["doc"]
    return {"filename": out["filename"], "notes": out["notes"],
            "passives": len(doc.get("passives", ())), "skills": len(doc.get("skills", ())),
            "slots": len(doc.get("inventory_slots", ()))}
