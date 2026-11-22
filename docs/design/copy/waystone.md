# Copy sheet: waystone

Templates for the waystone family: `server/al/text/waystone.py`
(`waystone_rewards_text`, `waystone_text`). The rules that bind every
template (one event, one sentence; player text quoted; missing fields read
honestly; overlay register; line limits; plurals; time words; passive
notifications; an exact-output test per template) stay in design 0001
section 9 ([0001-design-system.md](../0001-design-system.md)). This sheet
holds the templates only, moved word for word out of design 0001
(TEST-COPY-SHEETS); a new or changed waystone template is edited here, not
in design 0001.

## Templates

- Waystone rewards (decision 0039): `Rewards: +N% item quantity, +N%
  item rarity, ...` / `Rewards: none found in the item text.` /
  `Rewards: identify it to see them.`; overlay `+N% quantity, +N% rarity
  +K more` (34 chars).
