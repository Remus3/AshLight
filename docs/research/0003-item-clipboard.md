# Item clipboard text parsing (PoE2)

Research date: 2026-11-16. No code copied. Claims no source confirmed are marked UNVERIFIED.
The em dash (U+2014) used by the game in advanced headers is written as "EM-DASH" below.

Source keys (URLs in "## Sources"): [EE2-PARSER], [EE2-ADV], [EE2-CS], [EE2-STAT], [EE2-REPO],
[POB2], [FORUM-CTRLC], [TRADE2-STATS], [GGG-DEV], [APT], [SEARCH-POLICY].

## 1. Ctrl+C and Ctrl+Alt+C

- Ctrl+C over an item in game puts a plain-text description of the item on the clipboard.
  Exiled Exchange 2 (MIT) says that after Ctrl+C the game copies item text and the tool only needs to
  parse it. (accessed 2026-11-16) [EE2-REPO]
- Ctrl+Alt+C adds the "advanced" description: a braced header line above each mod and, in the PoE1
  sample, the possible roll range in parentheses after each rolled number plus reminder text lines.
  (accessed 2026-11-16) [FORUM-CTRLC]
- Path of Building PoE2 (license: not checked) recognises the advanced header (`{ ... }`) and sets
  an `advancedCopy` flag; EE2 has a dedicated `advanced-mod-desc` module. So the PoE2 game still
  produces the advanced format. (accessed 2026-11-16) [POB2] [EE2-ADV]
- Exiled Exchange 2 and Awakened PoE Trade (MIT) are the reference parsers for the trade overlay
  use case. (accessed 2026-11-16) [EE2-REPO] [APT]

## 2. Text structure

All source observations (accessed 2026-11-16) [EE2-PARSER] [EE2-CS] [POB2] [FORUM-CTRLC]:

- Lines split on newline (CRLF possible; EE2 splits on `\r?\n` and drops one trailing empty line).
- Sections are separated by a line that is exactly 8 hyphens: `--------`. Drop empty sections.
- Section 1 (name plate): `Item Class: <class>`, `Rarity: <Normal|Magic|Rare|Unique|Currency|Gem|...>`,
  then name line(s): rares and uniques have a name line then a base type line; magic and normal
  items have one line (magic name embeds affix words around the base). Stackable currency and gems
  have `Rarity: Currency` / `Rarity: Gem` (EE2 constants). 
- If the item is unusable for the character, a line "You cannot use this item. Its stats will be
  ignored" can appear in the first section; EE2 moves the rest of the section over. (EE2 client
  string `CANNOT_USE_ITEM`.)
- Base stats section: item category line (e.g. weapon type), damage / crit / APS or armour /
  evasion / ES lines, `Quality: +N%` (EE2 prefix `Quality: `; quality of a catalyst kind is
  `Quality (<Type> Modifiers): ...` in PoB).
- `Requirements:` header then `Level: N`, `Str: N`, `Dex: N`, `Int: N` lines (PoE1 sample) or a
  single `Requires: Level N, N Str, ...` line (EE2 has a regex for `Requires:`). Either may be
  present; handle both. Items not meeting them carry `(unmet)`. (accessed 2026-11-16) [EE2-CS]
  [FORUM-CTRLC]
- `Sockets: ...` line (PoE1 `B-B` letters). PoE2 uses item sockets as `S` and jewel sockets as `J` in
  PoB's importer; rune sockets appear as the sockets line plus socketed rune lines flagged
  `(rune)`. Exact PoE2 layout: UNVERIFIED. (accessed 2026-11-16) [POB2]
- `Item Level: N` (EE2 string; filled coffins use a corpse level line instead).
- Tier lines: `Waystone Tier: N`, `Map Tier: N`, `Talisman Tier: N` (EE2 strings).
- Waystone property lines (EE2 strings): `Revives Available: N`, `Pack Size: +N%`,
  `Magic Monsters: +N%`, `Rare Monsters: +N%`, `Waystone Drop Chance: +N%`, `Item Rarity: +N%`,
  `Monster Rarity: +N%` (UNVERIFIED sign format), `Monster Effectiveness: ...`.
- Currency: `Stack Size: N/M` (EE2 prefix `Stack Size: `; the `/M` part UNVERIFIED), then description text
  and usage hint lines.
- Gems: `Level: N` (EE2 `GEM_LEVEL`), requirements, description. Meta gems may have only the rarity
  line (EE2 has a fallback for a skill-gem-like item with no Item Class line). (accessed 2026-11-16)
  [EE2-PARSER] [EE2-CS]
- Status lines, each its own line or single-line section (EE2 / PoB): `Corrupted`, `Twice Corrupted`
  (EE2 `DOUBLE_CORRUPTED`), `Mirrored`, `Unidentified` (optionally `Unidentified (Tier N)`),
  `Sanctified`, `Fractured Item`, `Unmodifiable`; PoB also lists `Desecrated Prefix` /
  `Desecrated Suffix` as standalone lines (open affixes slots). (accessed 2026-11-16) [EE2-CS]
  [POB2]
- Note line: `Note: ~price 5 divine` (EE2 prefix `Note: `; the `~price` / `~b/o` convention is
  from the trade site stash-tab notes). Everything after the prefix is the note. (accessed
  2026-11-16) [EE2-PARSER] [EE2-CS]
- Flavour text and help text lines follow near the end; reminder text lines in parentheses sit
  under a mod and must be skipped when matching stats (EE2 skips lines wrapped in parentheses).
  (accessed 2026-11-16) [EE2-STAT]

### Mod line markers

- Stat lines can end with a lowercase parenthesised tag; EE2 and PoB recognise: `(implicit)`,
  `(enchant)`, `(rune)`, `(added rune)`, `(desecrated)`, `(fractured)`, `(crafted)`, `(scourge)`,
  and PoB adds `(mutated)`. The PoE1 sample shows `(implicit)` and `(crucible)`. (accessed 2026-11-16)
  [EE2-ADV] [POB2] [FORUM-CTRLC]
- Plain Ctrl+C: implicits, then explicits as separate sections; runes and enchants come with tags.

### Advanced header (Ctrl+Alt+C)

Format (EE2 and PoE1 sample): a line wrapped in `{ ... }`. Inside, EM-DASH-separated segments:
(accessed 2026-11-16) [EE2-ADV] [EE2-CS] [FORUM-CTRLC]

- Segment 1: type words, optional name in double quotes, optional `(Tier: N)` and `(Rank: N)`.
  EE2 regex shape: `^(type words)(?: "name")?(?: \(Tier: N\))?(?: \(Rank: N\))?$`.
  Type words seen: `Prefix Modifier`, `Suffix Modifier`, `Implicit Modifier`, `Unique Modifier`,
  `Enhancement` (enchant), with `Crafted`, `Fractured` or `Desecrated` words as a prefix.
- Segment 2: comma-separated tags (e.g. `Damage, Caster, Lightning`), or `NN% Increased` (roll
  increase) for some mods; segment 3 may hold the other of the two.
- Example: `{ Prefix Modifier "Humming" (Tier: 9) EM-DASH Damage, Elemental, Lightning, Caster }`
  then the stat line `Adds 1 to 5(4-5) Lightning Damage to Spells` where `5(4-5)` is the rolled
  value and `(4-5)` its range.

## 3. Representative samples

Sample 1, rare weapon, PoE1 text, quoted from an official forum thread to show the real shape of
Ctrl+Alt+C; PoE2 differs in items and tags but not in structure (accessed 2026-11-16) [FORUM-CTRLC]:

```
Item Class: Wands
Rarity: Rare
Foe Edge
Calling Wand
--------
Requirements:
Level: 21 (unmet)
Int: 81 (unmet)
--------
Item Level: 30
--------
{ Implicit Modifier EM-DASH Damage, Minion }
Minions deal 12(12-16)% increased Damage (implicit)
--------
{ Prefix Modifier "Scholar's" (Tier: 6) EM-DASH Damage, Caster }
31(30-39)% increased Spell Damage
```

Samples 2 to 4 are SYNTHETIC illustrations assembled from the marker strings in the sources, not
copied from a real PoE2 item. UNVERIFIED against the live game; capture real ones before coding
tests.

Sample 2, stackable currency (UNVERIFIED layout):

```
Item Class: Stackable Currency
Rarity: Currency
Orb of Example
--------
Stack Size: 12/20
--------
<effect description line>
--------
Right click this item then left click a target to apply it.
```

Sample 3, waystone (UNVERIFIED layout; marker strings from EE2):

```
Item Class: Waystones
Rarity: Rare
<name>
Waystone (Tier 5)
--------
Waystone Tier: 5
Revives Available: 2
Item Rarity: +20%
--------
Item Level: 79
--------
<explicit mod line>
<explicit mod line>
--------
Corrupted
```

Sample 4, skill gem (UNVERIFIED layout; EE2 `GEM_LEVEL`):

```
Item Class: Skill Gems
Rarity: Gem
<gem name>
--------
<tags>
Level: 3
--------
Requirements:
Level: 12
--------
<description>
```

## 4. Mapping text mods to trade API stat ids

- Official data: `GET https://www.pathofexile.com/api/trade2/data/stats` returns `{ "result": [ groups ] }`.
  Each group has `id` and `label` (e.g. `pseudo`, `explicit`, ...), and `entries`, each with `id`,
  `text` template, `type` (same as the group) and sometimes `options` (for enum stats). The payload
  is large (about 855 KB of text). (accessed 2026-11-16) [TRADE2-STATS]
- Example entries seen: `explicit.stat_3484657501` text `# to Armour (Local)`; `explicit.stat_4220027924`
  text `#% to Cold Resistance`; `pseudo.pseudo_total_life` text `+# total maximum Life`. (accessed
  2026-11-16) [TRADE2-STATS]
- Placeholders: every number in the template is `#`. Local stats carry a `(Local)` suffix in the
  text; the item text does not, so a matcher must decide local vs global from item context (e.g.
  armour or weapon base) or by trying both and preferring the one with a trade id for the mod type.
  (accessed 2026-11-16) [TRADE2-STATS] [EE2-STAT]
- Mod type is part of the id prefix (`explicit.`, `implicit.`, `rune.`, `enchant.`, `fractured.`,
  `desecrated.`, ... ; the exact PoE2 group list UNVERIFIED beyond `pseudo` and `explicit`). Use the
  tag from the line (`(implicit)`, `(rune)`, ...) or the advanced header to pick the group.
- EE2 approach (accessed 2026-11-16) [EE2-STAT]:
  1. Skip reminder-text lines; try joining 1..N consecutive lines (multi-line mods).
  2. Replace each number with `#`, recording its value; numbers with a parenthesised `(min-max)`
     range become bounds; build variants in which some numbers stay literal (for stats with
     fixed numbers in the text).
  3. Look the normalised string up in a prebuilt table; when several stats share the string, pick by
     item category (weapon / armour) or merge their trade ids.
  4. Fallback: a table built from the trade data's own text.
  5. Negated stats (`reduced` vs `increased`) flip the sign of the roll.
  Their tables are generated by a separate `dataParser` and shipped per language in the app.
- Pseudo stats (total resistance, total life etc.) are defined by the trade site, not present in
  item text; the app builds them from the parsed explicit stats.
- Do not reuse their tables: they are MIT but regenerate from the official trade data and game files.
  (accessed 2026-11-16) [EE2-REPO]

## 5. Localization pitfalls

- Every marker string above is language dependent (`Item Class: `, `Rarity: `, `Item Level: `,
  `Stack Size: `, mod text, tag names, `Requirements`). EE2 stores them in per-language
  client-string modules and, when parsing fails, checks a table of localized rarity prefixes to return
  a "wrong language" error rather than a generic parse error. (accessed 2026-11-16) [EE2-PARSER]
  [EE2-CS]
- Chinese and Korean clients exist; spacing and brackets differ. UNVERIFIED in detail.
- Advanced header: some languages (Spanish, per EE2 comments) place a second type word differently, so
  EE2 keeps `type` and `type2` capture groups. (accessed 2026-11-16) [EE2-ADV]
- Trade API: `trade2/data/stats` is served per locale (the host/locale selects language); keep the
  matcher language equal to the client language. Exact locale routing UNVERIFIED.
- Initial version: support English only, detect non-English by the first line not beginning with
  the English item-class marker and show a clear message.

## 6. Safety and policy

- GGG developer docs (accessed 2026-11-16) [GGG-DEV]:
  - "Reading from the screen or clipboard may only be performed once per manual key press."
  - Overlay tools may read screen, clipboard or logs only while the user is aware of what the app does
    with the information.
  - Macros must be invoked manually; timers, reacting to file changes and screen triggers are not
    allowed; one game-affecting action per invocation (a chat message or command counts as one).
  - Apps that interact with the game or its files are prohibited (account termination).
  - Public apps should state they are not affiliated with or endorsed by Grinding Gear Games.
  - API apps must send an identifiable User-Agent and obey `X-Rate-Limit-*` and `Retry-After`.
- Grey area: most price-check overlays (Awakened PoE Trade, Exiled Exchange 2) register a global
  hotkey, then send Ctrl+C to the game themselves and read the clipboard. Whether that counts as
  "one key press, one action" is not stated by GGG; players report these tools are tolerated, but GGG
  staff say they cannot guarantee any tool is allowed. (accessed 2026-11-16) [SEARCH-POLICY] [APT]
  The claim that the tools synthesise Ctrl+C was not read from source in this research (the pages
  fetched did not show it); UNVERIFIED here, widely described elsewhere.
- Safe alternative for this app (design, not a legal opinion): the user presses Ctrl+C (or
  Ctrl+Alt+C) in game; the app only listens for the clipboard change (Windows
  `AddClipboardFormatListener` / WM_CLIPBOARDUPDATE) and, on change, checks the text looks like a PoE
  item (first line starts with the item-class marker; contains `--------`), then parses. No input is
  sent to the game, no window focus change, no hooks into the game process.
- Make the read tied to one event: one clipboard update produces at most one parse; no polling
  loops that re-read the clipboard, no timers; ignore the clipboard changes that the app itself caused.
- Never log or upload clipboard text that is not a recognised item; do not read other clipboard
  formats.

## Parser design proposal

- Pipeline: raw clipboard string -> normalise (strip BOM, convert CRLF to LF, trim) -> section
  split on exact `--------` -> section classifier -> typed item model -> stat matcher -> trade query
  builder (separate module).
- Item model fields: `item_class`, `rarity`, `name`, `base_type`, `quality`, `item_level`,
  `requirements{level,str,dex,int,unmet}`, `sockets` (raw string plus counts), `rune_slots`, `tier`
  (waystone/map), `stack{count,max}`, `gem{level}`, `flags{corrupted,mirrored,unidentified,
  sanctified,fractured,desecrated_open_prefix,desecrated_open_suffix}`, `note`, `mods[]`, `warnings[]`.
- Mod model: `{ section: implicit|explicit|rune|enchant|desecrated|fractured|crafted, kind:
  prefix|suffix|null, name, tier, tags[], lines[], values[{value,min,max}], stat_id?, trade_id? }`.
- Classifier rules, in order: first section starts with the item-class marker; status single-line
  sections; `Requirements`; `Sockets`; `Item Level`; tier and waystone property lines; mod sections
  (any line with a trailing `(implicit)`, `(rune)` ... tag, or any section preceded by a braced
  header); flavour text last.
- Advanced mode is detected by any line starting with `{ ` and ending with ` }`. Header regex: three
  captures (type words, optional quoted name, optional tier / rank) plus EM-DASH segments for tags.
  Strip `(min-max)` range suffixes from values and keep them as `min`/`max`.
- Stat matcher: data-driven (JSON generated from `trade2/data/stats` plus a local hand-curated
  overrides file), normalise `+`, numbers -> `#`, lookup by (mod_section, normalised text, local
  hint). Unresolved lines go to `mods[].unmatched` with a warning, never a thrown error.
- Locale: parser constructed with a `ClientStrings` object; English first; failure with a non-English
  first line returns `wrong_language`.
- Safety integration: the parser is a pure function; the clipboard watcher is a separate module that
  triggers it only on a WM_CLIPBOARDUPDATE caused by an external copy, with a size cap (e.g. 64 KB) and
  an item-shape pre-check.
- Test plan: collect real PoE2 Ctrl+C and Ctrl+Alt+C captures (rare weapon, armour, ring, jewel, rune
  item, currency stack, waystone, gem, unique, unidentified, corrupted, mirrored, noted) as fixtures
  in the app repo; the synthetic samples above must be replaced before relying on them.

## Sources

- [EE2-REPO] Exiled Exchange 2 repository, license MIT (accessed 2026-11-16):
  https://github.com/Kvan7/Exiled-Exchange-2 and
  https://raw.githubusercontent.com/Kvan7/Exiled-Exchange-2/master/LICENSE
- [EE2-PARSER] EE2 parser source, read for structure only, MIT (accessed 2026-11-16):
  https://raw.githubusercontent.com/Kvan7/Exiled-Exchange-2/dev/renderer/src/parser/Parser.ts
- [EE2-ADV] EE2 advanced-mod-desc, MIT (accessed 2026-11-16):
  https://raw.githubusercontent.com/Kvan7/Exiled-Exchange-2/dev/renderer/src/parser/advanced-mod-desc.ts
- [EE2-CS] EE2 English client strings, MIT (accessed 2026-11-16):
  https://raw.githubusercontent.com/Kvan7/Exiled-Exchange-2/dev/renderer/public/data/en/client_strings.js
- [EE2-STAT] EE2 stat-translations, MIT (accessed 2026-11-16):
  https://raw.githubusercontent.com/Kvan7/Exiled-Exchange-2/dev/renderer/src/parser/stat-translations.ts
- [APT] Awakened PoE Trade, license MIT (accessed 2026-11-16):
  https://github.com/SnosMe/awakened-poe-trade
- [POB2] Path of Building PoE2 Item.lua (license not checked here; read for marker names only)
  (accessed 2026-11-16):
  https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/dev/src/Classes/Item.lua
- [FORUM-CTRLC] "Examples of Ctrl+C text on items" (PoE1; standard and advanced) (accessed
  2026-11-16): https://pathofexile.com/forum/view-thread/3361443
- [TRADE2-STATS] Official PoE2 trade stats data (accessed 2026-11-16):
  https://www.pathofexile.com/api/trade2/data/stats
- [GGG-DEV] GGG developer docs (accessed 2026-11-16): https://www.pathofexile.com/developer/docs
- [SEARCH-POLICY] Forum threads on third-party tool tolerance (accessed 2026-11-16):
  https://www.pathofexile.com/forum/view-thread/3474232 and
  https://pathofexile.com/forum/view-thread/3584808
