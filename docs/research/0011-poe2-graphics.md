# 0011 - PoE2 graphics options and PC specs (GFX-ADVISOR input)

Date: 2026-11-17. Feeds ROADMAP GFX-ADVISOR (`server/al/gfx.py`). Read by a
web-research agent; every line says whether the fact was confirmed on the
cited page. No GGG page lists the whole Graphics menu, so most option labels
come from third-party guides and are marked as such. Labels may differ in
capitalisation from the live menu; a screenshot of the live Graphics tab
would settle them (open item below).

## Official specs (Steam store page, confirmed)

Source: https://store.steampowered.com/app/2694490 (accessed 2026-11-17).
- Minimum: Windows 10; Intel Core i7-7700 or AMD Ryzen 5 2500X; 8 GB RAM;
  GTX 960 (3 GB) / Intel Arc A380 / Radeon RX 470; at least 3 GB VRAM;
  DirectX 12; 100 GB storage.
- Recommended: Windows 10; Intel Core i5-10500 or AMD Ryzen 5 3700X; 16 GB
  RAM; RTX 2060 / Arc A770 / RX 5600 XT; DirectX 12; SSD recommended.
  Recommended VRAM is not stated.

`gfx.py` uses MIN_RAM_GB 8 and MIN_VRAM_GB 3 from this page. MIN_THREADS 4
is AshLight's own floor (the minimum CPUs are 4-core parts), not a GGG
number.

## Option labels

- Renderer: DirectX 12 / DirectX 11 / Vulkan; Display Mode: Fullscreen /
  Windowed Fullscreen; Upscale Mode: FSR / DLSS / XeSS / NIS (plus off);
  NVIDIA Reflex; Triple Buffering. Confirmed in a player guide on the
  official forum: https://www.pathofexile.com/forum/view-thread/3852015
  (accessed 2026-11-17). Whether a plain "Windowed" mode exists:
  UNVERIFIED.
- Resolution, V-Sync, Foreground FPS Cap, Background FPS Cap,
  Antialiasing Quality, Lighting (Shadows Only / Shadows and Global
  Illumination), Shadow + GI Quality, Sun Shadow Quality, Number of Lights,
  Water Detail Level, Texture Quality, Texture Filtering, Bloom, Depth of
  Field, Dynamic Culling, Dynamic Resolution (with a target frame rate),
  Engine Multithreading. Confirmed on
  https://www.pcgamesn.com/path-of-exile-2/best-settings-pc (updated
  2025-08-15, accessed 2026-11-17) and in part on
  https://allthings.how/path-of-exile-2-best-settings-for-max-fps-on-pc
  (updated 2026-07-14, accessed 2026-11-17). Third-party wording.
- Upscaler quality presets (DLSS Quality, FSR Quality): confirmed on
  allthings.how. Frame generation: no option found (UNVERIFIED, likely
  absent).

## What costs the most FPS (third-party measurements)

- The Lighting mode is the largest single cost: Shadows Only vs Shadows and
  Global Illumination about 117 -> 137 fps at 1080p; Shadow + GI Quality
  Ultra -> Low about 117 -> 135 fps (pcgamesn, confirmed). allthings.how
  reports about 32 percent for the lighting mode and 15-20 percent for the
  quality step (confirmed).
- Resolution and upscaling matter most overall (pcgamesn, 4K DLSS Quality
  72 vs 59 fps native, confirmed).
- Engine Multithreading off lowered performance a lot (forum thread
  3852015, a player reply, confirmed there). Dynamic Resolution looks
  muddy (same thread).
- Windowed Fullscreen: no GGG statement found. AshLight requires it for the
  overlay (decision 0002, research 0007), which is why the advisor always
  recommends it.

## Open

- A screenshot of the live PoE2 Graphics tab to confirm the exact labels
  and value lists (then drop "third-party wording" above).
- Intel Arc DX12 FPS drop reports (forum thread 3900119): seen only in
  search snippets, UNVERIFIED; the advisor does not act on it.
