"""The loaded build, kept across restarts (TC-CODE ZERO-CLICK).

The last good share code is written to ops/runtime/build/last-code.txt
(gitignored per-host state, `paths.runtime_dir()`), and reloaded when the
store is made, so the last build is back on start with no click. A bad code
never replaces a good one.
"""

import logging
import threading
from pathlib import Path

from . import codec, model

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
    def __init__(self, path):
        self.path = Path(path)
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
        """Decode, parse, persist and publish. Raises codec.CodeError
        (ShareUrlError included) or model.BuildError; the previous build
        stays on error."""
        build = model.from_code(text)
        code = build.to_code() if codec.classify(text) != "code" else "".join(text.split())
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

    def snapshot(self):
        b = self.build
        return {"loaded": b is not None, "build": b.to_dict() if b else None,
                "code": b.to_code() if b else None, "load_error": self.load_error}
