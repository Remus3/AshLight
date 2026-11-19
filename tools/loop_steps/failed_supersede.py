"""LOOP-FAILED-PARK step (F-024, OPEN-36): a loop item in state `failed`
whose ROADMAP row is no longer open (flipped [x] or gone) becomes
`superseded`, a done state, so a stale failed record stops showing in every
checklist and the parked list once the row was finished another way (the 12
records of docs/plan/01-open-items.md L4). Its keep ref, if any, stays: the
WIP commit is never dropped by this step.

Only plan records (a resolve run of a plan row included: its base_kind is
plan) are rows; an order or deep-dive record has no ROADMAP row. An empty
row list (ROADMAP.md unreadable) supersedes nothing. Hermetic: it reads and
writes only the tick's own item records (tick.items)."""

STATE = "failed"
NEW_STATE = "superseded"


def _is_plan(rec):
    kind = rec.get("kind")
    return kind == "plan" or (kind == "resolve" and rec.get("base_kind", "plan") == "plan")


def post_work(tick, rows, work, skipped):
    if not rows:
        return None
    open_ids = {r.get("id") for r in rows if isinstance(r, dict) and r.get("open")}
    out = []
    for rec in tick.items.all().values():
        if rec.get("state") != STATE or not _is_plan(rec) or rec.get("id") in open_ids:
            continue
        rec.update(state=NEW_STATE, superseded_from=STATE)
        tick.items.put(rec)
        out.append(f"{rec['id']}: failed record superseded (row no longer open)")
    return out
