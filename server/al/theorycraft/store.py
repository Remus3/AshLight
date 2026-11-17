"""The loaded build, kept across restarts (TC-CODE ZERO-CLICK).

The last good share code is written to ops/runtime/build/last-code.txt
(gitignored per-host state, `paths.runtime_dir()`), and reloaded when the
store is made, so the last build is back on start with no click. A bad code
never replaces a good one.
"""

import logging
import threading
from pathlib import Path

from . import buildfile, codec, health, model, paste, searchstr

log = logging.getLogger("al.theorycraft")


def default_path(runtime_dir):
    return Path(runtime_dir) / "build" / "last-code.txt"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="ascii", newline="\n") as fh:
        fh.write(text)
    tmp.replace(path)


class BuildStore:
    def __init__(self, path, tree=None):
        """`tree`: optional treedata.TreeCache (DATA-TREE-SRC); when its
        cache file exists the snapshot names the tree nodes."""
        self.path = Path(path)
        self.tree = tree
        # MATH-NEXT-LOOK: callable(build, slot) -> {stat key: weight} that
        # PoB measured for this build (core sets the MATH-WEIGHTS cache's
        # fallback); None uses the health gaps only
        self.weights_for = None
        self.build = None
        self.load_error = None
        self._lock = threading.Lock()
        self._listeners = []
        self._reload()

    def _reload(self):
        try:
            code = self.path.read_text(encoding="ascii").strip()
        except FileNotFoundError:
            return
        except (OSError, ValueError) as e:
            self.load_error = f"unreadable: {type(e).__name__}"
            return
        try:
            self.build = model.from_code(code)
        except (codec.CodeError, model.BuildError) as e:
            self.load_error = str(e)
            log.warning("last build not reloaded: %s", e)

    def add_listener(self, fn):
        self._listeners.append(fn)

    def load_code(self, text):
        """Decode, parse, persist and publish any pasted format (PoB code or
        character JSON, auto-detected; TC-JSON). Raises codec.CodeError
        (ShareUrlError included) or model.BuildError; the previous build
        stays on error. A JSON paste persists as its PoB share code."""
        build = paste.parse(text)
        code = build.to_code() if paste.detect(text) != "code" else "".join(text.split())
        with self._lock:
            _write(self.path, code + "\n")
            self.build = build
            self.load_error = None
        for fn in list(self._listeners):
            try:
                fn(build)
            except Exception:  # a listener must not undo a good load
                log.exception("build listener failed")
        return build

    def _tree_data(self, b):
        if b is None or self.tree is None:
            return None
        try:
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
        return {"loaded": b is not None,
                "build": b.to_dict(tree_data) if b else None,
                "code": b.to_code() if b else None, "load_error": self.load_error,
                # UTIL-SEARCHSTR (decision 0030): copied only on a click
                "search_strings": searchstr.strings(b),
                # MATH-BUILD-HEALTH / MATH-NEXT-LOOK: PoB's own numbers only
                # (decision 0004); rebuilt on every read, so a new build or a
                # new PoB weight shows with no click
                "health": _safe(health.health, b, fallback=health.health(None)),
                "next_look": _safe(health.next_look, b, self.weights_for,
                                   fallback={"slots": [], "pob_weights": False}),
                # TC-BUILDFILE (decision 0034): what the .build download
                # holds; the text itself comes from GET /api/buildfile
                "build_file": build_file_summary(b, tree_data)}


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
