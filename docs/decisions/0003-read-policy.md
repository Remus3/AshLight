# 0003 - What AshLight reads, and when

Date: 2026-11-16. Input: `docs/research/0001-ggg-tool-policy.md` (verified
quotes of https://www.pathofexile.com/developer/docs, accessed 2026-11-16).

## Decision

- Client.txt: tailed continuously, read only, ONLY after the user's opt-in
  (first-run consent naming the file and what is derived from it), with a
  visible "reading Client.txt" indicator on the dashboard. GGG: "You may only
  read this information as long as the user is aware of what you are doing
  with that data."
- Clipboard and screen: read ONLY once per manual key press of an AshLight
  hotkey. No clipboard watcher, no timer, no continuous screen capture. GGG:
  "Reading from the screen or clipboard may only be performed once per manual
  key press."
- AshLight never sends any key, mouse or chat input to the game - not even
  the Ctrl+C that other tools synthesize. The user copies the item; the
  AshLight hotkey then reads the clipboard once.

## Alternatives

- Clipboard-change watcher (reads whenever the clipboard changes): ruled out,
  it reacts to events instead of a key press.
- Send Ctrl+C on the user's hotkey (Awakened PoE Trade / Exiled Exchange 2
  style): one action per key press is arguably allowed, but the floor here is
  stricter - no input to the game at all.

## Reverses if

GGG's developer docs change the overlay rules (re-read on every research
refresh; ROADMAP row RES-POLICY).
