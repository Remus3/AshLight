"""TEST-CLEAN-CLONE: one port rule for the core, run.ps1, keepalive and the
overlay (env AL_PORT, then config/local.json "port", then 8960)."""

from pathlib import Path

from server.al import keepalive, ports

ROOT = Path(__file__).resolve().parents[1]


def test_default_is_the_block_base():
    assert ports.resolve({}, {}) == ports.AL_PORT == 8960
    assert ports.resolve({}, {"port": None}) == 8960


def test_env_wins_over_config():
    assert ports.resolve({"AL_PORT": "8963"}, {"port": 8962}) == 8963


def test_config_port_used_without_env():
    assert ports.resolve({}, {"port": 8962}) == 8962
    assert ports.resolve({"AL_PORT": ""}, {"port": "8964"}) == 8964


def test_out_of_block_or_junk_is_ignored():
    assert ports.resolve({"AL_PORT": "80"}, {}) == 8960
    assert ports.resolve({"AL_PORT": "x"}, {"port": 8961}) == 8961
    assert ports.resolve({}, {"port": True}) == 8960
    assert ports.resolve({}, {"port": 9000}) == 8960


def test_keepalive_parser_defers_to_resolve():
    assert keepalive.build_parser().parse_args([]).port is None


def test_run_ps1_uses_resolve_and_passes_the_port_on():
    text = (ROOT / "scripts" / "run.ps1").read_text(encoding="ascii")
    assert "ports.resolve(" in text and "ports.AL_PORT)" not in text
    assert "[int]$Port = 0" in text
    assert "AL_PORT = [string]$port" in text  # overlay + keepalive's core
    assert "'--port', [string]$port" in text


def test_overlay_reads_the_same_sources():
    text = (ROOT / "app" / "main.js").read_text(encoding="utf-8")
    assert "process.env.AL_PORT" in text and "cfg.port" in text
