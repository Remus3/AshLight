"""TC-BRIDGE test double: speaks the bridge's stdio protocol like
server/al/theorycraft/bridge.lua does, with no LuaJIT and no PoB.

Lines on stdout that do not start with the frame prefix are noise the client
must ignore (PoB prints to stdout). Commands beyond the real ones drive the
failure paths: "sleep" hangs, "die" exits mid-request.
"""

import json
import os
import sys
import time

PREFIX = "ALB1 "


def send(obj):
    sys.stdout.write(PREFIX + json.dumps(obj) + "\n")
    sys.stdout.flush()


def main():
    state = {"xml": None, "items": []}
    marker = os.environ.get("ALB_FAKE_MARKER")
    if marker:
        with open(marker, "a", encoding="ascii") as f:
            f.write("start\n")
    sys.stdout.write("PoB noise line that is not a frame\n")
    send({"id": 0, "ok": True, "result": {"ready": True, "pob": "fake"}})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        rid = req.get("id")
        cmd = req.get("cmd")
        if cmd == "ping":
            send({"id": rid, "ok": True, "result": {"pong": True}})
        elif cmd == "load_build":
            state["xml"] = req.get("xml")
            state["items"] = []
            send({"id": rid, "ok": True, "result": {"loaded": True}})
        elif cmd == "set_item":
            if state["xml"] is None:
                send({"id": rid, "ok": False, "error": "no build loaded"})
                continue
            state["items"].append(req.get("text"))
            send({"id": rid, "ok": True,
                  "result": {"slot": req.get("slot") or "Weapon 1"}})
        elif cmd == "outputs":
            if state["xml"] is None:
                send({"id": rid, "ok": False, "error": "no build loaded"})
                continue
            out = {"Life": 1000 + 10 * len(state["items"]), "TotalDPS": 123.5,
                   "FullDPS": 130.25}
            keys = req.get("keys")
            if keys:
                out = {k: v for k, v in out.items() if k in keys}
            send({"id": rid, "ok": True, "result": {"outputs": out}})
        elif cmd == "sleep":
            time.sleep(60)
        elif cmd == "die":
            sys.exit(3)
        elif cmd == "quit":
            send({"id": rid, "ok": True, "result": {}})
            return 0
        else:
            send({"id": rid, "ok": False, "error": "unknown command"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
