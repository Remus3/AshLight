"""Lint of the tracked repository-settings files under ops/github/.

The files are applied with gh by GP-13 and GP-15 (docs/plan/04-go-public.md,
"Repository settings"). Here they are only parsed and cross-checked against
the job names of the two workflows, so a renamed job cannot silently make a
required check unsatisfiable.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GH = ROOT / "ops" / "github"
INTEGRATION_ID = 15368
ADMIN_ROLE_ID = 5


def _load(name):
    return json.loads((GH / name).read_text(encoding="utf-8"))


def _job_names(workflow):
    """Map job key -> its `name:` value (plain line scan, stdlib only)."""
    lines = (ROOT / ".github" / "workflows" / workflow).read_text(
        encoding="utf-8").splitlines()
    out, in_jobs, key = {}, False, None
    for ln in lines:
        if re.match(r"^jobs:\s*$", ln):
            in_jobs = True
            continue
        if not in_jobs:
            continue
        if re.match(r"^\S", ln):
            break
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", ln)
        if m:
            key = m.group(1)
            continue
        m = re.match(r"^    name:\s*(.+?)\s*$", ln)
        if m and key and key not in out:
            out[key] = m.group(1).strip("\"'")
    return out


def _required_contexts():
    rules = _load("ruleset-main-checks.json")["rules"]
    rsc = [r for r in rules if r["type"] == "required_status_checks"]
    assert len(rsc) == 1
    return rsc[0]["parameters"]["required_status_checks"]


def test_every_file_is_valid_json():
    for name in ("ruleset-main-protect.json", "ruleset-main-checks.json",
                 "ruleset-release-tags.json", "security.json",
                 "branch-protection-fallback.json"):
        assert isinstance(_load(name), dict), name


def test_only_the_checks_ruleset_has_a_bypass_actor():
    assert _load("ruleset-main-protect.json")["bypass_actors"] == []
    assert _load("ruleset-release-tags.json")["bypass_actors"] == []
    actors = _load("ruleset-main-checks.json")["bypass_actors"]
    assert actors == [{"actor_id": ADMIN_ROLE_ID,
                       "actor_type": "RepositoryRole",
                       "bypass_mode": "always"}]


def test_ruleset_shapes():
    for name, target, rules in (
        ("ruleset-main-protect.json", "branch",
         {"deletion", "non_fast_forward"}),
        ("ruleset-release-tags.json", "tag",
         {"deletion", "non_fast_forward", "update"}),
    ):
        d = _load(name)
        assert d["target"] == target and d["enforcement"] == "active"
        assert {r["type"] for r in d["rules"]} == rules
    assert _load("ruleset-release-tags.json")["conditions"]["ref_name"][
        "include"] == ["refs/tags/v*"]
    assert _load("ruleset-main-protect.json")["conditions"]["ref_name"][
        "include"] == ["~DEFAULT_BRANCH"]


def test_required_contexts_equal_the_workflow_job_names():
    ci = _job_names("ci.yml")
    guard = _job_names("fleet-identity-guard.yml")
    expected = {ci["test"], guard["fleet-identity-guard"]}
    got = {c["context"] for c in _required_contexts()}
    assert got == expected
    fb = _load("branch-protection-fallback.json")
    assert set(fb["required_status_checks"]["contexts"]) == expected


def test_each_required_check_has_the_actions_integration_id():
    for c in _required_contexts():
        assert c["integration_id"] == INTEGRATION_ID, c


def test_test_newest_is_not_required():
    ci = _job_names("ci.yml")
    assert ci.get("test-newest") == "test-newest"
    got = {c["context"] for c in _required_contexts()}
    fb = set(_load("branch-protection-fallback.json")
             ["required_status_checks"]["contexts"])
    assert "test-newest" not in got and "test-newest" not in fb


def test_fallback_protection_shape():
    fb = _load("branch-protection-fallback.json")
    assert fb["enforce_admins"] is False
    assert fb["allow_force_pushes"] is False
    assert fb["allow_deletions"] is False


def test_security_settings_enabled():
    sa = _load("security.json")["security_and_analysis"]
    assert sa["secret_scanning"]["status"] == "enabled"
    assert sa["secret_scanning_push_protection"]["status"] == "enabled"
    # Decision 0087: non-provider patterns and validity checks stay off.
    assert sa["secret_scanning_non_provider_patterns"]["status"] == "disabled"
    assert sa["secret_scanning_validity_checks"]["status"] == "disabled"


def test_code_scanning_default_setup():
    """Decision 0087: GitHub-managed CodeQL default setup, no workflow."""
    cs = _load("security.json")["code_scanning_default_setup"]
    assert cs["state"] == "configured"
    assert cs["query_suite"] == "default"
    assert sorted(cs["languages"]) == [
        "actions", "javascript-typescript", "python"]
    assert cs["required_check"] is False
    assert cs["workflow_file"] is False
    wf = ROOT / ".github" / "workflows"
    assert not any("codeql" in p.name.lower() for p in wf.iterdir())
    checks = json.dumps(_load("ruleset-main-checks.json")).lower()
    assert "codeql" not in checks


def test_files_name_no_owner_or_repository():
    for p in GH.glob("*.json"):
        txt = p.read_text(encoding="utf-8")
        assert "github.com" not in txt and "AshLight" not in txt, p.name
