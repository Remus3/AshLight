"""DOCS-FRESH (AUTO-14, F-146): facts the docs quote match the tree.

The check is clean on this checkout; each fact has a fixture test on a temp
copy of the files it reads: changing the source alone (or breaking the doc)
fails and names each stale file.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import docs_fresh as df  # noqa: E402


def _copy(tmp_path):
    for rel in df.INPUTS:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dst)
    for src in (ROOT / "scripts").glob("*.ps1"):  # names README quotes
        shutil.copyfile(src, tmp_path / "scripts" / src.name)
    for rel_dir in df.INDEX_DIRS:  # the index fact lists these folders
        (tmp_path / rel_dir).mkdir(parents=True, exist_ok=True)
        for src in (ROOT / rel_dir).glob("*.md"):
            shutil.copyfile(src, tmp_path / rel_dir / src.name)
    for rel in df.Tree(ROOT).py_files(df.CORE_DIR):  # settings keys read
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dst)
    return tmp_path


def _edit(root, rel, old, new, count=1):
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, (rel, old)
    path.write_bytes(text.replace(old, new, count).encode("utf-8"))


def _named(problems):
    return set(df.stale_files(problems))


def test_check_is_clean_on_the_tree():
    assert df.check(ROOT) == []


def test_fixture_copy_is_clean(tmp_path):
    assert df.check(_copy(tmp_path)) == []


def test_every_fact_is_listed_once():
    names = [f.__name__ for f in df.FACTS]
    assert len(names) == len(set(names))
    assert all(n.startswith("fact_") for n in names)


def _electron_pin(root):
    pkg = json.loads((root / df.PKG_REL).read_text(encoding="utf-8"))
    for key in ("dependencies", "devDependencies"):
        if "electron" in pkg.get(key, {}):
            return key, pkg[key]["electron"]
    raise AssertionError("no electron dependency")


def test_electron_pin_change_names_each_stale_doc(tmp_path):
    root = _copy(tmp_path)
    _key, pin = _electron_pin(root)
    _edit(root, df.PKG_REL, f'"electron": "{pin}"', '"electron": "99.0.1"')
    problems = df.check(root)
    assert _named(problems) == {df.MAIN_JS_REL, df.STACK_REL}
    assert all("electron pin" in p for p in problems)


def test_electron_pin_cli_exit_1_names_files(tmp_path):
    root = _copy(tmp_path)
    _key, pin = _electron_pin(root)
    _edit(root, df.PKG_REL, f'"electron": "{pin}"', '"electron": "99.0.1"')
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "docs_fresh.py"), "check",
         "--root", str(root)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 1
    assert "app/main.js" in proc.stdout
    assert "docs/decisions/0002-stack.md" in proc.stdout


def test_cli_exit_0_on_the_tree():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "docs_fresh.py"), "check"],
        capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ok" in proc.stdout


def test_electron_measured_history_is_not_checked(tmp_path):
    root = _copy(tmp_path)
    path = root / df.STACK_REL
    path.write_bytes((path.read_text(encoding="utf-8")
                      + "\n## Measured\n\nexact pin `1.2.3` then.\n")
                     .encode("utf-8"))
    assert df.check(root) == []


def test_missing_disclaimer_fails(tmp_path):
    root = _copy(tmp_path)
    disclaimer = df.Tree(root).py_constants(df.INIT_REL)["DISCLAIMER"]
    _edit(root, df.README_REL, disclaimer, "Unofficial.")
    problems = df.check(root)
    assert _named(problems) == {df.README_REL}
    assert any("not-affiliated" in p for p in problems)


def test_wrong_port_block_names_readme(tmp_path):
    root = _copy(tmp_path)
    _edit(root, df.PORTS_REL, "PORT_BLOCK = (8960, 8979)",
          "PORT_BLOCK = (8960, 8978)")
    problems = df.check(root)
    assert _named(problems) == {df.README_REL}
    assert all("port block" in p for p in problems)


def test_wrong_default_port_names_readme(tmp_path):
    root = _copy(tmp_path)
    _edit(root, df.README_REL, "`port` (default 8960)", "`port` (default 8962)")
    assert _named(df.check(root)) == {df.README_REL}


def test_wrong_python_floor_names_readme(tmp_path):
    root = _copy(tmp_path)
    _edit(root, df.SETUP_REL, "[version]$pyVer -lt [version]'3.11'",
          "[version]$pyVer -lt [version]'3.12'")
    problems = df.check(root)
    assert _named(problems) == {df.README_REL}
    assert all("python floor" in p for p in problems)


def test_wrong_node_floor_names_readme(tmp_path):
    root = _copy(tmp_path)
    floor = df._setup_value(df.Tree(root), "node floor",
                            r"\$nodeFloor\s*=\s*'" + df._DOTTED + "'")[0]
    _edit(root, df.SETUP_REL, f"$nodeFloor = '{floor}'",
          "$nodeFloor = '24.0.0'")
    problems = df.check(root)
    assert _named(problems) == {df.README_REL}
    assert all("node floor" in p for p in problems)


def test_wrong_version_names_files(tmp_path):
    root = _copy(tmp_path)
    version = df.Tree(root).py_constants(df.INIT_REL)["VERSION"]
    _edit(root, df.INIT_REL, f'VERSION = "{version}"', 'VERSION = "9.9.9"')
    problems = df.check(root)
    assert _named(problems) == {df.PKG_REL, df.LOCK_REL}
    assert all("version" in p for p in problems)


def test_wrong_kit_version_names_files(tmp_path):
    root = _copy(tmp_path)
    path = root / df.MANIFEST_REL
    man = json.loads(path.read_text(encoding="utf-8"))
    man["version"] = int(man["version"]) + 1
    path.write_bytes(json.dumps(man).encode("ascii"))
    problems = df.check(root)
    assert df.DESIGN_REL in _named(problems)
    assert _named(problems) <= {df.DESIGN_REL, df.CLAUDE_REL}
    assert all("kit version" in p for p in problems)


def test_kit_version_quote_in_claude_md_is_optional(tmp_path):
    root = _copy(tmp_path)
    path = root / df.CLAUDE_REL
    path.write_bytes(b"# rules\n\nKit: the version in MANIFEST.json.\n")
    assert df.check(root) == []
    path.write_bytes(b"# rules\n\nKit: v1, vendored at ops/fleet_kit/.\n")
    assert _named(df.check(root)) == {df.CLAUDE_REL}


def test_missing_script_and_unknown_script_named(tmp_path):
    root = _copy(tmp_path)
    (root / "scripts" / "build.ps1").unlink()
    _edit(root, df.README_REL, "scripts\\setup.ps1 -TcCalc",
          "scripts\\setupx.ps1 -TcCalc")
    problems = df.check(root)
    assert _named(problems) == {"scripts/build.ps1", df.README_REL}
    assert any("setupx.ps1" in p for p in problems)


def test_missing_doc_file_is_named(tmp_path):
    root = _copy(tmp_path)
    (root / df.MAIN_JS_REL).unlink()
    assert _named(df.check(root)) == {df.MAIN_JS_REL}


def test_index_fact_joins_the_table():
    assert df.fact_index in df.FACTS


def test_unindexed_decision_names_its_readme(tmp_path):
    root = _copy(tmp_path)
    (root / df.DECISIONS_DIR / "0999-planted.md").write_bytes(
        b"# 0999 - Planted decision\n")
    (root / df.RESEARCH_DIR / "0998-planted.md").write_bytes(
        b"# 0998 - Planted research\n")
    problems = df.check(root)
    assert _named(problems) == {"docs/decisions/README.md",
                                "docs/research/README.md"}
    assert all("index" in p for p in problems)
    assert any("0999-planted.md" in p for p in problems)
    assert any("0998-planted.md" in p for p in problems)


def test_missing_index_readme_is_named(tmp_path):
    root = _copy(tmp_path)
    (root / df.RESEARCH_DIR / "README.md").unlink()
    assert _named(df.check(root)) == {"docs/research/README.md"}


def test_cli_bad_root_exits_2(tmp_path):
    assert df.main(["check", "--root", str(tmp_path / "nope")]) == 2


# ---------------------------------------------- TEST-DOCS-FACTS-UI facts

def test_ui_facts_join_the_table():
    for fact in (df.fact_default_hotkeys, df.fact_budgets,
                 df.fact_settings_keys, df.fact_tab_names):
        assert fact in df.FACTS


def test_changed_default_hotkey_names_readme_and_example(tmp_path):
    root = _copy(tmp_path)
    _edit(root, df.HOTKEYS_REL, '"eval": ("Alt+Shift+E",',
          '"eval": ("Alt+Shift+Q",')
    problems = df.check(root)
    assert _named(problems) == {df.README_REL, df.EXAMPLE_REL}
    assert all("default hotkey" in p for p in problems)
    assert any("Alt+Shift+Q" in p for p in problems)


def test_changed_toggle_hotkey_names_readme(tmp_path):
    root = _copy(tmp_path)
    _edit(root, df.HOTKEYS_REL, '"toggle": ("Alt+Shift+A",',
          '"toggle": ("Alt+Shift+O",')
    _edit(root, df.EXAMPLE_REL, '"overlay_toggle": "Alt+Shift+A"',
          '"overlay_toggle": ""')  # blank = the default: not a quote
    problems = df.check(root)
    assert _named(problems) == {df.README_REL}
    assert all("toggle hotkey" in p for p in problems)


def test_hotkey_fact_does_not_read_web_text(tmp_path):
    # OVL-KEYS-WEB prints the snapshot's keys in web/: no literal there.
    root = _copy(tmp_path)
    path = root / df.INDEX_HTML_REL
    path.write_bytes(path.read_text(encoding="utf-8")
                     .replace("Alt+Shift+E", '<span data-hotkey="eval"></span>')
                     .replace("Alt+Shift+A", '<span data-hotkey="toggle"></span>')
                     .encode("utf-8"))
    assert df.check(root) == []


def test_budget_values_read_from_the_budget_tests():
    values = df.budget_values(df.Tree(ROOT))
    for prefix, _scale in df._BUDGET_TESTS.values():
        assert sum(name.startswith(prefix) for name in values) == 1, prefix


def test_changed_budget_number_names_readme_and_stack(tmp_path):
    root = _copy(tmp_path)
    _edit(root, df.BUDGETS_REL, "fleet_test_guard.budget(0.05)",
          "fleet_test_guard.budget(0.06)")
    problems = df.check(root)
    assert _named(problems) == {df.README_REL, df.STACK_REL}
    assert all("tail burst budget" in p for p in problems)
    assert all("'60'" in p for p in problems)


def test_changed_idle_share_names_readme_and_stack(tmp_path):
    root = _copy(tmp_path)
    _edit(root, df.BUDGETS_REL, "share < 0.01 * fleet_test_guard",
          "share < 0.03 * fleet_test_guard")
    problems = df.check(root)
    assert _named(problems) == {df.README_REL, df.STACK_REL}
    assert all("core idle budget" in p for p in problems)


def test_tailer_idle_fact_reads_the_real_loop_body_budget(tmp_path):
    # BUDGET-RETIRE-TAILER-IDLE: B1 (the real loop body with the tailer
    # thread polling) owns the README's idle tailing figure.
    assert df._BUDGET_TESTS["tailer idle"][0] == "test_real_loop_body"
    root = _copy(tmp_path)
    _edit(root, df.BUDGETS_REL, "share < 0.005 * fleet_test_guard",
          "share < 0.008 * fleet_test_guard")
    problems = df.check(root)
    assert _named(problems) == {df.README_REL}
    assert all("tailer idle budget" in p for p in problems)
    assert any("'0.8'" in p for p in problems)


def test_changed_parse_budget_names_readme_only(tmp_path):
    root = _copy(tmp_path)
    _edit(root, df.BUDGETS_REL, "fleet_test_guard.budget(0.25)",
          "fleet_test_guard.budget(0.3)")
    problems = df.check(root)
    assert _named(problems) == {df.README_REL}
    assert any("'300'" in p for p in problems)


def test_settings_key_missing_from_readme_is_named(tmp_path):
    root = _copy(tmp_path)
    _edit(root, df.README_REL, " and `tc_calc` (the optional", " (the optional")
    problems = df.check(root)
    assert _named(problems) == {df.README_REL}
    assert any("`tc_calc` is not listed" in p for p in problems)


def test_new_example_key_needs_readme_and_a_core_read(tmp_path):
    root = _copy(tmp_path)
    _edit(root, df.EXAMPLE_REL, '"tc_calc": false',
          '"tc_calc": false,\n  "planted_key": 1')
    problems = df.check(root)
    assert _named(problems) == {df.README_REL, df.EXAMPLE_REL}
    assert all("planted_key" in p for p in problems)


def test_dev_keys_are_not_settings(tmp_path):
    # "loop" sits in the example file but is a firstrun.DEV_KEYS key.
    root = _copy(tmp_path)
    example = json.loads((root / df.EXAMPLE_REL).read_text(encoding="utf-8"))
    assert "loop" in example
    assert df.fact_settings_keys(df.Tree(root)) == []


def test_readme_naming_an_unknown_key_is_named(tmp_path):
    root = _copy(tmp_path)
    _edit(root, df.README_REL, "`port` (default 8960),",
          "`port` (default 8960), `colour_theme`,")
    problems = df.check(root)
    assert _named(problems) == {df.README_REL}
    assert any("`colour_theme`" in p for p in problems)


def test_renamed_tab_names_readme(tmp_path):
    root = _copy(tmp_path)
    _edit(root, df.INDEX_HTML_REL, 'tabindex="-1">Settings <span',
          'tabindex="-1">Options <span')
    problems = df.check(root)
    assert _named(problems) == {df.README_REL}
    assert all("tab names" in p for p in problems)
    assert any("'Settings'" in p for p in problems)


def test_tab_without_a_button_names_index_html(tmp_path):
    root = _copy(tmp_path)
    _edit(root, df.TABS_REL, '"run", "settings"]', '"run", "loot", "settings"]')
    assert _named(df.check(root)) == {df.INDEX_HTML_REL}


def test_tab_labels_follow_tabs_js_order():
    tabs = df.tab_labels(df.Tree(ROOT))
    assert tabs and all(label for _tab, label in tabs)
    assert ("settings", "Settings") in tabs
