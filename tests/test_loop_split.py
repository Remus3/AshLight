"""Plan 107: tools/al_loop.py split by domain, no behaviour change.

The constants / small helpers, prompts, roadmap work list, inbox and merge
code live in tools/loop_*.py; al_loop still exposes every name it had (the
same object), and the Tick keeps every method (inbox, merge, review and work
ones through mixins; LOOP-SPLIT-TICK moved the review / commit and work-list /
dispatch methods). The seams tests monkeypatch stay defined in al_loop itself."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import al_loop  # noqa: E402

# Every module-level name of al_loop before the split (imported modules aside;
# the upstream data verdict items are not ported; TEST-GATE-CALLERS dropped
# XDIST_ARGS, _names_workers and _xdist_available: tools/suite_run.py picks the mode).
NAMES = (
    'ATTENTION_STATES', 'BACKOFF_BASE_S', 'BACKOFF_CAP_S', 'BACKOFF_REL', 'CI_SETUP_RX',
    'CI_WORKFLOW_REL', 'CODE', 'CONTROL_REL', 'DEEP_EXTRA', 'DEFAULT_MAX_NOTES',
    'DEFAULT_MAX_PLANS', 'DELIVERY_REL', 'DEPENDS_RX', 'DEP_ID_RX', 'DIRTY_WT_RX',
    'DONE_STATES', 'Deps', 'FLOORS_IN_HOOKS', 'GATES', 'GATE_CACHE_MAX', 'GATE_CACHE_REL',
    'GATE_TIMEOUT_S', 'GateCache', 'HALT_REL', 'HEADROOM', 'HOLD_STATES', 'HOP_RX',
    'INBOX_REL', 'INFRA_RX', 'IN_FLIGHT', 'ITEMS_REL', 'Items', 'KEEP_REF',
    'LANE_TIMEOUT_S', 'LEGACY_LEDGER_REL', 'LIMIT_RX', 'LOCK_REL', 'LOOP_OWNER',
    'MARKER_RX', 'MAX_ATTEMPTS', 'MAX_ROUNDS', 'MERGE_LOCK_REL', 'NEED_RX', 'NOTE_HEAD',
    'NOTE_MAX', 'NOTE_STAMP', 'NO_ROADMAP', 'ORDERS_REL', 'OUTBOX_REL', 'PROGRESS_TASK',
    'PUSH_LAST_REL', 'PUSH_WORKER_REL', 'RED_TTL_S', 'RESOLVABLE', 'REVIEW_LOG_KEEP',
    'REVIEW_START_S', 'ROADMAP_REL', 'ROOT', 'ROUTES', 'ROUTE_EFFORTS', 'ROW_RX',
    'RUN_FIELDS', 'SESSION_TARGETS', 'SHELL_OPERATOR_CHARS', 'SKIP_TAGS', 'STOP',
    'SUITE_GATE_REL', 'TICK_S', 'TICK_TARGET_S', 'Tick', 'VERDICT_RX',
    'VERIFY_EXTRA', 'WATCH_REL', '_BREAKAWAY', '_DETACHED',
    '_NO_WINDOW', '_ROUTE_MODEL', '_gate_argv', '_gates', '_git', '_git_run',
    '_gitlock', '_launch', '_leak_pre_push', '_load_watch', '_norm_path',
    '_norm_words', '_owner', '_python', '_pythonw', '_run_gate', '_shell_operator',
    '_whole_suite', 'ascii_text', 'atomic_write', 'backoff_clear',
    'backoff_hit', 'backoff_until', 'base_kind', 'ci_gate_commands',
    'deep_dive_prompt', 'dependency_cycles', 'dispatchable', 'epoch_of', 'eta_label',
    'fix_prompt', 'flip_roadmap', 'handoff_items', 'handoff_prompt', 'hooks_path_problem',
    'inbox_prompt', 'is_duplicate', 'is_limit', 'iso', 'lane_worker', 'load_config',
    'load_routes', 'main', 'next_number', 'order_id', 'order_prompt', 'plan_depends',
    'plan_doc', 'plan_prompt', 'plan_titles', 'push_worker', 'queued_orders', 'read_json',
    'read_jsonl', 'render_checklist', 'resolve_item', 'resolve_prompt', 'resolve_roadmap',
    'review_worker', 'roadmap_flip_time', 'roadmap_rows', 'route_kind', 'route_kw',
    'session_done', 'session_orders', 'session_paths', 'spawn_block', 'tick',
    'title_tokens', 'tree_key', 'triage_spawn_kwargs', 'verify_prompt', 'with_hop',
)

TICK_METHODS = (
    '_merge', 'answer', 'answer_order', 'blocked', 'blocked_marker', 'carry_verdict',
    'checklist', 'commit', 'commit_refused', 'deep_dive_item', 'deliver_note', 'dest_inbox',
    'dirty', 'dispatch', 'drop_keep', 'extra_checks', 'finished', 'free_lanes', 'gate',
    'handled', 'held_worktrees', 'inbox', 'keep', 'launch_push', 'launch_review',
    'marker_checks', 'merge', 'orders', 'plan_deps', 'process', 'push', 'push_needed',
    'queue_order', 'reap_lost', 'rearm', 'recover_lane_dirty', 'redeliver',
    'resolve_roadmap_conflict', 'retry_refused', 'review_alive', 'review_crashed', 'route',
    'run', 'salvage', 'send_batches', 'settle_conflicts', 'spawn', 'step', 'work_list',
    'worktree_unusable', 'write', 'write_note',
)

MOVED = {
    "loop_base": ("CODE", "CONTROL_REL", "INBOX_REL", "ROUTES", "MARKER_RX", "_NO_WINDOW",
                  "ascii_text", "atomic_write", "with_hop", "read_json", "read_jsonl", "iso",
                  "epoch_of", "load_config", "route_kw", "is_limit", "Items", "next_number"),
    "loop_prompts": ("GATES", "NO_ROADMAP", "plan_prompt", "handoff_prompt", "deep_dive_prompt",
                     "verify_prompt", "fix_prompt", "resolve_prompt"),
    "loop_roadmap": ("roadmap_rows", "flip_roadmap", "plan_depends", "plan_doc", "base_kind",
                     "RUN_FIELDS", "resolve_item", "dependency_cycles", "roadmap_flip_time",
                     "resolve_roadmap", "handoff_items",
                     "title_tokens", "is_duplicate", "plan_titles", "dispatchable"),
    "loop_inbox": ("inbox_prompt", "order_id", "SESSION_TARGETS", "session_paths",
                   "order_prompt", "queued_orders", "session_orders", "session_done",
                   "FLOORS_IN_HOOKS", "triage_spawn_kwargs"),
    "loop_merge": ("GateCache",),
    "loop_review": ("ReviewMixin", "ROUND_LOG_CAP", "ROUND_LOG_MAX_FINDINGS"),
    "loop_work": ("WorkMixin",),
}
INBOX_METHODS = ("inbox", "handled", "answer", "send_batches", "dest_inbox", "deliver_note",
                 "redeliver", "write_note", "answer_order", "orders", "queue_order")
MERGE_METHODS = ("merge", "_merge", "carry_verdict", "keep", "drop_keep", "settle_conflicts",
                 "resolve_roadmap_conflict")
REVIEW_METHODS = ("process", "log_round", "blocked_marker", "extra_checks", "changed_names",
                  "order_checks", "marker_checks", "commit", "commit_refused", "salvage",
                  "retry_refused")
WORK_METHODS = ("rearm", "plan_deps", "work_list", "held_worktrees", "worktree_unusable",
                "free_lanes", "recover_lane_dirty", "dispatch", "deep_dive_item")
# Tick methods that stay in al_loop.py itself
STAY_METHODS = ("dirty", "gate", "spawn", "step", "finished", "checklist", "write", "run")
# monkeypatched on al_loop by tests (and called through al_loop globals)
SEAMS = ("ROOT", "_git_run", "_git", "_gate_argv")


def test_every_pre_split_name_is_still_on_al_loop():
    missing = [n for n in NAMES if not hasattr(al_loop, n)]
    assert missing == []


def test_moved_names_are_the_same_objects():
    import importlib
    for mod, names in MOVED.items():
        m = importlib.import_module(mod)
        for n in names:
            assert getattr(m, n) is getattr(al_loop, n), f"{mod}.{n}"


def test_tick_keeps_every_method_inbox_and_merge_via_mixins():
    import loop_inbox
    import loop_merge
    assert [m for m in TICK_METHODS if not hasattr(al_loop.Tick, m)] == []
    assert issubclass(al_loop.Tick, loop_inbox.InboxMixin)
    assert issubclass(al_loop.Tick, loop_merge.MergeMixin)
    for m in INBOX_METHODS:
        assert m in vars(loop_inbox.InboxMixin) and m not in vars(al_loop.Tick), m
    for m in MERGE_METHODS:
        assert m in vars(loop_merge.MergeMixin) and m not in vars(al_loop.Tick), m
    import loop_review
    import loop_work
    assert issubclass(al_loop.Tick, loop_review.ReviewMixin)
    assert issubclass(al_loop.Tick, loop_work.WorkMixin)


def test_review_and_work_methods_live_in_their_mixins():
    import loop_review
    import loop_work
    for m in REVIEW_METHODS:
        assert m in vars(loop_review.ReviewMixin) and m not in vars(al_loop.Tick), m
    for m in WORK_METHODS:
        assert m in vars(loop_work.WorkMixin) and m not in vars(al_loop.Tick), m
    for m in STAY_METHODS:
        assert m in vars(al_loop.Tick), m
    # every Tick method lives in exactly one place
    homes = (vars(al_loop.Tick), vars(loop_review.ReviewMixin), vars(loop_work.WorkMixin))
    for m in TICK_METHODS:
        if m in INBOX_METHODS or m in MERGE_METHODS:
            continue
        assert sum(m in h for h in homes) == 1, m


def test_patched_seams_stay_defined_in_al_loop():
    for n in SEAMS:
        v = getattr(al_loop, n)
        assert n in vars(al_loop)
        if callable(v):
            assert v.__module__ == "al_loop", n


def test_new_modules_never_import_al_loop():
    # al_loop runs as __main__; an `import al_loop` in a part would load a
    # second copy whose monkeypatch seams and globals diverge.
    for mod in MOVED:
        src = (ROOT / "tools" / f"{mod}.py").read_text(encoding="utf-8")
        assert "import al_loop" not in src and "from al_loop" not in src, mod


def test_al_loop_is_smaller():
    n = len((ROOT / "tools" / "al_loop.py").read_text(encoding="utf-8").splitlines())
    assert n < 1300, n  # LOOP-SPLIT-TICK: review and work methods moved out
