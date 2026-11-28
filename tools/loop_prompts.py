"""AL loop lane prompts (plan 107 split of tools/al_loop.py, which
re-exports every name here). Stdlib only."""

from loop_base import MAX_ROUNDS, next_number, next_research_number  # noqa: F401


# ---------------------------------------------------------------- prompts

# DS-REVIEW-HOOK (design 0003, adjudicator ruling): a UI change is reviewed
# by the design-reviewer agent before the lane finishes; the warn-only
# pre-commit reminder is tools/design_gate.py.
DESIGN_RULE = ("Design review: if your change touches web/, app/overlay/, app/shared/ "
               "or the card and event text package server/al/text/, run the "
               "design-reviewer agent "
               "(.claude/agents/design-reviewer.md) in the foreground on your diff, fix "
               "every S1 and S2 it reports, and append one line to "
               "docs/design/reviews.log: 'YYYY-MM-DD | scope=<paths> | verdict=<PASS|PASS "
               "WITH FINDINGS|FAIL> S1=<n> S2=<n> S3=<n> S4=<n> | <row id> | "
               "audit=<docs/design file or ->'.")

# Plan 096: producers run touched tests only; the loop runs the authoritative
# gates (ops/loop/gates.txt, whole suite included) once on the finished tree.
# Plan 101: a headless lane works inline (nested background agents only added
# waits).
GATES = ("Gates before you finish: the test files your change touched or added green "
         "(targeted, e.g. `python -m pytest -q tests/test_x.py`); run `python "
         "tools/test_select.py` for your diff and run its run-ungated command as "
         "printed (the ungated list, file-named), and leave its gated list to the "
         "loop's own gates (decision 0060, wave gate policy); `node --test` on the "
         "app/ test files you touched if you changed app/, and `python "
         "tools/leak_sweep.py --staged` clean. Do NOT run the whole pytest suite: the "
         "loop runs the authoritative gates (ops/loop/gates.txt: whole pytest suite, "
         "npm test, leak sweep) once on your finished tree and sends any failure back "
         "to you. Python stays standard library only. Every authored file ASCII + LF "
         "(tests/test_ascii_lf.py); no absolute machine path, drive letter, account id, "
         "email or sibling tree name in a tracked file. The game ToS floor in CLAUDE.md "
         "is absolute (no game memory, injection, DirectX hooks, packets, game files or "
         "input to the game; clipboard / screen only per AshLight hotkey press; read-only "
         "public GETs with a truthful User-Agent; robots.txt and X-Rate-Limit headers "
         "respected). Do NOT commit, do NOT edit CLAUDE.md, AL-NEXT-SESSION.txt or "
         "ops/fleet_kit/. Any deviation from the row's ACCEPT goes into a "
         "docs/decisions/ entry or your final reply (decision, alternatives, why, "
         "reverses if) - adjudicate it yourself, never wait. Write the v7 checklist "
         "(FLEET item 13 d) into your progress JSON "
         "ops/loop/control/progress/{task}.json: the FLEET item 12 fields plus "
         "\"checklist\": [{{\"id\", \"task\", \"state\", \"eta_s\"}}, ...] - "
         "remaining steps only, ASCII, updated after each step. Work inline in this "
         "run: do not start background sub-agents or background shell commands and "
         "wait on them; run each step in the foreground. Name any helper or scratch "
         "script after your task ({task}_*.py), never a generic name like prog.py. "
         + DESIGN_RULE)


NO_ROADMAP = ("Do NOT edit ROADMAP.md: the loop flips your row in main when "
              "it merges (parallel lanes editing it collided). ")


def plan_prompt(item):
    brief = item.get("text") or item["title"]
    return (f"You are an AshLight (AL) build lane in a detached git worktree. Read "
            f"CLAUDE.md first. Task: ROADMAP.md row {item['id']} - {brief} "
            f"(an optional longer brief: docs/plan/briefs/{item['id']}.md). Meet its ACCEPT "
            "line - TDD, stdlib only for Python. End your final reply with one line "
            "`RESULT: <what you did; for a bug, the root cause and the fix>` - it goes "
            "into the commit body (AUDIT-LOOP-COMMIT-MSG). "
            + NO_ROADMAP + GATES.format(task=f"p{item['id']}-build"))


def handoff_prompt(item):
    return ("You are an AshLight (AL) build lane in a detached git worktree. Read "
            "CLAUDE.md first. Work this hand-off item: " + item["text"] + " If it needs "
            "no repo change, change nothing and say why in one line. "
            + NO_ROADMAP + GATES.format(task=item["id"]))


# DIVE-FLOOR (decision 0050, ruling Q-07): a dive has no WebFetch or
# WebSearch; its only sources are these, and every fetch is the allow-listed
# tools/webfetch.py.
DIVE_SOURCES = ("Sources, and no others: (1) text the operator pasted into the repo; "
                "(2) public non-GGG repositories through the documented GitHub API "
                "(https://api.github.com/repos/...); (3) GGG's API Reference and Data "
                "Exports pages only (https://www.pathofexile.com/developer/docs/reference "
                "and /developer/docs/data). You have no WebFetch or WebSearch tool: fetch "
                "every page with `python tools/webfetch.py get <url>` (check a URL first "
                "with `python tools/webfetch.py check <url>`); it refuses every other "
                "GGG page, the trade site, poe2db and wiki hosts, and it sends nothing "
                "while web data is off - then write the research from sources already in "
                "the repo and say so. Never work around a refusal. ")


def deep_dive_prompt(root, date, max_plans, today_titles, items_root=None, exclude=None):
    """Idle mode: Path of Exile 2 research, read-only. New work is proposed as
    ROADMAP.md rows (the one exception to NO_ROADMAP). The note number skips
    every open dive's claimed number (RES-DIVE-NUMBER-COLLISION)."""
    rn = next_research_number(root, items_root, exclude)
    titles = "; ".join(f"{k} {v}" for k, v in sorted(today_titles.items()))
    return ("You are the AshLight (AL) deep-dive lane (idle mode) in a detached git "
            "worktree. Read CLAUDE.md and docs/research/0001-ggg-tool-policy.md first. "
            "Research, read-only and unauthenticated, robots.txt respected, a truthful "
            "User-Agent, no login and no POESESSID: Path of Exile 2 changes since the "
            "last deep-dive. " + DIVE_SOURCES + "Topics: changes to GGG's API "
            "Reference and Data Exports (endpoints, fields, X-Rate-Limit rules), "
            "Client.txt log format changes found in public repositories or "
            "operator-pasted text, and community tools worth learning from (ideas only; "
            "GPL / AGPL / NC code is never copied). Write "
            f"docs/research/{rn:04d}-deep-dive-{date}.md (every claim with its source URL "
            "and access date) and add it to docs/research/README.md. Propose "
            f"AT MOST {max_plans} new ROADMAP.md rows, each ONE line "
            "'- [ ] ID (lane) title. ACCEPT: ...' (ID upper-case words joined by '-', "
            "lane build / data / review), appended under the matching lane section. "
            "Do not duplicate an existing row: " + titles + ". "
            "Write no code. " + GATES.format(task="deep-dive"))


def verify_prompt(item, rnd, tree=None):
    """Plan 096: the loop's gates already ran green on exactly this tree; the
    verifier reviews and does not re-run pytest (VERIFY_EXTRA has none)."""
    on = f" (tree {tree[:12]})" if tree else ""
    # plan 163: a FIX's ordered files missing from the diff is a FAIL
    order = ("For this order: list every ordered file (one the note orders changed); "
             "one that "
             "is missing from the diff and not named in a BLOCKED / NOT-APPLICABLE "
             "bullet of its 'Order <id> - blocked items' ROADMAP section is a FAIL. "
             if item.get("kind") == "order" else "")
    return (f"You are the AL review-lane verifier, refute round {rnd}/{MAX_ROUNDS}. This "
            f"worktree's uncommitted diff (git status, git diff HEAD) implements: "
            f"{item['label']}. Read-only: never edit. The loop's authoritative gates "
            f"(whole pytest suite, npm test, leak sweep) ran green on exactly this "
            f"tree{on}: do not re-run pytest. " + order + "Check the diff against the "
            "row's ACCEPT line and its tests, the game ToS floor in CLAUDE.md, ASCII + "
            "LF, and no machine path. A diff touching web/, app/overlay/, app/shared/ "
            "or the server/al/text/ event text without a new docs/design/reviews.log "
            "line (design-reviewer verdict with S1=0 S2=0) is a FAIL. End with exactly one line 'VERDICT: PASS' or "
            "'VERDICT: FAIL', then numbered findings for a FAIL.")


def fix_prompt(item, rnd, findings):
    return (f"You are the AL producer answering refute round {rnd}/{MAX_ROUNDS} for "
            f"{item['label']} in this worktree. Fix every finding below, or record why "
            "it stands (decision, alternatives, why, reverses if) in a docs/decisions/ "
            "entry. " + GATES.format(task="fix")
            + "\n\nFindings:\n" + "\n".join(findings)[:8000])


def resolve_prompt(item):
    """Plan 058: the lane worker has already started the merge of the kept
    lane commit onto current main in the lane's worktree."""
    ref = item["keep_ref"]
    return ("You are an AshLight (AL) resolve lane in a detached git worktree. Read "
            f"CLAUDE.md first. The loop could not merge {item['label']} into main: a merge "
            "conflict. Before you started, the loop ran `git merge --no-ff --no-commit "
            f"{ref}` (the kept lane commit) onto current main in THIS worktree; `git "
            "status` lists the unmerged paths. Resolve every conflict keeping BOTH sides' "
            "features (main's newer work and the lane's), leave no conflict marker, and "
            "record decision / alternatives / why for each non-trivial resolution in your "
            "final reply. Leave the merge uncommitted: the loop "
            "verifies, commits and merges it. " + NO_ROADMAP
            + GATES.format(task=f"p{item['id']}-resolve"))
