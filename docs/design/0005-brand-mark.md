# 0005 - AshLight brand mark, icon set and README hero

Status: accepted 2026-11-17 (operator order: a proper, distinctive app
icon for the shortcut and tray, and a README hero; BRAND-ICON). Builds on
`docs/design/0001-design-system.md` (palette, section 5) and the ToS floor
in `CLAUDE.md` (no GGG trademarks, art, logos, fonts or game imagery).

## Decision

- **Mark:** an ember flame rising from two bars of ash on a dark rounded
  tile. The flame leans right with one licking tongue on the left and a
  pale hot core low in the body; two short, narrowing grey bars sit under
  it (the ash bed). Three small sparks float off at 48 px and up. It reads
  the name literally: ash below, light rising out of it.
- **Small variant** (16, 24, 32 px; tray, favicon): the same flame and core
  in flat colours, one ash bar on the 16 px pixel grid, no sparks, a
  full-bleed tile so more pixels are lit. Separate source, not a scaled
  copy, so the tray stays crisp.
- **Colours:** kit tokens only, plus one brand colour. Tile: surface-2 to
  surface (dark) with the dark `border` hairline; flame: chart-2 orange
  `#eb6834` to chart-4 amber `#eda100`; ash: dark `text-muted` `#99a1aa`
  and dark `status-idle` `#5b636c`; core: brand-only pale amber `#fff1d2` /
  `#f7c35f` (small: `#fcd27a`). The tile is always dark, so flame and ash
  keep their contrast (5.4:1 and 6.6:1 on the tile) on any taskbar or
  tab strip; a `border` hairline (`#323840`) marks the tile edge on dark
  ones.
- **Wordmark and tagline** (README hero): own monoline lettering drawn as
  SVG strokes (round caps, 16 unit stroke for "AshLight", a tracked
  uppercase line for the tagline), so there is **no font at all**: no font
  file, no font licence, no system-font dependency. The dot of the i is an
  ember drop in the flame gradient. Tagline, own words: "A live, glanceable
  companion for Path of Exile 2" ("Path of Exile 2" descriptive only).
- **Hero themes:** one SVG with a `prefers-color-scheme: dark` rule; it is
  rendered twice (light ground `#f3f4f6` with `text` ink, dark ground
  `#0f1216` with dark `text` ink) and the README picks one with
  `<picture>`, so it fits GitHub light and dark. At phone width the
  tagline line is decorative; the alt text and the README's first line
  carry the same words.
- **Pipeline:** `tools/make_icons.py` (stdlib) runs the pinned Electron
  (`scripts/brand_render.js`: offscreen window, software raster, scale factor
  1, throwaway profile in the sidecar Temp) to render PNGs, writes the
  ICOs itself (PNG entries, 16-256), and copies only files whose bytes
  changed; a second run prints "unchanged" (read back 2026-11-17). Every
  `scripts/build.ps1` run checks the set; `-Icons` re-renders.

## Files

Sources: `assets/brand/ashlight-mark.svg`, `ashlight-mark-small.svg`,
`readme-hero.svg`. Renders: `assets/brand/png/ashlight-<n>.png`
(n = 16 24 32 48 64 128 256), `assets/brand/readme-hero-{light,dark}.png`
(1280 x 400). App: `app/assets/icon.ico`, `icon-256.png`, `tray-16.png`,
`tray-32.png`, found through `app/brand/index.js` (`ICO`, `TRAY_16`,
`TRAY_32`, `ICON_256`, `trayImage(nativeImage)`). Dashboard:
`web/favicon.ico` (16 32 48) served at `/favicon.ico`, `web/favicon.svg`.
Tests: `tests/test_brand_assets.py`, `app/test/brand.test.js`, the favicon
case in `tests/test_http_security.py`.

## Alternatives

- **Code-drawn ember dot** (the desktop-client branch's `app/client/icon.js`):
  generic, no story, cannot carry a hero. Replaced by these files.
- **Lantern outline:** reads as a camping or utility app and turns to mush
  under 24 px (frame, handle and glass all need lines).
- **Letter monogram "AL":** forgettable, and close to many unrelated apps.
- **Sun or star over a horizon:** loses the "ash" half of the name and
  looks like a weather app.
- **Text in a system font (Segoe UI) or a bundled free font:** needs a font
  licence record or a font file; drawn strokes need neither.
- **A stdlib Python rasteriser:** fully byte-reproducible anywhere, but a
  lot of code for anti-aliased curves; the pinned Electron is already a
  dependency and gives identical bytes run to run on one machine.

## Why

It says the name in one shape, it survives 16 px (flame, core and one bar
stay distinct), it uses only the kit palette, and it borrows nothing from
the game: no GGG mark, font, colour scheme or imagery.

## Reverses if

The operator picks another mark; a trademark or confusion conflict with
the flame-over-ash shape turns up; or the design system palette changes
(re-render with `tools/make_icons.py`).
