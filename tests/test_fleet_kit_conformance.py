"""The fleet kit is vendored byte-for-byte (ops/fleet_kit/, pinned by its
MANIFEST.json) and the CLAUDE.md FLEET-COMMON block is byte-identical. Never edit
the kit locally; MAIN ships new versions. On a kit adoption, update KIT_VERSION
and MANIFEST_SHA256 below in the same change."""

import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT_DIR = ROOT / "ops" / "fleet_kit"
KIT = KIT_DIR / "fleet_headless.py"
KIT_VERSION = 32
MANIFEST_SHA256 = "cede0b7c8a80ca6ece410c07b572e4ac9dabe0bf7769d9c82d692bb1858c757d"
SF_CMD = 'bash "$CLAUDE_PROJECT_DIR/ops/fleet_kit/fleet_hook.sh" fleet_subagent_first.py'
CLAIMS_CMD = 'bash "$CLAUDE_PROJECT_DIR/ops/fleet_kit/fleet_hook.sh" fleet_claims.py hook'
RELEASE_CMD = 'python "$CLAUDE_PROJECT_DIR/ops/fleet_kit/fleet_claims.py" release-hook'
# ops/loop/slots.py is the fleet's shared governor file, copied unmodified.
SLOTS_SHA256 = "290cbf80ce6989e15ad778be9032503733c8820030bfa6a9b27439b29d70486e"


def _load():
    spec = importlib.util.spec_from_file_location("fleet_headless", KIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _manifest():
    return json.loads((KIT_DIR / "MANIFEST.json").read_text("ascii"))


def _flat(text):
    return " ".join(text.replace(">", " ").split())


def test_fleet_kit_conformance():
    assert KIT.is_file()
    assert _load().conformance(ROOT) == []


def test_kit_version_and_manifest_pin():
    man = _manifest()
    assert man["version"] == KIT_VERSION
    assert _load().KIT_VERSION == KIT_VERSION
    data = (KIT_DIR / "MANIFEST.json").read_bytes()
    assert hashlib.sha256(data).hexdigest() == MANIFEST_SHA256


def test_every_kit_file_matches_its_manifest_hash():
    files = _manifest()["files"]
    on_disk = {p.name for p in KIT_DIR.iterdir() if p.is_file()}
    assert on_disk == set(files) | {"MANIFEST.json"}
    for name, sha in files.items():
        assert hashlib.sha256((KIT_DIR / name).read_bytes()).hexdigest() == sha, name


def _settings_files():
    return sorted((ROOT / ".claude").glob("settings*.json"))


def _keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from _keys(v)


def test_no_tree_level_display_keys():
    """Kit v9 item 15: display keys live only in the account settings."""
    forbidden = set(json.loads((KIT_DIR / "cli_display.json")
                               .read_text("ascii"))["tree_forbidden"])
    for f in _settings_files():
        found = forbidden & set(_keys(json.loads(f.read_text("utf-8"))))
        assert not found, f"{f.name}: {sorted(found)}"


def _settings():
    return json.loads((ROOT / ".claude" / "settings.json").read_text("ascii"))


def test_stop_hook_runs_kit_done_with_relative_path():
    cmds = [h["command"] for g in _settings()["hooks"]["Stop"] for h in g["hooks"]]
    assert "python ops/fleet_kit/fleet_done.py stop-hook" in cmds
    assert all(":" not in c for c in cmds)  # no drive path


def test_pretooluse_hook_runs_kit_subagent_first():
    """Kit v11 section 4 item 2: the subagent-first hook, anchored command."""
    want = {"matcher": "Bash|PowerShell|Read|Edit|Write|Grep|Glob|NotebookEdit|MultiEdit",
            "hooks": [{"type": "command", "command": SF_CMD, "timeout": 15}]}
    assert want in _settings()["hooks"]["PreToolUse"]
    assert (KIT_DIR / "fleet_subagent_first.py").is_file()


def test_claims_hooks_wired_exactly():
    """Kit v12 section 3 item 3: claims PreToolUse + SubagentStop release."""
    doc = _settings()
    pre = {"matcher": "Edit|Write|NotebookEdit|MultiEdit|Bash|PowerShell",
           "hooks": [{"type": "command", "command": CLAIMS_CMD, "timeout": 15}]}
    assert pre in doc["hooks"]["PreToolUse"]
    stop = [h for g in doc["hooks"]["SubagentStop"] for h in g["hooks"]]
    assert {"type": "command", "command": RELEASE_CMD, "timeout": 10} in stop


def test_done_ritual_last_act_is_the_marker_and_it_is_dispatched():
    text = (ROOT / ".claude" / "commands" / "done.md").read_text("ascii")
    mark = "python ops/fleet_kit/fleet_done.py mark --session <n> --status done"
    assert mark in text
    tail = text[text.index(mark):]
    assert "Done ritual complete, safe to clear" in tail
    assert "git push" not in tail
    assert ("DISPATCH (kit v10):** the main session runs no tool for /done; it dispatches "
            "the whole ritual to ONE background sub-agent and relays only that agent's "
            "final line verbatim.") in _flat(text)


def test_done_routes_commit_and_suite_through_the_guards():
    """Kit v12 section 3 item 5: /done says gitlock + suite gate."""
    text = (ROOT / ".claude" / "commands" / "done.md").read_text("ascii")
    assert "fleet_gitlock.py run --owner" in text
    assert "fleet_suite_gate.py run --owner" in text


def test_shared_slots_governor_is_byte_identical():
    data = (ROOT / "ops" / "loop" / "slots.py").read_bytes()
    assert hashlib.sha256(data).hexdigest() == SLOTS_SHA256


def test_race_guard_paths_gitignored():
    """Kit v12 section 3 item 4: every race-guard path is ignored, by its own
    line or by the ops/loop/control/* wildcard."""
    lines = (ROOT / ".gitignore").read_text("ascii").splitlines()
    wildcard = "ops/loop/control/*" in lines
    for want in ("ops/loop/control/claims/", "ops/loop/control/locks/",
                 "ops/loop/control/claims.jsonl", "ops/loop/control/claims.mode",
                 "ops/loop/control/gitlock.jsonl"):
        assert wildcard or want in lines, want


def test_conftest_installs_test_guard():
    """Kit v12 section 3 item 6."""
    text = (ROOT / "tests" / "conftest.py").read_text("ascii")
    assert "fleet_test_guard.install(globals()" in text


def test_git_hooks_wire_identity_and_leak_sweep():
    """Kit v13 (FLEET-COMMON 17): commit-msg strips, pre-push guards every
    push (ref rule, identity gate, leak sweep), pre-commit runs the leak
    sweep over staged lines."""
    hooks = ROOT / ".githooks"
    cm = (hooks / "commit-msg").read_text("ascii")
    pp = (hooks / "pre-push").read_text("ascii")
    pc = (hooks / "pre-commit").read_text("ascii")
    assert re.search(r'fleet_identity\.py" commit-msg "\$1" \|\| (true|exit 1)', cm)
    assert 'fleet_identity.py" pre-push "$@" || exit 1' in pp
    assert 'leak_sweep.py" --pre-push' in pp
    # GP-02 (decision 0046): the guarded push replaces refuse-all
    assert "PUSH REFUSED" not in pp
    assert "AL_ALLOW_PUSH" not in pp
    assert pp.rstrip().endswith("exit 0")
    assert "refs/heads/main|refs/tags/v[0-9]*" in pp
    order = [pp.index("check_refs || exit 1"),
             pp.index('push_guard.py" "$@" || exit 1'),
             pp.index('release.py" prepush-check "$@" || exit 1'),
             pp.index('fleet_identity.py" pre-push "$@" || exit 1'),
             pp.index('leak_sweep.py" --pre-push "$@" || exit 1'),
             pp.rstrip().rindex("exit 0")]
    assert order == sorted(order), order
    assert 'tools/leak_sweep.py" --staged' in pc
    for hook in (cm, pp, pc):
        assert "\r" not in hook and hook.startswith("#!/bin/sh")
