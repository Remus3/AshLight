# Common issues

Start here: open the dashboard's Settings tab and look at the Checks list.
Every check that needs a fix says what to do. Copy report copies a short
plain-text report with no file paths, names, contact or chat in it; paste it
where you ask for help.

## The dashboard says Client.txt was not found

Start Path of Exile 2 once so it writes its log file, Client.txt. AshLight
finds it by itself.

If you typed a Client.txt path in your settings and that file is gone, correct
"client_log" in config\local.json, or remove it so AshLight finds Client.txt by
itself.

## The dashboard says "not reading Client.txt"

You have not allowed it yet. Press "Allow reading Client.txt" on the Play tab.
You can stop it again at any time with "Stop reading Client.txt".

## Checks says AshLight is not reading Client.txt

A part of AshLight stopped. Run `scripts\run.ps1` to start AshLight's parts
again; it starts only the parts that are not already running.

## "can't reach AshLight"

AshLight itself is not running. Start it again from its Start Menu shortcut.

## "open AshLight from the link it showed at start"

The page was opened without its one-time access link. Use the AshLight window,
or open the link AshLight showed when it started.

## "log quiet - game closed or AFK?"

Nothing to fix. The game has written nothing to its log for 20 minutes, so it
may be closed or you are away. The overlay hides itself and comes back with
the next log line.

## The overlay does not show over the game

- Play in Windowed Fullscreen; the overlay cannot sit on top of exclusive
  fullscreen.
- Check that Show in-game overlay is ticked in the tray menu.
- Try Restart overlay in the tray menu.

## The item check key does nothing

Another app holds the key. Pick a different item check key under Overlay
position and size in AshLight's Tools. No restart is needed. The same goes for
the overlay key. Remember to press Ctrl+C on the item in the game first: if
the clipboard is empty, the card says "Copy the item first".

## No prices

- Prices need web data. Tick "Use web data" under Prices and web data.
- Type your contact in the Prices and web data card; without it price fetches
  stay off.
- If prices still do not come, check this computer's internet connection.
  AshLight tries again by itself.

## Game data is missing or old

AshLight fetches it by itself while web data is on, at most once a day. If it
stays missing or old, check this computer's internet connection.

## Build numbers are missing from item checks

The optional calc component is off or needs a fix. Run
`scripts\setup.ps1 -TcCalc`; that one step installs the calc again and turns
it on.

## Other accounts on this computer can change AshLight's files

Run `scripts\setup.ps1` again. If Checks still names the AshLight folder, run
`python -m server.al.acl apply .` in the AshLight folder.

## Port 8960 is taken by another program

Set "port" in config\local.json to another port from 8960 to 8979, or start
once with `scripts\run.ps1 -Port 8961`.

---

This product isn't affiliated with or endorsed by Grinding Gear Games in any way.
