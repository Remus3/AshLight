"""TC-PRESS-SAMPLES (decision 0045 amendment 2026-11-18): the dev-host
item-press sample part (server/al/theorycraft/cardparts/sample.py) and its
tool (tools/press_samples.py). Every item text here is the synthetic
tc_eval_fixtures text or invented in this file."""

import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import press_samples  # noqa: E402
from server.al import paths, settingsio  # noqa: E402
from server.al.core import Core  # noqa: E402
from server.al.theorycraft import cardparts  # noqa: E402
from server.al.theorycraft.cardparts import sample  # noqa: E402
from tc_eval_fixtures import ADVANCED_RING, RARE_GLOVES  # noqa: E402

CHATTY = ("Item Class: Rings\nRarity: Rare\nStorm Loop\nExample Ring\n--------\n"
          "+55 to maximum Life\n--------\n"
          "Note: ask Invented_Player9 for this one\n"
          "@InventedFriend hello\n"
          "@From InventedSeller: wtb ring for 5 exalted\n"
          "To InventedBuyer: sold, thanks\n")


@pytest.fixture(autouse=True)
def fresh_parts():
    cardparts.reset()
    yield
    cardparts.reset()


@pytest.fixture
def sidecar(tmp_path, monkeypatch):
    root = tmp_path / "sidecar"
    monkeypatch.setenv(paths.SIDECAR_ENV, str(root))
    return root


def _core(tmp_path, config=None):
    log = tmp_path / "Client.txt"
    if not log.exists():
        log.write_bytes(b"")
    cfg = tmp_path / "local.json"
    if config is not None:
        cfg.write_text(json.dumps(config), encoding="ascii")
    return Core(runtime=tmp_path / "rt", log_path=str(log), tail=False, poll_s=0.05,
                config_path=cfg)


def _files(root):
    return sorted(p for p in root.rglob("*") if p.is_file()) if root.exists() else []


def test_the_part_is_discovered_and_never_adds_a_value():
    assert sample in cardparts.parts()
    ctx = {"text": RARE_GLOVES, "config": lambda: {}}
    assert sample.compute(ctx) is None
    assert sample.words(None, {}, {"notes": []}) is None


@pytest.mark.parametrize("config", [None, {}, {"dev_press_samples": False},
                                    {"dev_press_samples": "true"},
                                    {"dev_press_samples": 1}])
def test_key_absent_or_not_true_writes_nothing(tmp_path, sidecar, config):
    core = _core(tmp_path, config)
    try:
        core.last_eval.run(RARE_GLOVES, "Gloves")
        assert "sample" not in core.state.snapshot()["eval"]["parts"]
    finally:
        core.close()
    assert _files(sidecar) == []


def test_key_true_saves_one_sanitized_candidate_in_tmp(tmp_path, sidecar):
    core = _core(tmp_path, {"dev_press_samples": True})
    try:
        core.last_eval.run(CHATTY, "Ring")
        core.last_eval.rerun()  # a re-score writes nothing new
        core.last_eval.run(CHATTY, "Ring")  # neither does a repeat press
        assert "sample" not in core.state.snapshot()["eval"]["parts"]
    finally:
        core.close()
    files = _files(tmp_path)
    written = [p for p in files if sidecar in p.parents and "press-samples" in p.parts]
    assert len(written) == 1
    assert written[0].parent == sidecar / "Scratch" / "press-samples"
    text = written[0].read_text(encoding="utf-8")
    assert "Invented" not in text and "@" in text
    assert sample.leaks(text) == []
    assert text.startswith("Item Class: Rings\nRarity: Rare\n")


def test_a_test_core_never_writes_outside_tmp_path(tmp_path, monkeypatch):
    # no test sidecar: under pytest the part refuses to write at all
    monkeypatch.delenv(paths.SIDECAR_ENV, raising=False)
    calls = []
    real_dir = sample.sample_dir
    monkeypatch.setattr(sample, "sample_dir", lambda *a: calls.append(1) or real_dir(*a))
    core = _core(tmp_path, {"dev_press_samples": True})
    try:
        core.last_eval.run(RARE_GLOVES, "Gloves")
    finally:
        core.close()
    assert calls == []
    assert sample.save(RARE_GLOVES) is None


def test_an_installed_copy_has_no_sample_folder(tmp_path):
    env = {paths.HOME_ENV: str(tmp_path / "home")}
    with pytest.raises(ValueError):
        sample.sample_dir(env)


def test_sanitizer_masks_note_at_names_and_whispers():
    out = sample.sanitize(CHATTY)
    assert "Invented_Player9" not in out and "Note: <masked>" in out
    assert "InventedFriend" not in out and "@<name> hello" in out
    assert "InventedSeller" not in out and "wtb" not in out
    assert "@From <masked>" in out
    assert "InventedBuyer" not in out and "sold" not in out
    assert "From <masked>: <masked>" in out or "To <masked>: <masked>" in out
    assert "+55 to maximum Life" in out  # item text itself is kept
    assert sample.leaks(out) == []
    assert set(sample.leaks(CHATTY)) == {"note", "at", "whisper"}


def test_sanitizer_keeps_a_price_note_and_plain_items():
    out = sample.sanitize(RARE_GLOVES)
    assert "Note: ~price 5 exalted" in out
    assert out == RARE_GLOVES
    ring = sample.sanitize(ADVANCED_RING)
    assert "\r" not in ring and sample.leaks(ring) == []
    assert sample.sanitize("") is None and sample.sanitize(None) is None
    assert len(sample.sanitize("x" * 20000)) <= sample.TEXT_MAX + 1
    assert "\x07" not in sample.sanitize("Item\x07 text")


def test_candidate_dir_is_bounded_to_50_files(sidecar):
    folder = sample.sample_dir()
    for i in range(sample.MAX_FILES + 5):
        sample.save(f"Item Class: Rings\nRarity: Magic\nInvented Ring {i}\n")
    assert len(sample.candidates(folder)) == sample.MAX_FILES == 50
    assert not list(folder.glob("*.tmp"))


def test_key_is_not_a_player_setting_and_never_exported():
    assert sample.KEY == "dev_press_samples"
    assert sample.KEY not in settingsio.ALLOWED
    doc = settingsio.export_doc({sample.KEY: True, "poll_ms": 250}, "0.0.0")
    assert sample.KEY not in json.dumps(doc)


def _candidate(sidecar, text):
    path = sample.save(text)
    assert path is not None
    return path


def test_promote_writes_only_the_rewritten_form(sidecar, tmp_path):
    path = _candidate(sidecar, ADVANCED_RING)
    dest = tmp_path / "fixtures"
    out = io.StringIO()
    rc = press_samples.main(["promote", path.stem, "--folder", str(path.parent),
                             "--dest", str(dest)], out=out)
    assert rc == 0, out.getvalue()
    fixture = (dest / path.name).read_text(encoding="ascii")
    original = path.read_text(encoding="utf-8")
    assert fixture != original
    assert fixture.isascii() and "\r" not in fixture
    assert "Storm Loop" not in fixture and "Example Ring" not in fixture
    assert "Lightning" not in fixture and "Hale" not in fixture
    assert fixture.count("\n") == original.count("\n")
    assert fixture.splitlines()[:2] == ["Item Class: Rings", "Rarity: Rare"]
    assert "(Tier: 3)" in fixture and "+55(50-59)" in fixture
    # a second promote of the same name refuses to overwrite
    assert press_samples.main(["promote", path.stem, "--folder", str(path.parent),
                               "--dest", str(dest)], out=io.StringIO()) == 1


def test_promote_refuses_a_candidate_that_still_matches_a_mask(sidecar, tmp_path):
    path = _candidate(sidecar, RARE_GLOVES)
    path.write_text(CHATTY, encoding="utf-8")  # hand-edited after capture
    with pytest.raises(press_samples.PromoteError, match="still matches"):
        press_samples.promote(path.stem, path.parent, tmp_path / "fx")
    assert not (tmp_path / "fx").exists()
    out = io.StringIO()
    assert press_samples.main(["check", "--folder", str(path.parent)], out=out) == 1
    assert "leaks" in out.getvalue()


def test_promote_refuses_a_verbatim_copy(sidecar, tmp_path):
    path = _candidate(sidecar, "Item Class: Rings\nRarity: Rare\n--------\nCorrupted\n")
    with pytest.raises(press_samples.PromoteError, match="verbatim"):
        press_samples.promote(path.stem, path.parent, tmp_path / "fx")


def test_promote_refuses_bad_names(sidecar, tmp_path):
    folder = sample.sample_dir()
    for name in ("../x", "", "a/b", "missing"):
        with pytest.raises(press_samples.PromoteError):
            press_samples.promote(name, folder, tmp_path / "fx")


def test_list_and_check(sidecar):
    _candidate(sidecar, RARE_GLOVES)
    folder = str(sample.sample_dir())
    out = io.StringIO()
    assert press_samples.main(["list", "--folder", folder], out=out) == 0
    assert "candidates: 1 of 50" in out.getvalue()
    out = io.StringIO()
    assert press_samples.main(["check", "--folder", folder], out=out) == 0
    assert "leaking: 0" in out.getvalue()
