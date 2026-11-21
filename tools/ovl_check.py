#!/usr/bin/env python3
"""OVL-CHECK (finding F-128, ruling Q-18, budget B19): the in-map overlay
check as one normally played map. Developer-only; the shipped app never
starts it and nothing under server/ or app/ imports it.

    python tools/ovl_check.py arm [--port N] [--no-spawn]
    python tools/ovl_check.py run [--port N]
    python tools/ovl_check.py status
    python tools/ovl_check.py answer same|dropped
    python tools/ovl_check.py restore [--port N]

arm writes the armed flag (valid ARM_TTL_S) in the sidecar Logs dir and
starts one hidden `run`. run waits until the running core's GET /api/state
shows an open map (maps.current.inside, the game not idle) for WARMUP_S,
then plays nine BLOCK_S blocks, hidden / shown / updating three times:

- hidden: POST /api/overlay-layout with every overlay part off
  (OVL-OVERLAY-KEYS; a failure word still shows, by design);
- shown: the player's own parts restored;
- updating: parts restored plus POST /api/overlay-sample (OVL-CARD-SLOT,
  a 10 s sample card, asked again every SAMPLE_EVERY_S) and an opacity
  nudge inside the layout limits every NUDGE_EVERY_S.

The player's saved layout is copied first (ovl_check.restore.json) and put
back at the end and on any error; a leftover copy is put back by the next
run or by `restore`.

Each second it records (decision 0006 methods 1 to 3 only):
- the core's own CPU seconds and working set from the token-gated
  GET /api/debug (the core measures itself through its own handle);
- the desktop client's figures from overlay-state.json in the runtime dir
  (app/metrics.js, once a minute; budgetlog.read_client), so the client
  part is coarse: each block uses the client rows written inside it;
- system-wide CPU totals (GetSystemTimes on Windows, /proc/stat
  elsewhere), never keyed to any process.
It opens no process, lists no process, looks at no window, reads no screen
and sends no input; it only calls endpoints the core already has. The
game's own FPS display is read by the operator (method 1): one same /
dropped answer at the end, from a console prompt when run in one, else
from the 'Tried in game' card (OVL-FPS Worked = same, Refused = dropped,
GET /api/verdicts) within ANSWER_WAIT_S, or later by `answer`.

Output in the sidecar Logs dir: ovl_check-<stamp>.json (the report) and
ovl_check-<stamp>.txt (a 15-line summary). The armed flag is cleared when
the blocks end. B19 (decision 0006 note 2026-11-21), a proxy, not a
frame-time measure: the operator saw no change on the game's own FPS
display with the HUD on, AshLight CPU under 1 percent of one core while
shown and updating, and system CPU within the noise of the hidden blocks.

Standard library only.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.al import budgetlog, hello, jsonfile, paths, ports  # noqa: E402

WARMUP_S = 20.0
BLOCK_S = 30.0
KINDS = ("hidden", "shown", "updating")
BLOCKS = KINDS * 3
SAMPLE_S = 1.0
STATE_EVERY_S = 5.0
POLL_S = 2.0
HEARTBEAT_S = 10.0
RUNNER_FRESH_S = 30.0
ARM_TTL_S = 24 * 3600.0
ANSWER_WAIT_S = 900.0
ANSWER_POLL_S = 10.0
SAMPLE_EVERY_S = 10.0
NUDGE_EVERY_S = 5.0
NUDGE = 0.02
MAX_ABORTS = 3
TIMEOUT_S = 3.0
MAX_BODY = 256 * 1024
CPU_LIMIT_PCT = 1.0      # B19: AshLight under 1 percent of one core
NOISE_FLOOR_PCT = 2.0    # system CPU: never call a change under this noise
SUMMARY_LINES = 15
ANSWERS = ("same", "dropped")
VERDICT_CHECK = "OVL-FPS"
VERDICT_ANSWER = {"worked": "same", "refused": "dropped"}
PREFIX = "ovl_check"
ARMED_FILE = PREFIX + ".armed.json"
RESTORE_FILE = PREFIX + ".restore.json"
RUNNER_FILE = PREFIX + ".running.json"
REPORT_VERSION = 1
PROXY_NOTE = ("A proxy, not a frame-time measure: the game's own FPS display "
              "read by the operator, AshLight's own CPU and system-wide CPU "
              "totals (decision 0006 methods 1 to 3).")


class CoreGone(Exception):
    """The core did not answer, failed the hello proof or refused a call."""


# -- files in the sidecar Logs dir
def logs_dir():
    d = paths.sidecar_dir("Logs")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read(name):
    return jsonfile.read_json(logs_dir() / name, kind=dict, default=None)


def _write(name, doc):
    jsonfile.write_json(logs_dir() / name, doc, indent=2)


def _drop(name):
    try:
        (logs_dir() / name).unlink()
    except FileNotFoundError:
        pass


def armed(now):
    doc = _read(ARMED_FILE)
    if not isinstance(doc, dict):
        return False
    exp = doc.get("expires_at")
    return isinstance(exp, (int, float)) and not isinstance(exp, bool) and now < exp


def _iso(t):
    return datetime.datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


# -- the core link (loopback only, no proxy, hello proof before the token)
def read_token():
    try:
        return paths.token_file().read_text(encoding="ascii").strip()
    except (OSError, ValueError):
        return ""


def default_port():
    return ports.resolve(None, paths.load_local_config())


class Link:
    def __init__(self, port, token=None, timeout=TIMEOUT_S):
        self.port = int(port)
        self.token = read_token() if token is None else token
        self.timeout = timeout

    def _open(self, req):
        if not self.token or not hello.verify(self.port, self.token,
                                              opener=hello.NO_PROXY_OPENER,
                                              timeout=self.timeout):
            raise CoreGone("no verified core")
        try:
            with hello.NO_PROXY_OPENER.open(req, timeout=self.timeout) as r:
                data = r.read(MAX_BODY + 1)
                status = r.status
        except (OSError, ValueError) as exc:
            hello.forget(self.port)
            raise CoreGone(type(exc).__name__) from None
        if status != 200 or len(data) > MAX_BODY:
            hello.forget(self.port)
            raise CoreGone("status")
        try:
            doc = json.loads(data or b"null")
        except ValueError:
            raise CoreGone("not json") from None
        if not isinstance(doc, dict):
            raise CoreGone("shape")
        return doc

    def _url(self, path):
        return f"http://{ports.LOOPBACK}:{self.port}{path}"

    def get(self, path):
        return self._open(urllib.request.Request(
            self._url(path), headers={"X-AL-Token": self.token}))

    def post(self, path, body):
        data = json.dumps(body).encode("ascii")
        return self._open(urllib.request.Request(
            self._url(path), data=data, method="POST",
            headers={"X-AL-Token": self.token, "Content-Type": "application/json"}))


def in_map(state):
    if not isinstance(state, dict) or state.get("game_idle"):
        return False
    cur = (state.get("maps") or {}).get("current") or {}
    return isinstance(cur, dict) and cur.get("inside") is True


# -- system-wide CPU totals (never per process)
def system_times():
    """(idle, total) CPU seconds summed over all CPUs, or None."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        idle, kern, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        if not ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
            return None

        def secs(ft):
            return ((ft.dwHighDateTime << 32) | ft.dwLowDateTime) / 1e7
        # kernel time includes idle time
        return secs(idle), secs(kern) + secs(user)
    try:
        with open("/proc/stat", encoding="ascii") as fh:
            parts = fh.readline().split()
    except OSError:
        return None
    if not parts or parts[0] != "cpu":
        return None
    vals = [float(v) for v in parts[1:]]
    return vals[3] + (vals[4] if len(vals) > 4 else 0.0), sum(vals)


def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
        return None
    return float(v)


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


def _r(v):
    return None if v is None else round(v, 3)


class Checker:
    """One armed check. clock / sleep / wall / system / ask are injectable
    (the test runs it on a fake clock against a stub core)."""

    def __init__(self, port, runtime=None, clock=time.monotonic, sleep=time.sleep,
                 wall=time.time, system=system_times, ask=None, out=None,
                 answer_wait_s=ANSWER_WAIT_S):
        self.port = int(port)
        self.runtime = Path(runtime) if runtime is not None else paths.runtime_dir()
        self.clock, self.sleep, self.wall = clock, sleep, wall
        self.system = system
        self.ask = ask
        self.out = out or sys.stdout
        self.answer_wait_s = answer_wait_s
        self._beat = None

    def link(self):
        return Link(self.port)

    def heartbeat(self, step, force=False):
        now = self.clock()
        if force or self._beat is None or now - self._beat >= HEARTBEAT_S:
            self._beat = now
            _write(RUNNER_FILE, {"updated": self.wall(), "step": step})

    # -- waiting for the map
    def wait_for_map(self):
        """True once the map has been open WARMUP_S; False when disarmed."""
        since = None
        while True:
            if not armed(self.wall()):
                return False
            self.heartbeat("waiting")
            try:
                inside = in_map(self.link().get("/api/state"))
            except CoreGone:
                inside = False
            now = self.clock()
            if inside:
                since = now if since is None else since
                if now - since >= WARMUP_S:
                    return True
            else:
                since = None
            self.sleep(POLL_S)

    # -- the blocks
    def restore_leftover(self):
        doc = _read(RESTORE_FILE)
        if isinstance(doc, dict) and isinstance(doc.get("layout"), dict):
            self.link().post("/api/overlay-layout", doc["layout"])
            _drop(RESTORE_FILE)
            return True
        return False

    def _apply(self, link, kind, layout):
        parts = dict(layout.get("parts") or {})
        if kind == "hidden":
            link.post("/api/overlay-layout", {"parts": {p: False for p in parts}})
        else:
            link.post("/api/overlay-layout", {"parts": parts,
                                              "opacity": layout.get("opacity")})

    @staticmethod
    def nudged(layout, limits):
        base = _num(layout.get("opacity")) or 0.86
        lo, hi = (limits or {}).get("opacity") or [0.8, 1.0]
        up = round(base + NUDGE, 2)
        return up if up <= hi else round(max(lo, base - NUDGE), 2)

    def run_blocks(self):
        link = self.link()
        doc = link.get("/api/overlay-layout")
        layout = doc.get("layout")
        if not isinstance(layout, dict):
            raise CoreGone("no layout")
        _write(RESTORE_FILE, {"layout": layout})
        blocks, restored = [], False
        try:
            for kind in BLOCKS:
                self.heartbeat(kind, force=True)
                blocks.append(self._block(link, kind, layout, doc.get("limits")))
        finally:
            try:
                Link(self.port).post("/api/overlay-layout", layout)
                _drop(RESTORE_FILE)
                restored = True
            except CoreGone:
                restored = False
        return blocks, restored

    def _block(self, link, kind, layout, limits):
        self._apply(link, kind, layout)
        t0 = self.clock()
        cpu, sysv, clients, in_map_s, samples = [], [], {}, 0, 0
        last_state, inside = None, True
        last_sample = last_nudge = None
        nudge_on = False
        while True:
            now = self.clock()
            el = now - t0
            if el >= BLOCK_S:
                break
            if kind == "updating":
                if last_sample is None or now - last_sample >= SAMPLE_EVERY_S:
                    link.post("/api/overlay-sample", {})
                    last_sample = now
                if last_nudge is None or now - last_nudge >= NUDGE_EVERY_S:
                    nudge_on = not nudge_on
                    op = self.nudged(layout, limits) if nudge_on else layout.get("opacity")
                    link.post("/api/overlay-layout", {"opacity": op})
                    last_nudge = now
            debug = link.get("/api/debug")
            proc = debug.get("process") or {}
            cpu.append((now, _num(proc.get("cpu_s")), _num(proc.get("working_set_mb"))))
            st = self.system()
            if st is not None:
                sysv.append(st)
            got = budgetlog.read_client(self.runtime, self.wall())
            if got:
                c = got[0]
                key = round(self.wall() - (c.get("age_s") or 0.0))
                clients[key] = c
            if last_state is None or now - last_state >= STATE_EVERY_S:
                try:
                    inside = in_map(link.get("/api/state"))
                except CoreGone:
                    inside = False
                last_state = now
            in_map_s += 1 if inside else 0
            samples += 1
            self.sleep(SAMPLE_S)
        return self._summarize(kind, cpu, sysv, clients, in_map_s, samples)

    @staticmethod
    def _summarize(kind, cpu, sysv, clients, in_map_s, samples):
        core_pct = ws = None
        good = [r for r in cpu if r[1] is not None]
        if len(good) >= 2 and good[-1][0] > good[0][0]:
            core_pct = max(0.0, (good[-1][1] - good[0][1]) / (good[-1][0] - good[0][0]) * 100.0)
        ws_vals = [r[2] for r in cpu if r[2] is not None]
        if ws_vals:
            ws = max(ws_vals)
        sys_pct = None
        if len(sysv) >= 2:
            d_idle = sysv[-1][0] - sysv[0][0]
            d_total = sysv[-1][1] - sysv[0][1]
            if d_total > 0:
                sys_pct = max(0.0, min(100.0, (d_total - d_idle) / d_total * 100.0))
        rows = list(clients.values())
        client_pct = _mean([_num(c.get("cpu_pct")) for c in rows])
        overlay_pct = _mean([_num(c.get("overlay_cpu_pct")) for c in rows])
        ash = None if core_pct is None else core_pct + (client_pct or 0.0)
        return {"kind": kind, "samples": samples, "in_map_s": in_map_s,
                "core_cpu_pct": _r(core_pct), "core_ws_mb_max": _r(ws),
                "client_rows": len(rows), "client_cpu_pct": client_pct,
                "overlay_cpu_pct": overlay_pct, "ashlight_cpu_pct": _r(ash),
                "system_cpu_pct": _r(sys_pct)}


# -- the report
def by_kind(blocks):
    out = {}
    for kind in KINDS:
        mine = [b for b in blocks if b["kind"] == kind]
        out[kind] = {k: _mean([b.get(k) for b in mine])
                     for k in ("ashlight_cpu_pct", "core_cpu_pct", "client_cpu_pct",
                               "overlay_cpu_pct", "system_cpu_pct")}
    return out


def b19(blocks, answer):
    kinds = by_kind(blocks)
    on = [kinds[k]["ashlight_cpu_pct"] for k in ("shown", "updating")]
    cpu_ok = None if any(v is None for v in on) else all(v < CPU_LIMIT_PCT for v in on)
    hidden = [b["system_cpu_pct"] for b in blocks
              if b["kind"] == "hidden" and b["system_cpu_pct"] is not None]
    base = kinds["hidden"]["system_cpu_pct"]
    ons = [kinds[k]["system_cpu_pct"] for k in ("shown", "updating")]
    noise = round(max(NOISE_FLOOR_PCT, (max(hidden) - min(hidden)) if hidden else 0.0), 3)
    delta = None if base is None or any(v is None for v in ons) else round(max(ons) - base, 3)
    sys_ok = None if delta is None else delta <= noise
    ans_ok = None if answer is None else answer == "same"
    parts = (cpu_ok, sys_ok, ans_ok)
    verdict = ("fail" if False in parts else "pending" if None in parts else "pass")
    return {"verdict": verdict, "ashlight_cpu_ok": cpu_ok, "cpu_limit_pct": CPU_LIMIT_PCT,
            "system_delta_pct": delta, "system_noise_pct": noise,
            "system_within_noise": sys_ok, "answer_ok": ans_ok}


def _fmt(v):
    return "-" if v is None else f"{v:g}"


def summary_lines(rep):
    k, b = rep["by_kind"], rep["b19"]

    def row(kind):
        d = k[kind]
        return (f"{kind}: ashlight={_fmt(d['ashlight_cpu_pct'])}% core={_fmt(d['core_cpu_pct'])}%"
                f" client={_fmt(d['client_cpu_pct'])}% system={_fmt(d['system_cpu_pct'])}%")
    cpu_word = {True: "ok", False: "over", None: "unknown"}[b["ashlight_cpu_ok"]]
    sys_word = {True: "within", False: "above", None: "unknown"}[b["system_within_noise"]]
    total_s = int(len(BLOCKS) * BLOCK_S)
    lines = [
        f"ovl_check: {b['verdict']} (budget B19)",
        f"started: {rep['started']}",
        f"ended: {rep['ended']}",
        f"blocks: {len(rep['blocks'])} x {int(BLOCK_S)} s (hidden, shown, updating)",
        f"in_map: {sum(x['in_map_s'] for x in rep['blocks'])} of {total_s} s",
        row("hidden"), row("shown"), row("updating"),
        f"ashlight_cpu: shown={_fmt(k['shown']['ashlight_cpu_pct'])}%"
        f" updating={_fmt(k['updating']['ashlight_cpu_pct'])}%"
        f" limit {CPU_LIMIT_PCT:g}% -> {cpu_word}",
        f"system_cpu: delta={_fmt(b['system_delta_pct'])}%"
        f" noise={_fmt(b['system_noise_pct'])}% -> {sys_word}",
        f"client_rows: {sum(x['client_rows'] for x in rep['blocks'])}"
        " (the client writes once a minute)",
        f"answer: {rep['answer'] or 'pending'} (the game's own FPS display, HUD on)",
        "layout: " + ("restored" if rep["layout_restored"] else
                      "NOT restored, run: python tools/ovl_check.py restore"),
        "method: decision 0006 methods 1 to 3; a proxy, not a frame-time measure",
        f"report: {rep['name']}.json",
    ]
    assert len(lines) == SUMMARY_LINES
    return lines


def write_report(rep):
    rep["b19"] = b19(rep["blocks"], rep.get("answer"))
    d = logs_dir()
    jsonfile.write_json(d / (rep["name"] + ".json"), rep, indent=2)
    (d / (rep["name"] + ".txt")).write_bytes(
        ("\n".join(summary_lines(rep)) + "\n").encode("ascii"))
    return d / (rep["name"] + ".json")


def make_report(blocks, restored, started, ended):
    stamp = datetime.datetime.fromtimestamp(started).strftime("%Y%m%d-%H%M%S")
    return {"v": REPORT_VERSION, "tool": PREFIX, "name": f"{PREFIX}-{stamp}",
            "started": _iso(started), "started_at": int(started),
            "ended": _iso(ended), "block_s": BLOCK_S, "warmup_s": WARMUP_S,
            "blocks": blocks, "by_kind": by_kind(blocks), "layout_restored": restored,
            "answer": None, "answered_at": None, "answer_source": None,
            "note": PROXY_NOTE}


def latest_report():
    files = sorted(logs_dir().glob(PREFIX + "-*.json"))
    return files[-1] if files else None


def set_answer(path, answer, source, at):
    rep = jsonfile.read_json(path, kind=dict, default=None)
    if not isinstance(rep, dict):
        return None
    rep.update(answer=answer, answer_source=source, answered_at=int(at))
    return write_report(rep)


def verdict_answer(doc, since):
    """same / dropped from a GET /api/verdicts document: the newest OVL-FPS
    row recorded at or after `since`, else None."""
    for row in (doc or {}).get("rows") or []:  # newest first
        if not isinstance(row, dict) or row.get("check") != VERDICT_CHECK:
            continue
        at = row.get("at")
        if isinstance(at, int) and not isinstance(at, bool) and at >= since:
            return VERDICT_ANSWER.get(row.get("result"))
        return None
    return None


def collect_answer(chk, since):
    """The operator's one answer: a console prompt, else the card."""
    if chk.ask is not None:
        for _ in range(3):
            got = (chk.ask() or "").strip().lower()
            if got in ANSWERS:
                return got, "prompt"
        return None, None
    end = chk.clock() + chk.answer_wait_s
    while chk.clock() < end:
        try:
            got = verdict_answer(chk.link().get("/api/verdicts"), since)
        except CoreGone:
            got = None
        if got:
            return got, "card"
        chk.sleep(ANSWER_POLL_S)
    return None, None


def run(chk):
    """Wait, play the blocks, report, clear the flag, take the answer.
    Returns the report path, or None when disarmed before a map."""
    try:
        chk.restore_leftover()
    except CoreGone:
        pass
    aborts = 0
    while aborts < MAX_ABORTS:
        if not chk.wait_for_map():
            _drop(RUNNER_FILE)
            return None
        started = chk.wall()
        try:
            blocks, restored = chk.run_blocks()
        except CoreGone:
            aborts += 1
            continue
        rep = make_report(blocks, restored, started, chk.wall())
        path = write_report(rep)
        _drop(ARMED_FILE)
        chk.heartbeat("answer", force=True)
        answer, source = collect_answer(chk, int(started))
        if answer:
            path = set_answer(path, answer, source, chk.wall())
        _drop(RUNNER_FILE)
        for line in summary_lines(jsonfile.read_json(path, kind=dict)):
            chk.out.write(line + "\n")
        return path
    _drop(RUNNER_FILE)
    return None


# -- commands
def spawn_runner(port):
    exe = Path(sys.executable)
    quiet = exe.with_name("pythonw.exe")
    exe = quiet if os.name == "nt" and quiet.is_file() else exe
    flags = 0
    if os.name == "nt":
        flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                 | subprocess.CREATE_NO_WINDOW)
    subprocess.Popen([str(exe), str(Path(__file__).resolve()), "run", "--port", str(port)],
                     cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)


def runner_live(now):
    doc = _read(RUNNER_FILE)
    up = doc.get("updated") if isinstance(doc, dict) else None
    return isinstance(up, (int, float)) and not isinstance(up, bool) and now - up < RUNNER_FRESH_S


def cmd_arm(args, out, wall=time.time, spawn=spawn_runner):
    now = wall()
    _write(ARMED_FILE, {"armed_at": now, "expires_at": now + ARM_TTL_S})
    out.write(f"armed: yes, for {int(ARM_TTL_S // 3600)} h\n")
    if args.no_spawn or runner_live(now):
        out.write("runner: " + ("already live\n" if runner_live(now) else "not started\n"))
        return 0
    spawn(args.port)
    out.write("runner: started hidden\n")
    return 0


def cmd_status(out, wall=time.time):
    now = wall()
    out.write(f"armed: {'yes' if armed(now) else 'no'}\n")
    out.write(f"runner: {'live' if runner_live(now) else 'none'}\n")
    out.write(f"restore_pending: {'yes' if _read(RESTORE_FILE) else 'no'}\n")
    path = latest_report()
    if path is None:
        out.write("last_report: none\n")
        return 0
    rep = jsonfile.read_json(path, kind=dict, default={}) or {}
    out.write(f"last_report: {path.name}\n")
    out.write(f"answer: {rep.get('answer') or 'pending'}\n")
    out.write(f"verdict: {(rep.get('b19') or {}).get('verdict', '-')}\n")
    return 0


def cmd_answer(args, out, wall=time.time):
    path = latest_report()
    if path is None:
        out.write("answer: no report yet\n")
        return 1
    set_answer(path, args.value, "command", wall())
    out.write(f"answer: {args.value} recorded in {path.name}\n")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="python tools/ovl_check.py",
                                 description="The in-map overlay check (OVL-CHECK, B19).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("arm", "run", "restore"):
        p = sub.add_parser(name)
        p.add_argument("--port", type=int, default=None)
        if name == "arm":
            p.add_argument("--no-spawn", action="store_true",
                           help="write the flag only; start `run` yourself")
    sub.add_parser("status")
    p = sub.add_parser("answer")
    p.add_argument("value", choices=ANSWERS)
    return ap


def _console_ask():
    return input("Game's own FPS display with the HUD on: same or dropped? ")


def main(argv=None, out=None):
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    if args.cmd == "status":
        return cmd_status(out)
    if args.cmd == "answer":
        return cmd_answer(args, out)
    if getattr(args, "port", None) is None:
        args.port = default_port()
    if args.cmd == "arm":
        return cmd_arm(args, out)
    chk = Checker(args.port, out=out,
                  ask=_console_ask if sys.stdin is not None and sys.stdin.isatty() else None)
    if args.cmd == "restore":
        try:
            done = chk.restore_leftover()
        except CoreGone:
            out.write("restore: core not reachable\n")
            return 1
        out.write("restore: " + ("layout put back\n" if done else "nothing to restore\n"))
        return 0
    path = run(chk)
    if path is None:
        out.write("run: ended without a check (disarmed or the core kept failing)\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
