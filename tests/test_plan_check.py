"""tools/plan_check.py: one test per check on a synthetic plan, the ROADMAP
rows (wrap, BLOCKED text), wave --json, and the real docs/plan/packages.json
when it exists."""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import plan_check  # noqa: E402


def pkg(pid, wave=1, **kw):
    p = {
        "id": pid, "title": f"Package {pid}", "goal": "Do one thing.",
        "units": [f"U-{pid}"], "files": [f"server/al/{pid.lower()}.py"],
        "new_files": [], "integrator_edits": [],
        "tests": [f"tests/test_{pid.lower()}.py"],
        "accept": f"python -m pytest -q tests/test_{pid.lower()}.py passes.",
        "zero_click": "Runs from the loop tick with no player click.",
        "size": "S", "est_min": 20, "deps": [], "serial_group": "",
        "agent": "builder", "isolation": "worktree", "lane": "build",
        "design_review": False, "blocked": None, "operator_act": "",
        "notes": "", "wave": wave,
    }
    p.update(kw)
    return p


def base_plan():
    packages = [pkg("A1", 1), pkg("B2", 2, deps=["A1"]), pkg("C3", 2)]
    return {
        "schema": 1, "generated": "2026-11-18",
        "integrator_files": list(plan_check.INTEGRATOR_FILES),
        "hotspots": ["server/al/state.py"],
        "waves": [
            {"n": 1, "title": "First", "goal": "g", "merge_order": ["A1"],
             "gate": "suite green"},
            {"n": 2, "title": "Second", "goal": "g", "merge_order": ["B2", "C3"],
             "gate": "suite green"},
        ],
        "packages": packages,
        "coverage": {"U-A1": ["A1"], "U-B2": ["B2"], "U-C3": ["C3"],
                     "U-OLD": "done: landed in session 40",
                     "U-NO": "not_adopted: out of scope",
                     "U-OP": "operator: physical act"},
    }


def find(plan, pid):
    return next(p for p in plan["packages"] if p["id"] == pid)


def problems(plan):
    return plan_check.check_plan(plan)


def write(tmp_path, plan):
    f = tmp_path / "packages.json"
    f.write_text(json.dumps(plan), encoding="utf-8", newline="\n")
    return f


def test_base_plan_passes(tmp_path, capsys):
    assert problems(base_plan()) == []
    assert plan_check.main(["check", "--file", str(write(tmp_path, base_plan()))]) == 0
    assert capsys.readouterr().out.strip() == "plan_check: ok 3 packages, 2 waves"


def test_check_exit_1_one_line_per_problem(tmp_path, capsys):
    plan = base_plan()
    find(plan, "A1")["lane"] = "nope"
    find(plan, "C3")["size"] = "XL"
    assert plan_check.main(["check", "--file", str(write(tmp_path, plan))]) == 1
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2


def test_unreadable_and_bad_json(tmp_path, capsys):
    assert plan_check.main(["check", "--file", str(tmp_path / "none.json")]) == 1
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert plan_check.main(["check", "--file", str(bad)]) == 1
    out = capsys.readouterr().out
    assert "cannot read" in out and "invalid JSON" in out


def test_required_fields_present():
    plan = base_plan()
    del find(plan, "A1")["accept"]
    del plan["coverage"]
    got = problems(plan)
    assert "package A1: missing field accept" in got
    assert "plan: missing field coverage" in got


def test_fields_typed():
    plan = base_plan()
    find(plan, "A1")["est_min"] = "20"
    find(plan, "A1")["design_review"] = "no"
    find(plan, "A1")["files"] = "server/al/a1.py"
    plan["waves"][0]["n"] = "1"
    got = problems(plan)
    assert "package A1: field est_min must be an integer" in got
    assert "package A1: field design_review must be a boolean" in got
    assert "package A1: field files must be a list of strings" in got
    assert any("wave 1: field n must be an integer" == x for x in got)


def test_schema_version_and_ascii():
    plan = base_plan()
    plan["schema"] = 2
    find(plan, "A1")["notes"] = "caf\u00e9"
    got = problems(plan)
    assert "plan: schema 2 is not 1" in got
    assert any("non-ASCII" in x for x in got)


def test_ids_unique():
    plan = base_plan()
    plan["packages"].append(pkg("A1", 1, files=["x/other.py"], units=["U-A1"]))
    assert "package A1: duplicate id" in problems(plan)


def test_ids_loop_safe():
    plan = base_plan()
    for bad in ("a1", "A1-", "A_1", "A1 B"):
        plan2 = copy.deepcopy(plan)
        find(plan2, "A1")["id"] = bad
        assert any("not loop-safe" in x for x in problems(plan2)), bad


def test_paths_repo_relative():
    plan = base_plan()
    drive = "C" + ":" + "/x.py"  # built, so the leak sweep sees no drive path
    find(plan, "A1")["files"] = ["server\\al\\a1.py", "/abs.py", drive, "a/../b.py"]
    got = [x for x in problems(plan) if x.startswith("package A1: files")]
    assert len(got) == 4


def test_dep_is_a_package_id():
    plan = base_plan()
    find(plan, "B2")["deps"] = ["A1", "ZZ9"]
    assert "package B2: dep ZZ9 is not a package id" in problems(plan)


def test_no_dependency_cycle():
    plan = base_plan()
    for p in plan["packages"]:
        p["wave"] = 99
    plan["waves"] = [{"n": 99, "title": "Parked", "goal": "g",
                      "merge_order": ["A1", "B2", "C3"], "gate": "none"}]
    find(plan, "A1")["deps"] = ["B2"]
    got = problems(plan)
    assert any(x.startswith("dependency cycle:") and "A1" in x and "B2" in x
               for x in got)
    find(plan, "A1")["deps"] = ["A1"]
    assert "dependency cycle: A1 -> A1" in problems(plan)


def test_dep_in_strictly_earlier_wave():
    plan = base_plan()
    find(plan, "C3")["deps"] = ["B2"]
    assert "package C3: dep B2 is in wave 2, not before wave 2" in problems(plan)


def test_parked_wave_is_exempt_from_wave_order():
    plan = base_plan()
    plan["packages"].append(pkg("P9", 99, deps=["C3"], units=[],
                                files=["server/al/c3.py"], serial_group="",
                                blocked={"on": "x", "who": "operator", "unblock": "y"}))
    plan["packages"].append(pkg("Q9", 99, units=[], files=["docs/q.md"]))
    find(plan, "P9")["deps"] = ["Q9"]
    plan["waves"].append({"n": 99, "title": "Parked", "goal": "g",
                          "merge_order": ["P9", "Q9"], "gate": "none"})
    assert problems(plan) == []
    find(plan, "A1")["deps"] = ["Q9"]
    assert "package A1: dep Q9 is in wave 99, not before wave 1" in problems(plan)


def test_no_shared_path_inside_a_wave():
    plan = base_plan()
    find(plan, "C3")["new_files"] = ["server/al/b2.py"]
    assert "wave 2: B2 and C3 both touch server/al/b2.py" in problems(plan)
    # the same path in different waves is fine
    plan = base_plan()
    find(plan, "B2")["files"] = ["server/al/a1.py"]
    assert problems(plan) == []


def test_no_shared_serial_group_inside_a_wave():
    plan = base_plan()
    find(plan, "B2")["serial_group"] = "state"
    find(plan, "C3")["serial_group"] = "state"
    assert "wave 2: B2 and C3 share serial_group state" in problems(plan)
    find(plan, "A1")["serial_group"] = "other"
    find(plan, "C3")["serial_group"] = "other"
    assert problems(plan) == []


def test_no_integrator_file_in_files_or_new_files():
    plan = base_plan()
    find(plan, "A1")["files"] = ["ROADMAP.md"]
    find(plan, "B2")["new_files"] = ["docs/plan/README.md"]
    got = problems(plan)
    assert any("integrator file ROADMAP.md in files" in x for x in got)
    assert any("integrator file docs/plan/README.md in new_files" in x for x in got)


def test_integrator_edits_name_only_integrator_files():
    plan = base_plan()
    find(plan, "A1")["integrator_edits"] = [
        {"file": "ROADMAP.md", "change": "flip the A1 row"},
        {"file": "server/al/state.py", "change": "nope"},
        {"file": "CLAUDE.md", "change": " "},
        {"file": "CLAUDE.md"},
    ]
    got = [x for x in problems(plan) if "integrator_edits" in x]
    assert len(got) == 3
    assert any("server/al/state.py, not an integrator file" in x for x in got)


def test_tests_accept_zero_click_non_empty():
    plan = base_plan()
    find(plan, "A1")["tests"] = []
    find(plan, "A1")["accept"] = "  "
    find(plan, "A1")["zero_click"] = ""
    got = problems(plan)
    for key in ("tests", "accept", "zero_click"):
        assert f"package A1: {key} is empty" in got


def test_size_and_est_min():
    plan = base_plan()
    find(plan, "A1")["size"] = "XL"
    find(plan, "B2")["est_min"] = 91
    got = problems(plan)
    assert "package A1: size 'XL' not in S M L" in got
    assert "package B2: est_min 91 outside 1..90" in got


def test_lane_and_isolation():
    plan = base_plan()
    find(plan, "A1")["lane"] = "deploy"
    find(plan, "A1")["isolation"] = "container"
    got = problems(plan)
    assert "package A1: lane 'deploy' not in build data review" in got
    assert "package A1: isolation 'container' not in worktree none" in got


def test_blocked_fields_and_parked_wave():
    plan = base_plan()
    find(plan, "C3")["blocked"] = {"on": "GGG reply", "who": "operator"}
    got = problems(plan)
    assert "package C3: blocked needs a non-empty unblock" in got
    assert "package C3: blocked but in wave 2, not 99" in got


def test_merge_order_is_exactly_the_wave_packages():
    plan = base_plan()
    plan["waves"][1]["merge_order"] = ["B2", "B2", "A1"]
    got = problems(plan)
    assert "wave 2: merge_order lists B2 twice" in got
    assert "wave 2: merge_order names A1, not a package of this wave" in got
    assert "wave 2: package C3 missing from merge_order" in got


def test_package_wave_must_be_listed():
    plan = base_plan()
    find(plan, "C3")["wave"] = 5
    assert "package C3: wave 5 is not a listed wave" in problems(plan)


def test_every_unit_in_coverage():
    plan = base_plan()
    find(plan, "A1")["units"] = ["U-A1", "U-NEW"]
    find(plan, "C3")["units"] = ["U-B2"]
    got = problems(plan)
    assert "package A1: unit U-NEW missing from coverage" in got
    assert "package C3: coverage U-B2 does not name it" in got


def test_coverage_lists_name_existing_packages():
    plan = base_plan()
    plan["coverage"]["U-X"] = ["A1", "GONE"]
    plan["coverage"]["U-Y"] = []
    got = problems(plan)
    assert "coverage U-X: 'GONE' is not a package id" in got
    assert "coverage U-Y: empty package list" in got


def test_coverage_string_prefixes():
    plan = base_plan()
    plan["coverage"]["U-S"] = "later: maybe"
    plan["coverage"]["U-N"] = 3
    got = problems(plan)
    assert any(x.startswith("coverage U-S: string must start with") for x in got)
    assert "coverage U-N: must be a package list or a string" in got


def test_non_object_inputs_do_not_crash():
    assert problems([]) == ["plan: top level must be a JSON object"]
    plan = base_plan()
    plan["packages"].append("junk")
    plan["waves"].append(7)
    got = problems(plan)
    assert "packages[3]: must be an object" in got
    assert "waves[2]: must be an object" in got


def test_rows_order_wrap_and_blocked(tmp_path, capsys):
    plan = base_plan()
    long = "python -m pytest -q " + " ".join(f"tests/test_part{i}.py" for i in range(12))
    find(plan, "C3")["accept"] = long + " passes"
    plan["waves"][1]["merge_order"] = ["C3", "B2"]
    plan["packages"].append(pkg("P9", 99, units=[], files=["docs/p9.md"],
                                lane="review", title="Parked work.",
                                blocked={"on": "GGG app registration",
                                         "who": "operator",
                                         "unblock": "GGG opens registration."}))
    plan["waves"].append({"n": 99, "title": "Parked", "goal": "g",
                          "merge_order": ["P9"], "gate": "none"})
    f = write(tmp_path, plan)
    assert plan_check.main(["rows", "--file", str(f)]) == 0
    out = capsys.readouterr().out
    assert out.isascii()
    lines = out.splitlines()
    assert all(len(ln) <= 100 for ln in lines)
    heads = [ln.split()[3] for ln in lines if ln.startswith("- [ ] ")]
    assert heads == ["A1", "C3", "B2", "P9"]
    for ln in lines:
        assert ln.startswith("- [ ] ") or (ln.startswith("  ") and ln[2] != " ")
    joined = " ".join(ln.strip() for ln in lines)
    assert "- [ ] A1 (build) Package A1. ACCEPT: python -m pytest -q" in joined
    assert "ZERO-CLICK: Runs from the loop tick with no player click." in joined
    assert (len([ln for ln in lines if not ln.startswith("- [ ] ")]) >= 1)
    assert ("- [ ] P9 (review) Parked work. ACCEPT:" in joined)
    assert joined.endswith("BLOCKED: GGG app registration; unblocks when GGG opens"
                           " registration (operator).")
    assert plan_check.main(["rows", "--file", str(f), "--wave", "2"]) == 0
    heads = [ln.split()[3] for ln in capsys.readouterr().out.splitlines()
             if ln.startswith("- [ ] ")]
    assert heads == ["C3", "B2"]
    assert plan_check.main(["rows", "--file", str(f), "--wave", "7"]) == 1


def test_rows_refuse_an_invalid_plan(tmp_path, capsys):
    plan = base_plan()
    find(plan, "A1")["lane"] = "x"
    assert plan_check.main(["rows", "--file", str(write(tmp_path, plan))]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "lane" in captured.err


def test_wave_json(tmp_path, capsys):
    f = write(tmp_path, base_plan())
    assert plan_check.main(["wave", "2", "--file", str(f), "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["n"] == 2 and info["gate"] == "suite green"
    assert [p["id"] for p in info["packages"]] == ["B2", "C3"]
    b2 = info["packages"][0]
    for key in ("files", "deps", "tests", "agent", "size", "design_review"):
        assert key in b2
    assert b2["deps"] == ["A1"] and b2["design_review"] is False
    assert plan_check.main(["wave", "2", "--file", str(f)]) == 0
    text = capsys.readouterr().out
    assert text.startswith("wave 2: Second") and "deps: A1" in text
    assert plan_check.main(["wave", "8", "--file", str(f), "--json"]) == 1


def test_parked_wave_is_exempt_from_shared_paths_and_groups():
    plan = base_plan()
    block = {"on": "x", "who": "operator", "unblock": "y"}
    plan["packages"].append(pkg("P9", 99, units=[], files=["web/index.html"],
                                serial_group="web", blocked=dict(block)))
    plan["packages"].append(pkg("Q9", 99, units=[], files=["web/index.html"],
                                serial_group="web", blocked=dict(block)))
    plan["waves"].append({"n": 99, "title": "Parked", "goal": "g",
                          "merge_order": ["P9", "Q9"], "gate": "none"})
    assert problems(plan) == []


def test_owner_values_and_loop_rules():
    plan = base_plan()
    find(plan, "A1")["owner"] = "loop"
    find(plan, "B2")["owner"] = "session"
    find(plan, "C3")["owner"] = "robot"
    got = problems(plan)
    assert "package C3: owner 'robot' not in session loop" in got
    assert "package B2: owner session but dep A1 is owned by the loop" in got
    # a loop package may depend on a session package
    plan = base_plan()
    find(plan, "A1")["owner"] = "session"
    find(plan, "B2")["owner"] = "loop"
    find(plan, "C3")["owner"] = "session"
    assert problems(plan) == []
    # a loop package is never blocked or parked
    find(plan, "B2")["blocked"] = {"on": "x", "who": "operator", "unblock": "y"}
    find(plan, "B2")["wave"] = 99
    plan["waves"][1]["merge_order"] = ["C3"]
    plan["waves"].append({"n": 99, "title": "Parked", "goal": "g",
                          "merge_order": ["B2"], "gate": "none"})
    got = problems(plan)
    assert "package B2: owner loop but blocked" in got
    assert "package B2: owner loop but in the parked wave" in got


def test_sessions_list():
    plan = base_plan()
    plan["sessions"] = [{"n": 1, "waves": [1, 2]}]
    assert problems(plan) == []
    plan["sessions"] = [{"n": 1, "waves": [1]}, {"n": 1, "waves": [1, 7, 99]},
                        {"n": 2, "waves": []}, {"waves": [2]}]
    got = problems(plan)
    assert "session 1: duplicate session number" in got
    assert "session 1: wave 1 is already in session 1" in got
    assert "session 1: wave 7 is not a listed wave" in got
    assert "session 1: names the parked wave" in got
    assert "session 2: no waves" in got
    assert "sessions[3]: needs an integer n and a list of wave numbers" in got
    assert "wave 2: holds session work but is in no session" in got
    # a wave that holds only loop packages needs no session
    plan = base_plan()
    for p in plan["packages"]:
        p["owner"] = "loop" if p["wave"] == 2 else "session"
    plan["sessions"] = [{"n": 1, "waves": [1]}]
    assert problems(plan) == []
    plan["sessions"] = "none"
    assert "plan: field sessions must be a list" in problems(plan)


def test_rows_owner_tags_and_wave_owner(tmp_path, capsys):
    plan = base_plan()
    find(plan, "A1")["owner"] = "session"
    find(plan, "B2")["owner"] = "loop"
    find(plan, "C3")["owner"] = "session"
    plan["packages"].append(pkg("P9", 99, units=[], files=["docs/p9.md"], deps=["A1"],
                                owner="session",
                                blocked={"on": "a reply", "who": "operator",
                                         "unblock": "the reply is recorded"}))
    plan["waves"].append({"n": 99, "title": "Parked", "goal": "g",
                          "merge_order": ["P9"], "gate": "none"})
    f = write(tmp_path, plan)
    assert plan_check.main(["rows", "--file", str(f)]) == 0
    rows, cur = {}, None
    for ln in capsys.readouterr().out.splitlines():
        if ln.startswith("- [ ] "):
            cur = ln.split()[3]
            rows[cur] = ln
        else:
            rows[cur] += " " + ln.strip()
    assert rows["A1"].endswith("BLOCKED: session wave 1.") and "DEPENDS" not in rows["A1"]
    assert rows["B2"].endswith("DEPENDS: A1.") and "BLOCKED" not in rows["B2"]
    assert rows["C3"].endswith("BLOCKED: session wave 2.")
    assert rows["P9"].endswith("DEPENDS: A1. BLOCKED: a reply; unblocks when the reply is"
                               " recorded (operator).")
    assert "session wave" not in rows["P9"]
    assert plan_check.main(["wave", "2", "--file", str(f), "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert [p["owner"] for p in info["packages"]] == ["loop", "session"]
    assert plan_check.main(["wave", "2", "--file", str(f)]) == 0
    assert "owner loop" in capsys.readouterr().out


def test_real_plan_passes(capsys):
    if not plan_check.DEFAULT_FILE.exists():
        pytest.skip("docs/plan/packages.json not written yet")
    rc = plan_check.main(["check"])
    out = capsys.readouterr().out
    assert rc == 0, out
