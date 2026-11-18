"""docs/plan/09-operator-acts.md is the one batched operator ask (PLAN-LANDING).

It must name every package of docs/plan/packages.json whose operator_act is
not empty, every unit whose coverage starts with 'operator:', every qid of
docs/plan/findings.json operator_decisions beside the word 'Default', and
the entries OA-1 to OA-11; the floor questions A-01 and A-03 carry the word
'floor' and offer the strict answer first. gaps() is the one checker: the
real files must give no gap, and each rule is shown to fail on a cut copy.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs" / "plan" / "packages.json"
FINDINGS = ROOT / "docs" / "plan" / "findings.json"
ACTS = ROOT / "docs" / "plan" / "09-operator-acts.md"

OA_REQUIRED = tuple(f"OA-{n}" for n in range(1, 12))
FLOOR_QIDS = ("A-01", "A-03")
ID_CHARS = "A-Za-z0-9-"


def has_id(text, ident):
    """True when ident stands in text as a whole id (OA-1 is not in OA-10)."""
    return re.search(rf"(?<![{ID_CHARS}]){re.escape(ident)}(?![{ID_CHARS}])",
                     text) is not None


def entries(text):
    """{entry id: entry text} for every '### OA-<n> ...' entry of 09."""
    out = {}
    for block in re.split(r"(?m)^(?=### )", text):
        m = re.match(r"### (OA-\d+) [^\n]*\n", block)
        if m:
            out[m.group(1)] = re.split(r"(?m)^## ", block)[0]
    return out


def bullet(entry, label):
    """The text of the '- <label>...' bullet of an entry, joined to one line."""
    m = re.search(rf"(?ms)^- {re.escape(label)}\b(.*?)(?=^- |\Z)", entry)
    return " ".join(m.group(1).split()) if m else ""


def gaps(text, plan, findings):
    out = []
    for p in plan["packages"]:
        if p.get("operator_act") and not has_id(text, p["id"]):
            out.append(f"package {p['id']}: operator_act set, not named in 09")
    for unit, cov in plan["coverage"].items():
        if isinstance(cov, str) and cov.startswith("operator:") \
                and not has_id(text, unit):
            out.append(f"unit {unit}: operator coverage, not named in 09")
    ents = entries(text)
    for oa in OA_REQUIRED:
        if oa not in ents:
            out.append(f"{oa}: no entry heading in 09")
    for oa, body in sorted(ents.items()):
        if not bullet(body, "Default"):
            out.append(f"{oa}: entry without a Default bullet")
    default_lines = [ln for ln in text.splitlines() if "Default" in ln]
    for d in findings["operator_decisions"]:
        qid = d["qid"]
        if not any(has_id(ln, qid) for ln in default_lines):
            out.append(f"decision {qid}: not beside the word Default in 09")
    for qid in FLOOR_QIDS:
        mine = [b for b in ents.values() if has_id(b.split("\n", 1)[0], qid)]
        if len(mine) != 1:
            out.append(f"floor question {qid}: {len(mine)} entries, want 1")
            continue
        body = mine[0]
        if "floor" not in body.lower():
            out.append(f"floor question {qid}: the word floor is missing")
        steps = bullet(body, "Steps")
        if not steps.lstrip(": ").startswith("the strict answer first"):
            out.append(f"floor question {qid}: the strict answer is not first")
    return out


def load():
    return (ACTS.read_text(encoding="ascii"),
            json.loads(PLAN.read_text(encoding="utf-8")),
            json.loads(FINDINGS.read_text(encoding="utf-8")))


def test_operator_acts_file_has_no_gap():
    text, plan, findings = load()
    assert gaps(text, plan, findings) == []


def test_the_inputs_are_not_empty():
    # an empty plan or findings file would make the check above pass for
    # nothing; the numbers are floors, not pins
    _, plan, findings = load()
    acts = [p["id"] for p in plan["packages"] if p.get("operator_act")]
    units = [u for u, c in plan["coverage"].items()
             if isinstance(c, str) and c.startswith("operator:")]
    qids = [d["qid"] for d in findings["operator_decisions"]]
    assert len(acts) >= 30 and len(units) >= 5 and len(qids) >= 10
    assert set(FLOOR_QIDS) <= set(qids)


def test_whole_id_match():
    assert has_id("see OA-1, then", "OA-1")
    assert not has_id("see OA-10, then", "OA-1")
    assert not has_id("GP-09", "GP-0") and not has_id("XGP-09", "GP-09")
    assert has_id("(A-01):", "A-01") and not has_id("OA-01", "A-01")


def test_a_missing_package_unit_or_entry_is_a_gap():
    text, plan, findings = load()
    pid = next(p["id"] for p in plan["packages"] if p.get("operator_act"))
    cut = re.sub(rf"(?<![{ID_CHARS}]){re.escape(pid)}(?![{ID_CHARS}])",
                 "X", text)
    assert f"package {pid}: operator_act set, not named in 09" in gaps(
        cut, plan, findings)
    unit = next(u for u, c in plan["coverage"].items()
                if isinstance(c, str) and c.startswith("operator:"))
    cut = re.sub(rf"(?<![{ID_CHARS}]){re.escape(unit)}(?![{ID_CHARS}])",
                 "X", text)
    assert f"unit {unit}: operator coverage, not named in 09" in gaps(
        cut, plan, findings)
    cut = text.replace("### OA-11 ", "### OB-11 ")
    assert "OA-11: no entry heading in 09" in gaps(cut, plan, findings)


def test_a_decision_without_its_default_is_a_gap():
    text, plan, findings = load()
    cut = "\n".join(ln for ln in text.splitlines()
                    if not ("Default" in ln and has_id(ln, "Q-07")))
    got = gaps(cut, plan, findings)
    assert "decision Q-07: not beside the word Default in 09" in got
    more = dict(findings, operator_decisions=findings["operator_decisions"]
                + [{"qid": "Q-98"}])
    assert "decision Q-98: not beside the word Default in 09" in gaps(
        text, plan, more)


def test_a_floor_question_must_say_floor_and_put_the_strict_answer_first():
    text, plan, findings = load()
    ents = entries(text)
    for qid in FLOOR_QIDS:
        body = next(b for b in ents.values()
                    if has_id(b.split("\n", 1)[0], qid))
        soft = body.replace("the strict answer first: ", "either answer: ")
        assert soft != body
        got = gaps(text.replace(body, soft), plan, findings)
        assert f"floor question {qid}: the strict answer is not first" in got
        plain = re.sub(r"(?i)floor", "rule", body)
        got = gaps(text.replace(body, plain), plan, findings)
        assert f"floor question {qid}: the word floor is missing" in got
