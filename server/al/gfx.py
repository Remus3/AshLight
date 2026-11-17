"""GFX-ADVISOR: read this PC's hardware and recommend PoE2 graphics settings.

RECOMMEND ONLY (decision 0004 item 10, CLAUDE.md ToS floor): the player
applies the settings in game. This module never opens a file at all - not
the game's config, not anything under the game's folders - and never
touches the game process. Hardware comes from Windows' own CIM query and
the display adapter class key in the registry (VRAM; the CIM AdapterRAM
field stops at 4 GB), through one hidden `powershell.exe` run with a
timeout. Off Windows, or when the query fails, the panel says so.

The read happens on the first GET /api/gfx, which the dashboard sends when
the player opens the panel - a click on the dashboard, so the game is not
the focused window then - and is kept for the life of the core. Nothing is
written to disk; no serial number, host name or user name is read.

Setting names and the official specs: docs/research/0011-poe2-graphics.md.
"""

import json
import os
import re
import subprocess
import threading
import time

QUERY_TIMEOUT_S = 25
GB = 1024 ** 3

# Steam store page, PoE2 minimum specs (research 0011).
MIN_RAM_GB = 8
MIN_VRAM_GB = 3
MIN_THREADS = 4

PS_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$cpu = Get-CimInstance -ClassName Win32_Processor |
  Select-Object -First 1 Name, NumberOfCores, NumberOfLogicalProcessors
$cs = Get-CimInstance -ClassName Win32_ComputerSystem | Select-Object TotalPhysicalMemory
$gpus = @(Get-CimInstance -ClassName Win32_VideoController |
  Select-Object Name, AdapterRAM, CurrentHorizontalResolution,
    CurrentVerticalResolution, CurrentRefreshRate)
$key = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0*'
$vram = @(Get-ItemProperty -Path $key | ForEach-Object {
  [pscustomobject]@{ name = $_.DriverDesc; bytes = $_.'HardwareInformation.qwMemorySize' } })
[pscustomobject]@{ cpu = $cpu; system = $cs; gpus = $gpus; vram = $vram } |
  ConvertTo-Json -Depth 4 -Compress
"""

_INTEGRATED = re.compile(
    r"intel\(r\) (uhd|hd|iris)|intel (uhd|hd|iris)|^amd radeon\(tm\) graphics|"
    r"^amd radeon graphics|radeon\(tm\) vega|vega \d+ graphics|radeon \d{3}m", re.I)
_IGNORED = re.compile(r"microsoft basic|remote display|virtual|parsec|meta virtual", re.I)


def run_query(timeout=QUERY_TIMEOUT_S):
    """Raw CIM data as a dict, or None (not Windows, timeout, bad output)."""
    if os.name != "nt":
        return None
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive",
                            "-ExecutionPolicy", "Bypass", "-Command", PS_SCRIPT],
                           capture_output=True, text=True, timeout=timeout,
                           creationflags=flags, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        doc = json.loads(r.stdout or "")
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def _list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _gb(n, digits=0):
    if not n or n <= 0:
        return None
    return round(n / GB, digits) if digits else int(round(n / GB))


def vendor_of(name):
    n = (name or "").lower()
    if "nvidia" in n or "geforce" in n or "quadro" in n:
        return "nvidia"
    if "radeon" in n or n.startswith("amd"):
        return "amd"
    if "intel" in n:
        return "intel"
    return "other"


def parse(raw):
    """Clean hardware facts from run_query() output. Never raises."""
    raw = raw if isinstance(raw, dict) else {}
    cpu = raw.get("cpu") if isinstance(raw.get("cpu"), dict) else {}
    system = raw.get("system") if isinstance(raw.get("system"), dict) else {}
    vram = {}
    for v in _list(raw.get("vram")):
        if isinstance(v, dict) and v.get("name"):
            b = v.get("bytes")
            if isinstance(b, list):  # REG_BINARY on some drivers
                b = sum(int(x) << (8 * i) for i, x in enumerate(b) if isinstance(x, int))
            b = _int(b)
            if b:
                vram[str(v["name"]).strip().lower()] = b
    gpus = []
    for g in _list(raw.get("gpus")):
        if not isinstance(g, dict) or not (g.get("Name") or g.get("name")):
            continue
        name = re.sub(r"\s+", " ", str(g.get("Name") or g.get("name"))).strip()
        if _IGNORED.search(name):
            continue
        b = vram.get(name.lower()) or _int(g.get("AdapterRAM"))
        gpus.append({"name": name[:80], "vendor": vendor_of(name),
                     "integrated": bool(_INTEGRATED.search(name)),
                     # whole GB from 2 GB up (a 12 GB card reports 11.94)
                     "vram_gb": (_gb(b) if b >= 2 * GB else _gb(b, 1)) if b else None,
                     "width": _int(g.get("CurrentHorizontalResolution")),
                     "height": _int(g.get("CurrentVerticalResolution")),
                     "refresh_hz": _int(g.get("CurrentRefreshRate"))})
    # The game GPU: a dedicated card first, then the most VRAM.
    gpus.sort(key=lambda g: (g["integrated"], -(g["vram_gb"] or 0)))
    game = gpus[0] if gpus else None
    # The screen the game GPU drives; else any adapter that reports one.
    shown = game if game and game["width"] else next((g for g in gpus if g["width"]), None)
    return {
        "cpu": {"name": (re.sub(r"\s+", " ", str(cpu.get("Name") or "")).strip()[:80]
                         or None),
                "cores": _int(cpu.get("NumberOfCores")),
                "threads": _int(cpu.get("NumberOfLogicalProcessors"))},
        "ram_gb": _gb(_int(system.get("TotalPhysicalMemory"))),
        "gpu": game,
        "gpus": gpus,
        "display": ({"width": shown["width"], "height": shown["height"],
                     "refresh_hz": shown["refresh_hz"]} if shown else None),
    }


def tier_of(hw):
    """"low", "medium", "high", or "unknown" when the GPU is not known."""
    gpu = hw.get("gpu")
    if not gpu:
        return "unknown"
    vram = gpu.get("vram_gb") or 0
    ram = hw.get("ram_gb") or 0
    threads = (hw.get("cpu") or {}).get("threads") or 0
    if gpu.get("integrated") or vram < 4 or (ram and ram < 12):
        return "low"
    if vram >= 8 and (not threads or threads >= 8) and (not ram or ram >= 16):
        return "high"
    return "medium"


TIER_TEXT = {
    "low": "Light settings: this PC is near the game's minimum.",
    "medium": "Balanced settings: this PC handles the game well with a few trims.",
    "high": "High settings: this PC has room for the full lighting.",
    "unknown": "Balanced settings: AshLight could not read the graphics card.",
}


def _upscaler(gpu):
    name = (gpu or {}).get("name") or ""
    if (gpu or {}).get("vendor") == "nvidia" and "rtx" in name.lower():
        return "DLSS (Quality)", "your NVIDIA RTX card runs DLSS"
    if (gpu or {}).get("vendor") == "intel" and "arc" in name.lower():
        return "XeSS (Quality)", "your Intel Arc card runs XeSS"
    return "FSR (Quality)", "FSR runs on any graphics card"


def recommend(hw):
    """Pure: the advice for one hardware profile. Each setting is
    {setting, value, why}; `warnings` lists anything under the official
    minimum specs."""
    hw = hw or {}
    tier = tier_of(hw)
    gpu = hw.get("gpu") or {}
    disp = hw.get("display") or {}
    vram = gpu.get("vram_gb") or 0
    settings = []

    def add(setting, value, why):
        settings.append({"setting": setting, "value": value, "why": why})

    add("Display Mode", "Windowed Fullscreen",
        "the AshLight overlay can only sit above the game in this mode")
    if disp.get("width") and disp.get("height"):
        add("Resolution", f"{disp['width']}x{disp['height']}", "your screen's current resolution")
    else:
        add("Resolution", "your screen's native resolution", "sharpest picture")
    add("Renderer", "DirectX 12", "the game's default; try Vulkan if you see stutter")
    hz = disp.get("refresh_hz")
    if hz and hz >= 30:
        add("Foreground FPS Cap", str(hz), f"matches your {hz} Hz screen, so frames stay even")
    else:
        add("Foreground FPS Cap", "your screen's refresh rate", "frames stay even")
    add("V-Sync", "Off", "the FPS cap keeps frames even with less input delay")
    add("Background FPS Cap", "30", "saves power while you are in another window")
    add("Engine Multithreading", "Enabled", "turning it off costs a lot of FPS")
    if tier == "high":
        add("Upscale Mode", "Off", "this card renders at full resolution")
        add("Lighting", "Shadows and Global Illumination", "this card has room for it")
        add("Shadow + GI Quality", "High", "the best look at a steady frame rate")
        add("Dynamic Resolution", "Disabled", "keeps the picture sharp")
    else:
        up, why = _upscaler(gpu)
        add("Upscale Mode", up, why)
        add("Lighting", "Shadows Only",
            "global illumination is the setting that costs the most FPS")
        add("Shadow + GI Quality", "Low" if tier == "low" else "Medium",
            "the second biggest cost after the lighting mode")
        add("Dynamic Resolution", "Enabled" if tier == "low" else "Disabled",
            "keeps busy fights smooth" if tier == "low" else "keeps the picture sharp")
    if vram >= 8:
        add("Texture Quality", "High", f"{_num(vram)} GB of video memory is enough")
    elif vram >= 4:
        add("Texture Quality", "Medium", f"{_num(vram)} GB of video memory")
    elif vram:
        add("Texture Quality", "Low", f"only {_num(vram)} GB of video memory")
    else:
        add("Texture Quality", "Medium", "video memory unknown")

    warnings = []
    ram = hw.get("ram_gb")
    threads = (hw.get("cpu") or {}).get("threads")
    if ram and ram < MIN_RAM_GB:
        warnings.append(f"{ram} GB of memory is under the game's minimum of {MIN_RAM_GB} GB.")
    if vram and vram < MIN_VRAM_GB:
        warnings.append(f"{_num(vram)} GB of video memory is under the game's minimum "
                        f"of {MIN_VRAM_GB} GB.")
    if threads and threads < MIN_THREADS:
        warnings.append(f"{threads} processor threads is under the game's minimum.")
    if gpu.get("integrated"):
        warnings.append("This is a built-in graphics chip; expect low frame rates.")
    return {"tier": tier, "tier_text": TIER_TEXT[tier], "settings": settings,
            "warnings": warnings}


def _num(n):
    return str(int(n)) if float(n).is_integer() else str(n)


class Advisor:
    """Reads the hardware once (on the first get) and keeps the advice."""

    def __init__(self, runner=run_query, clock=time.time):
        self._runner = runner
        self._clock = clock
        self._lock = threading.Lock()
        self._doc = None

    def get(self):
        with self._lock:
            if self._doc is None:
                raw = None
                try:
                    raw = self._runner()
                except Exception:  # a broken query never breaks the core
                    raw = None
                if raw is None:
                    self._doc = {"ok": False, "read_at": self._clock(),
                                 "error": "AshLight could not read this computer's hardware.",
                                 "hardware": None, "advice": recommend({})}
                else:
                    hw = parse(raw)
                    self._doc = {"ok": True, "read_at": self._clock(), "error": None,
                                 "hardware": hw, "advice": recommend(hw)}
            return json.loads(json.dumps(self._doc))
