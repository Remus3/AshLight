# Copy sheet: buildlive

Templates for the build alert family: `server/al/text/buildlive.py`
(`build_alert_text`, `upgrade_notice_text`, `upgrades_text`). The rules
that bind every template (one event, one sentence; player text quoted;
missing fields read honestly; overlay register; line limits; plurals; time
words; passive notifications; an exact-output test per template) stay in
design 0001 section 9 ([0001-design-system.md](../0001-design-system.md)).
This sheet holds the templates only, moved word for word out of design
0001 (TEST-COPY-SHEETS); a new or changed buildlive template is edited
here, not in design 0001.

## Templates

- build alert and upgrade notices (BUILD-LIVE, decision 0045,
  `build_alert_text` / `upgrade_notice_text` / `upgrades_text` in
  server/al/text/buildlive.py, shown by web/buildlive.js in the #build-alert card titled
  `Your build`, hidden when the build fits and nothing is an upgrade;
  not a live region): `No build saved for <name> yet. Paste a PoB code
  on the Build tab to check items for <name>.`, `Build is for a
  <class>, but <name> is a <class>. Paste <name>'s own PoB code so item
  checks fit.`, `Build is from level <n>; you are level <n>. Paste a
  fresh PoB code to keep item checks right.`; list `Upgrades from items
  you checked`, `1 item you checked is an upgrade now.` / `<n> items you
  checked are upgrades now.` (no list and no text with none), rows `New upgrade for <slot>: <item>` (or
  `Upgrade for ...`), `Replaces <name>, <+n points|+n%>.` / `Goes in
  your empty <slot> slot, <delta>.`, fit `Fits your <class> build.` or
  `Needs level <n>; you are level <n>.` The card clears by itself when
  the build is fixed (re-pasted, or the character's file changes) or a
  re-score drops the item; no timer and no dismiss button.
