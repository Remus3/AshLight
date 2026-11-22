# Copy sheet: overlaycard

Templates for the overlay card family: `server/al/text/overlaycard.py`
(`overlay_card`) and the overlay HUD status slot words next to the card.
The rules that bind every template (one event, one sentence; player text
quoted; missing fields read honestly; overlay register; line limits;
plurals; time words; passive notifications; an exact-output test per
template) stay in design 0001 section 9
([0001-design-system.md](../0001-design-system.md)). This sheet holds the
templates only, moved word for word out of design 0001 (TEST-COPY-SHEETS);
a new or changed overlaycard template is edited here, not in design 0001.

## Templates

- open trade count (UX-REVIEW F1, `format.js tradeCount`): HUD status
  slot `1 trade` / `<n> trades` while a card hides the trade card;
  slot order: connection, Client.txt state, trade count, under-level
  word (UTIL-UNDERLEVEL `N lv under`, at most 11 characters), AFK / DND,
  campaign hint word (UTIL-CAMPAIGN-CHECKS, at most 15 characters)
