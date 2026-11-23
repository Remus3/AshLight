# Quick start

From nothing to a live dashboard in four steps. Windows only.

## 1. Set it up

You need Python 3.11 or newer (3.13 or newer for a new install). Node.js
22.12.0 or newer is only needed for the desktop client and the overlay. There
is no release yet, so AshLight runs from a copy of its source code (see
[Download](download.md)). In that folder, run once:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

It checks what you have, makes AshLight's folders and, when Node.js is
installed, sets up the desktop client and puts an "AshLight" shortcut in the
Start Menu and on the desktop.

## 2. Start it

Click the AshLight shortcut. One click starts everything: the companion window
with the dashboard, a tray icon and the in-game overlay. Closing the window
with X keeps AshLight in the tray; click the tray icon to bring it back.
Right-click the tray icon for the menu, where Quit AshLight stops it.

Without Node.js, or from a terminal:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run.ps1
```

## 3. Say yes to the log

On the Play tab, press "Allow reading Client.txt". AshLight reads the game's
own log file only after you allow it, and the pill at the top says
"reading Client.txt" while it does. Start Path of Exile 2 once if AshLight
says Client.txt was not found yet; it finds the file by itself.

From then on the dashboard and the overlay show your zone and zone timer,
level, deaths and session time, plus incoming whispers and trade requests.

## 4. Check an item

Hover an item in the game and press Ctrl+C yourself, then press AshLight's
item check key (Alt+Shift+E by default). AshLight reads the clipboard once for
that press and shows a verdict for 20 seconds. Paste your Path of Building code
on the Build tab first to check items against your build.

The overlay shows and hides with Alt+Shift+A by default. Both keys can be
changed with Change a key under Settings, Keys.

## Optional

- Prices: tick "Use web data" under Prices and web data and type your contact
  there. AshLight then fetches prices and game data by itself.
- Full build numbers: `scripts\setup.ps1 -TcCalc` installs the optional calc
  component (Path of Building PoE2 run unmodified as a separate program).
- Start at logon: `scripts\autostart.ps1 -Enable` starts AshLight in the tray
  when you log on; `-Disable` turns it off.

Something not working? See [Common issues](common-issues.md).

---

This product isn't affiliated with or endorsed by Grinding Gear Games in any way.
