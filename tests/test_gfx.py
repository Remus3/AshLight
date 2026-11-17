"""GFX-ADVISOR: hardware parse and settings advice on fixture profiles.

Every profile below is invented (common retail model names, no serials, no
host data). The advisor is RECOMMEND ONLY: it never opens a file.
"""

import ast
import http.client
import json
import threading
from pathlib import Path

import pytest

from server.al import gfx
from server.al.core import Core
from server.al.http import serve

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "f" * 48
GiB = 1024 ** 3


def raw_profile(gpu_name, vram_bytes, ram_gb, threads, res=(1920, 1080), hz=60, extra=()):
    gpus = [{"Name": gpu_name, "AdapterRAM": min(vram_bytes or 0, 4293918720) or None,
             "CurrentHorizontalResolution": res[0], "CurrentVerticalResolution": res[1],
             "CurrentRefreshRate": hz}] + list(extra)
    return {"cpu": {"Name": "Example 6-Core Processor", "NumberOfCores": threads // 2,
                    "NumberOfLogicalProcessors": threads},
            "system": {"TotalPhysicalMemory": ram_gb * GiB},
            "gpus": gpus,
            "vram": [{"name": gpu_name, "bytes": vram_bytes}]}


HIGH = raw_profile("NVIDIA GeForce RTX 4070", int(11.94 * GiB), 32, 16, (2560, 1440), 165)
MEDIUM = raw_profile("AMD Radeon RX 6600", 8 * GiB, 16, 6)
LOW_IGPU = raw_profile("Intel(R) UHD Graphics 620", None, 8, 4, (1366, 768), 60)
UNDER_MIN = raw_profile("NVIDIA GeForce GTX 950", 2 * GiB, 6, 2)
ARC = raw_profile("Intel(R) Arc(TM) A750 Graphics", 8 * GiB, 16, 6)


def advice(raw):
    hw = gfx.parse(raw)
    return hw, gfx.recommend(hw)


def setting(adv, name):
    return next(s["value"] for s in adv["settings"] if s["setting"] == name)


def test_high_profile():
    hw, adv = advice(HIGH)
    assert hw["gpu"]["vram_gb"] == 12 and hw["gpu"]["vendor"] == "nvidia"
    assert hw["ram_gb"] == 32 and hw["cpu"]["threads"] == 16
    assert hw["display"] == {"width": 2560, "height": 1440, "refresh_hz": 165}
    assert adv["tier"] == "high" and adv["warnings"] == []
    assert setting(adv, "Display Mode") == "Windowed Fullscreen"
    assert setting(adv, "Resolution") == "2560x1440"
    assert setting(adv, "Foreground FPS Cap") == "165"
    assert setting(adv, "Lighting") == "Shadows and Global Illumination"
    assert setting(adv, "Upscale Mode") == "Off"
    assert setting(adv, "Texture Quality") == "High"


def test_medium_profile_uses_fsr_and_shadows_only():
    _, adv = advice(MEDIUM)
    assert adv["tier"] == "medium"  # 8 GB card, but only 6 processor threads
    assert setting(adv, "Texture Quality") == "High"
    _, adv = advice(raw_profile("AMD Radeon RX 6500 XT", 4 * GiB, 16, 12))
    assert adv["tier"] == "medium"
    assert setting(adv, "Upscale Mode") == "FSR (Quality)"
    assert setting(adv, "Lighting") == "Shadows Only"
    assert setting(adv, "Shadow + GI Quality") == "Medium"
    assert setting(adv, "Dynamic Resolution") == "Disabled"
    assert setting(adv, "Texture Quality") == "Medium"


def test_low_integrated_profile():
    hw, adv = advice(LOW_IGPU)
    assert hw["gpu"]["integrated"] is True and hw["gpu"]["vram_gb"] is None
    assert adv["tier"] == "low"
    assert setting(adv, "Dynamic Resolution") == "Enabled"
    assert setting(adv, "Shadow + GI Quality") == "Low"
    assert any("built-in graphics" in w for w in adv["warnings"])


def test_under_minimum_warns():
    _, adv = advice(UNDER_MIN)
    assert adv["tier"] == "low"
    text = " ".join(adv["warnings"])
    assert "6 GB of memory is under the game's minimum of 8 GB." in text
    assert "2 GB of video memory is under the game's minimum of 3 GB." in text
    assert "2 processor threads" in text
    assert setting(adv, "Texture Quality") == "Low"


def test_upscaler_by_vendor():
    assert setting(advice(ARC)[1], "Upscale Mode") == "XeSS (Quality)"
    rtx = raw_profile("NVIDIA GeForce RTX 3050", 4 * GiB, 16, 12)
    assert setting(advice(rtx)[1], "Upscale Mode") == "DLSS (Quality)"
    gtx = raw_profile("NVIDIA GeForce GTX 1660", 6 * GiB, 16, 12)
    assert setting(advice(gtx)[1], "Upscale Mode") == "FSR (Quality)"


def test_dedicated_card_beats_igpu_and_virtual_adapters():
    extra = [{"Name": "Intel(R) UHD Graphics 770", "AdapterRAM": 1073741824,
              "CurrentHorizontalResolution": None},
             {"Name": "Microsoft Remote Display Adapter"},
             {"Name": "Example Virtual Display", "CurrentHorizontalResolution": 1600,
              "CurrentVerticalResolution": 900, "CurrentRefreshRate": 60}]
    hw, _ = advice(raw_profile("NVIDIA GeForce RTX 4060", 8 * GiB, 16, 12, extra=extra))
    assert hw["gpu"]["name"] == "NVIDIA GeForce RTX 4060"
    assert hw["display"]["width"] == 1920
    assert all("Microsoft" not in g["name"] for g in hw["gpus"])


def test_bad_or_missing_data_never_raises():
    for raw in (None, {}, {"gpus": "x", "vram": 5, "cpu": [], "system": None},
                {"gpus": [{"Name": "X", "AdapterRAM": "lots"}]}):
        hw = gfx.parse(raw)
        adv = gfx.recommend(hw)
        assert adv["settings"][0]["value"] == "Windowed Fullscreen"
    assert gfx.recommend({})["tier"] == "unknown"


def test_advisor_reads_once_and_reports_failure():
    calls = []

    def runner():
        calls.append(1)
        return HIGH
    a = gfx.Advisor(runner=runner, clock=lambda: 100.0)
    one, two = a.get(), a.get()
    assert len(calls) == 1 and one == two and one["ok"] and one["read_at"] == 100.0
    bad = gfx.Advisor(runner=lambda: None).get()
    assert bad["ok"] is False and bad["hardware"] is None
    assert bad["error"] == "AshLight could not read this computer's hardware."
    assert bad["advice"]["settings"][0]["value"] == "Windowed Fullscreen"

    def boom():
        raise RuntimeError("x")
    assert gfx.Advisor(runner=boom).get()["ok"] is False


def test_recommend_only_never_opens_files():
    """ToS floor: no file opened at all (so none under the game's folders),
    and the query names no path but the display adapter registry key."""
    src = (ROOT / "server" / "al" / "gfx.py").read_text(encoding="ascii")
    tree = ast.parse(src)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert "open" not in names and not {"read_text", "read_bytes", "write_text",
                                        "write_bytes", "open"} & attrs
    assert "Path" not in names and "pathlib" not in src
    for word in ("Path of Exile", "production_Config", "Documents", ".ini", "Steam"):
        assert word not in gfx.PS_SCRIPT


@pytest.mark.server
def test_api_gfx_token_and_payload(tmp_path):
    log = tmp_path / "Client.txt"
    log.write_bytes(b"")
    core = Core(runtime=tmp_path / "rt", log_path=str(log), poll_s=0.05)
    srv = serve(core, TOKEN, port=0, web_root=ROOT / "web",
                tokens_css=ROOT / "ops" / "fleet_kit" / "tokens.css")
    srv.gfx = gfx.Advisor(runner=lambda: MEDIUM)
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    try:
        def get(token):
            conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
            h = {"Host": f"127.0.0.1:{srv.port}"}
            if token:
                h["X-AL-Token"] = token
            conn.request("GET", "/api/gfx", headers=h)
            r = conn.getresponse()
            body = r.read()
            conn.close()
            return r.status, body
        assert get(None)[0] == 401
        status, body = get(TOKEN)
        doc = json.loads(body)
        assert status == 200 and doc["ok"] and doc["hardware"]["gpu"]["vram_gb"] == 8
        assert doc["advice"]["settings"][0]["setting"] == "Display Mode"
    finally:
        srv.stop()
        core.close()
