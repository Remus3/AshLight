"""GP-05 (F-013, OPEN-14): the CI workflows stay pinned, read-only and offline.

Text parse only (stdlib, no YAML library): .github/workflows/ci.yml is the
text of docs/plan/04-go-public.md GP-05 plus the floating, NOT required job
`test-newest`; .github/workflows/fleet-identity-guard.yml is a byte copy of
the kit file; requirements-dev.txt is hash pinned for --require-hashes.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF_DIR = ROOT / ".github" / "workflows"
CI = WF_DIR / "ci.yml"
GUARD = WF_DIR / "fleet-identity-guard.yml"
KIT_GUARD = ROOT / "ops" / "fleet_kit" / "fleet_identity_guard.yml"
REQS = ROOT / "requirements-dev.txt"
ATTRS = ROOT / ".gitattributes"

PINNED_RX = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d+(?:\.\d+)*$")
# docs/plan/04 GP-05: the required job keeps these strings exactly.
FIXED_PY = '"3.11"'
FIXED_NODE = '"22.12.0"'
PIP_STEP = "python -m pip install --require-hashes -r requirements-dev.txt"
NPM_STEP = "npm ci --prefix app --ignore-scripts"


def _text(path):
    return path.read_bytes().decode("ascii")


def _workflows():
    return [CI, GUARD]


def _jobs(text):
    """{job id: block text} of the top-level `jobs:` map (2-space job ids)."""
    lines = text.split("\n")
    start = lines.index("jobs:")
    jobs, cur = {}, None
    for line in lines[start + 1:]:
        if line and not line.startswith(" "):
            break
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if m:
            cur = m.group(1)
            jobs[cur] = []
        elif cur is not None:
            jobs[cur].append(line)
    return {k: "\n".join(v) for k, v in jobs.items()}


def _field(block, key, indent=4):
    """The value of a job-level `key:` (job keys sit at 4 spaces)."""
    pat = "(?m)^" + " " * indent + re.escape(key) + r":[ \t]*(.*?)\s*$"
    m = re.search(pat, block)
    return m.group(1) if m else None


def _all(block, key):
    """Every value of `key:` anywhere in the block, in order."""
    return re.findall(r"(?m)^\s*" + re.escape(key) + r":[ \t]*(.*?)\s*$", block)


def _runs(block):
    """The run commands of a job, in order (block scalars joined by newline)."""
    out, lines, i = [], block.split("\n"), 0
    while i < len(lines):
        m = re.match(r"^(\s*)(?:-\s+)?run:\s*(.*?)\s*$", lines[i])
        i += 1
        if not m:
            continue
        if m.group(2) in ("|", ">", "|-", ">-"):
            ind, body = len(m.group(1)), []
            while i < len(lines) and (not lines[i].strip()
                                      or len(lines[i]) - len(lines[i].lstrip()) > ind):
                body.append(lines[i].strip())
                i += 1
            out.append("\n".join(b for b in body if b))
        else:
            out.append(m.group(2))
    return out


def test_files_exist_ascii_lf():
    for p in _workflows() + [REQS]:
        raw = p.read_bytes()
        raw.decode("ascii")
        assert b"\r" not in raw, p.name


def test_every_uses_is_pinned_by_full_sha_with_tag_comment():
    seen = 0
    for p in _workflows():
        for line in _text(p).split("\n"):
            if re.match(r"^\s*(?:-\s+)?uses:", line):
                ref = line.split("uses:", 1)[1].strip()
                assert PINNED_RX.match(ref), f"{p.name}: unpinned {line.strip()!r}"
                seen += 1
    assert seen >= 4


def test_same_action_same_pin_across_workflows():
    pins = {}
    for p in _workflows():
        for m in re.finditer(r"uses:\s*([\w.-]+/[\w./-]+)@([0-9a-f]{40}) # (v\S+)", _text(p)):
            pins.setdefault(m.group(1), set()).add((m.group(2), m.group(3)))
    assert pins and all(len(v) == 1 for v in pins.values()), pins


def test_top_level_permissions_exactly_contents_read():
    for p in _workflows():
        text = _text(p)
        m = re.search(r"(?m)^permissions:[ \t]*\n((?:[ \t]+.*\n?)*)", text)
        assert m, f"{p.name}: no top-level permissions"
        body = [ln.strip() for ln in m.group(1).split("\n") if ln.strip()]
        assert body == ["contents: read"], (p.name, body)
        # no job widens it
        assert len(re.findall(r"(?m)^\s*permissions:", text)) == 1, p.name


def test_no_secrets_no_pull_request_target_no_web_data():
    for p in _workflows():
        text = _text(p)
        for bad in ("secrets.", "pull_request_target", "web_data"):
            assert bad not in text, f"{p.name}: {bad}"


def test_ci_calls_no_ggg_or_poe_ninja_host():
    text = _text(CI).lower()
    for host in ("pathofexile.com", "poe.ninja", "grindinggear", "poe2db", "poewiki"):
        assert host not in text, host
    assert "http://" not in text and "https://" not in text


def test_job_test_on_windows_2025_with_fixed_versions():
    jobs = _jobs(_text(CI))
    t = jobs["test"]
    assert _field(t, "name") == "test"
    assert _field(t, "runs-on") == "windows-2025"
    assert _field(t, "continue-on-error") is None
    assert _all(t, "python-version") == [FIXED_PY]
    assert _all(t, "node-version") == [FIXED_NODE]


def test_job_test_newest_floats_and_may_fail():
    jobs = _jobs(_text(CI))
    n = jobs["test-newest"]
    assert _field(n, "name") not in (None, "test")
    assert _field(n, "name") == "test-newest"
    assert _field(n, "continue-on-error") == "true"
    assert _all(n, "python-version") and _all(n, "python-version") != [FIXED_PY]
    assert _all(n, "node-version") and _all(n, "node-version") != [FIXED_NODE]


def test_test_newest_runs_the_same_install_steps_as_test():
    jobs = _jobs(_text(CI))
    t, n = _runs(jobs["test"]), _runs(jobs["test-newest"])
    for step in (PIP_STEP, NPM_STEP):
        assert t.count(step) == 1 and n.count(step) == 1, step
    assert t == n  # same steps; only the two version strings differ


def test_test_newest_is_the_only_floating_job():
    jobs = _jobs(_text(CI))
    assert set(jobs) == {"test", "test-newest"}
    for jid, block in jobs.items():
        if jid == "test-newest":
            continue
        assert set(_all(block, "python-version")) <= {FIXED_PY}, jid
        assert set(_all(block, "node-version")) <= {FIXED_NODE}, jid


def test_every_job_sets_al_ci_and_nothing_else_does():
    # decision 0080: AL_CI=1 (timing budgets skip, test waits widen) is set
    # in the job env of ci.yml only; the guard workflow never sets it.
    jobs = _jobs(_text(CI))
    for jid, block in jobs.items():
        assert _all(block, "AL_CI") == ['"1"'], jid
    assert _text(CI).count("AL_CI") == len(jobs)
    assert "AL_CI" not in _text(GUARD)


def test_no_matrix_so_the_required_context_stays_test():
    text = _text(CI)
    assert not re.search(r"(?m)^\s*(strategy|matrix):", text)


def test_python_is_the_setup_python_exe_not_a_venv_launcher():
    # Session 7 (GP-04): tests/test_procs.py is red under a venv launcher and
    # green on the real 3.11 exe, so CI runs the setup-python interpreter as is.
    text = _text(CI)
    for bad in ("-m venv", "virtualenv", "\\Scripts\\", "/Scripts/", "activate"):
        assert bad not in text, bad
    for jid, block in _jobs(text).items():
        assert "actions/setup-python@" in block, jid
        runs = _runs(block)
        assert "python -m pytest -q" in runs, jid


def test_guard_is_byte_copy_of_kit_file():
    assert GUARD.read_bytes() == KIT_GUARD.read_bytes()


def test_guard_copy_is_never_normalised():
    lines = _text(ATTRS).split("\n")
    assert ".github/workflows/fleet-identity-guard.yml -text" in lines


def _requirements():
    """[(logical line)] of requirements-dev.txt, continuations joined."""
    logical, cur = [], ""
    for line in _text(REQS).split("\n"):
        if line.lstrip().startswith("#"):
            continue
        if line.rstrip().endswith("\\"):
            cur += line.rstrip()[:-1] + " "
            continue
        cur += line
        if cur.strip():
            logical.append(" ".join(cur.split()))
        cur = ""
    assert not cur.strip()
    return logical


def _req_ok(req):
    """True when a logical line is `name==version` plus only sha256 hashes."""
    m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==(\S+)\s+(.*)$", req)
    if not m:
        return False
    hashes = re.findall(r"--hash=sha256:([0-9a-f]+)", m.group(3))
    rest = re.sub(r"--hash=sha256:[0-9a-f]{64}(?![0-9a-f])", "", m.group(3)).strip()
    return bool(hashes) and all(len(h) == 64 for h in hashes) and not rest


def test_every_requirement_is_exact_and_hash_pinned():
    reqs = _requirements()
    names = []
    for req in reqs:
        assert _req_ok(req), f"not an exact pin with sha256 hashes: {req!r}"
        names.append(req.split("==", 1)[0].lower())
    assert "pytest" in names
    assert len(names) == len(set(names))


def test_requirement_check_refuses_bad_lines():
    good = "pluggy==1.7.0 --hash=sha256:" + "a" * 64
    assert _req_ok(good)
    assert not _req_ok("pluggy==1.7.0")
    assert not _req_ok("pluggy>=1.7 --hash=sha256:" + "a" * 64)
    assert not _req_ok("pluggy==1.7.0 --hash=sha256:" + "a" * 63)
    assert not _req_ok("pluggy==1.7.0 --hash=md5:" + "a" * 32)
