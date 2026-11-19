# 0058 - Hotkeys: effective keys, rebind in the app, self-healing fallback

Date: 2026-11-18. Source: package OVL-KEYS-CLIENT (wave 5); finding F-026
(docs/plan/02-findings.md); decision 0003 (one clipboard read per manual
press, never input to the game); AREA-AUDIT P5-3 (app/hotkey.js, the safe
hotkey rule); decision 0053 (the main-process parts seam). The core side
(server/al/hotkeys.py mirrors the fallback lists, the core publishes the
effective keys and every surface prints those) is OVL-KEYS-CORE.

## Decision

1. Two keys, no more. The client registers at most two global keys:
   item check (`eval`, default Alt+Shift+E) and overlay show / hide
   (`toggle`, default Alt+Shift+A). Any further shortcut ships unset. The
   registry in app/parts/20-hotkeys.js refuses any other name.
2. Re-register on a config change. On the parts hook `configChanged`
   (config/local.json saved) the part re-picks each key exactly as
   app/main.js does (Hotkey.pick: env, then config, then the default) and
   swaps only a key whose wanted value changed: it unregisters that key's
   old accelerator only (never unregisterAll) and registers the new one.
   No restart. A key that was bound nowhere is retried on the next change.
3. Self-healing fallback. When the wanted key is taken (register returns
   false), the client tries `Hotkey.FALLBACKS[name]` in order, skipping
   the wanted key and the key the other shortcut holds:
   - eval: Alt+Shift+E, Ctrl+Shift+F9, Alt+Shift+F9, Ctrl+Alt+F9
   - toggle: Alt+Shift+A, Ctrl+Shift+F10, Alt+Shift+F10, Ctrl+Alt+F10
   Each is canonical, passes safeAccelerator (Ctrl or Alt held, never a
   game or Windows key) and the two lists share no key; the case table
   app/test/hotkey_cases.json holds the same lists under "fallbacks".
   A fallback is logged as "<label> shortcut <want> is taken; using
   <bound>". Nothing bound at all keeps the old sentence
   "<label> shortcut not available: <want>", which server/al/diag.py reads.
4. ops/runtime/hotkeys.json. On the hooks `ready`, `configChanged` and
   `toggled` the client writes, atomically (tmp + rename, ASCII, LF):
   `{"updated": ISO time, "keys": {"eval": {"want", "bound",
   "registered", "fallback"}, "toggle": {...}}, "overlay": {"user_on":
   <the player's show / hide choice>}}`. `fallback` is true when `bound`
   is a fallback key, `bound` is null when nothing is registered.
5. The item check handler stays ctx.actions.onEval, built in app/main.js
   around the one clipboard read per manual press. The part never reads
   the clipboard and sends nothing to the game.

## Alternatives

- Fixed keys with a Checks row only: a taken key stays dead and the
  player is told. Rejected: the player must act (change config, restart)
  to get a working key; minimal interaction (CLAUDE.md) asks for self
  healing.
- A settings-file edit: write the working fallback back into
  config/local.json. Rejected: AshLight would overwrite the player's own
  choice, and the next start could no longer try the wanted key again
  once it is free. The runtime file reports, the config stays the
  player's.
- Ctrl+Alt+letter fallbacks. Rejected: on many keyboard layouts Ctrl+Alt
  is AltGr and types a character in the game's chat.

## Choices the package text left open (ruled by the builder)

- `fallback` is a boolean, not the key: `bound` already names the key.
  Reverses if: a consumer needs the index in the list.
- A refused config key (pick's log line) is logged once per value per
  process, not on every config save (the dashboard saves the layout into
  the same file). Reverses if: diag needs the line repeated.
- With nothing registered yet (configChanged before ready), the hook does
  nothing. `user_on` is true while no overlay gate exists yet (the
  overlay window starts shown by the player's default).

## Why

A global shortcut taken by another program used to stay dead until the
player edited the config and restarted. The fallback heals it at start
and on a config change with no click, and hotkeys.json lets the core
print the key that really works instead of a literal. Checked by
app/test/hotkeys_live.test.js, app/test/hotkey.test.js and
app/test/parts.test.js.

## Reverses if

A fallback key clashes with a game bind in play, GGG's overlay rules
change (decision 0003), or the operator orders fixed keys.
