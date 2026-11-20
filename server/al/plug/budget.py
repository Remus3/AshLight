"""RUN-BUDGET-LOG-CORE (F-032, OPEN-03, OVL-BUDGET): the once-a-minute
budget log tick and its Checks row, through the plug seam (decision 0056).

attach() gives the core a budgetlog.Sampler writing budget.jsonl to the
sidecar Logs dir (a test core: its own tmp runtime dir, never the sidecar).
The tick costs one clock compare between rows. The Checks row reads
"AshLight uses N MB" from the last row (core + client + luajit), and adds
one sentence when that row broke a research 0048 budget. Only AshLight's
own processes are measured (server/al/budgetlog.py has the floor note).
"""

from .. import budgetlog, paths

ORDER = 800  # after the feature plugs, before debug (900)
ROW_ID = "budget"
LABEL = "Memory use"
OVER_TEXT = ("That is more than AshLight should use; the budget log keeps "
             "the figures.")


def log_path(core):
    if getattr(core, "_real", False):
        return paths.sidecar_dir("Logs") / budgetlog.FILE_NAME
    return core.runtime / budgetlog.FILE_NAME


def attach(core):
    core.budget_log = budgetlog.BudgetLog(log_path(core))
    core.budget_sampler = budgetlog.Sampler(core, core.budget_log)
    core.add_tick("tick_budget", lambda: core.budget_sampler.due())


def facts(core, now):
    log = getattr(core, "budget_log", None)
    row = log.last if log is not None else None
    if not row:
        return {"budget_mb": None, "budget_over": []}
    mb = row.get("total_mb")
    return {"budget_mb": mb, "budget_over": list(log.last_breaches)}


def detail_text(mb, over):
    text = f"AshLight uses {int(round(mb))} MB."
    return text + " " + OVER_TEXT if over else text


def rows(f, now):
    mb = f.get("budget_mb")
    if isinstance(mb, bool) or not isinstance(mb, (int, float)):
        return None
    over = [b for b in (f.get("budget_over") or ()) if isinstance(b, str)]
    return {"id": ROW_ID, "label": LABEL, "status": "note" if over else "pass",
            "detail": detail_text(mb, over)}
