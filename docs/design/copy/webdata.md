# Copy sheet: webdata

The web-data opt-in sentence: `server/al/text/webdata.py`. The core picks
it by copy kind (`Core.web_data_sentence`, the rates client's release gate
of decision 0072) and GET / POST /api/web-data publish it as `sentence`.
Settings, Reading and web data (`#webdata-sentence`, filled by
web/panels/webdata.js) and the build link recovery (web/tc.js
`linkRecover`, before its confirm click) show it as it is; web/index.html
holds no copy (UX-WEBDATA-SENTENCE-TRUE, review 2026-11-28 P1-2). The
rules of design 0001 section 9 bind it. `tests/test_webdata_sentence.py`
pins both strings exactly.

Any change to either sentence bumps `server/al/updates.py`
`WORDING_VERSION` (now 2), so an opt-in acknowledged under older words
makes no update request until the player ticks the switch beside the new
sentence once (ruling Q-21).

## Templates

- installed copy, poe.ninja release polling off (`SENTENCE_INSTALLED`):
  `Off unless you turn it on. When on, AshLight downloads game data (item
  bases, gems, the passive tree) from public GitHub pages once a day. It
  opens a build link you paste, once. It checks GitHub once a day for a
  new AshLight. A new version downloads by itself while the game is
  closed and installs the next time you open AshLight. AshLight asks
  poe.ninja for nothing in this copy. Prices show as a trade link you
  open. It never asks the trade site anything. It sends
  no account, password or cookie, and never touches the game.`
- checkout, or a release once polling is on (`SENTENCE_CHECKOUT`): the
  same, with `It fetches currency and item prices from poe.ninja,
  currency hourly, the rest every 3 hours.` in place of the two poe.ninja
  sentences above.
- the review's suggested wording (one long head sentence) was split into
  short sentences on the design review of this row (S3 / S4); the list of
  requests is unchanged.
- before the first answer: nothing is shown and the switch cannot be
  ticked on (it can still be turned off); a failed read shows `Can't load
  what web data does. Open AshLight again from the tray.`
- the link offer with no sentence read yet: `Reading the web data
  setting...`, then the sentence; if it still has none, `Can't load the
  web data setting. Open AshLight again from the tray.`
