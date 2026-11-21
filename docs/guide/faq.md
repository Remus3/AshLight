# FAQ

## Is it allowed? Can I be banned?

The honest answer: no third-party tool is approved. Grinding Gear Games does
not certify or vouch for any tool, and says bans are at its own discretion, so
nobody can promise you that a tool is safe or will stay allowed. AshLight
cannot promise that either.

What we can tell you is how AshLight is built. GGG's developer documentation
names three kinds of apps. Apps that interact with the game or its files are
against its Terms of Use. Apps that run on their own, apart from the game, are
"not encouraged" but "permitted", as long as they follow its rules for macros
and overlays: read the screen or the clipboard only once per manual key press,
and read the game's logs only while you know what is done with that data.
AshLight is built to sit in that second kind and to stay on the strict side of
every one of those rules.

AshLight does:

- Read the game's log file, Client.txt, only after you allow it on the Play
  tab. The pill at the top says when it is reading.
- Read the clipboard once each time you press the item check key, and at no
  other time.
- Copy text to your clipboard only when you click a Copy button.
- Fetch prices from poe.ninja, and open a build link you paste, only when you
  turn on web data.
- Run on this computer only. Its page can't be opened from another device.

AshLight never:

- Sends a key press, click or chat message to the game. Not even a copy
  shortcut: you press Ctrl+C yourself.
- Reads or changes the game's memory or network traffic, or changes any game
  file.
- Writes into your game folders. A file it makes for the game, such as a
  `.build` guide or a loot filter add-on, goes to your downloads and you move
  it yourself.
- Asks for your account, password or login cookie.
- Calls the trade site. It only builds a trade link that you open in your own
  browser.

Sources: GGG developer documentation, policy section (read 2026-11-16 and
2026-11-17), recorded in AshLight's research note 0001.

## Does AshLight cost frames?

It is built not to. The overlay is a separate window that never takes focus
and draws only when a shown value changes, with no animation. Its tested
budgets: under 1 percent of one CPU core when idle and under 250 MB of memory.

## Does anything leave my computer?

Not unless you turn on web data, which is off by default. With it on,
AshLight fetches prices from poe.ninja, public game data, and a build share
link once when you paste it. Every request names AshLight and its version and
carries no cookie or account id.

## Does it store my chat?

No. The log can hold chat text. AshLight keeps only a short in-memory list of
recent whispers and events and writes none of it to disk.

## Do I need Path of Building?

No. Paste a Path of Building PoE2 code to see your build and to check items
against it. For full build numbers, the optional calc component runs Path of
Building PoE2 unmodified as a separate program. AshLight has no damage
calculator of its own.

## Is there an installer?

No release yet: install from source (see [Download](download.md)).

## Does it cost anything?

No. AshLight is free, has no paid tier, no ads and no donation gate.

## Who makes it?

An independent project, not made by Grinding Gear Games.

---

This product isn't affiliated with or endorsed by Grinding Gear Games in any way.
