# Watcher row templates

One file per watch source, `<source>.json` (lower case, digits, hyphens); `tools/watch_rows.py` loads every file here as one table.
Shape: `{"kinds": {<kind>: {"act", "id", "lane", "priority", "blocked", "text", "tokens", "sample"}}}`.
`act` is `note`, `row`, `gate` or `dive`; `row` and `gate` need `id`, `lane` (`build`, `data`, `review`) and a one-line ASCII `text`.
Placeholders are `<name>`; `<YYYY-MM-DD>` and `<YYYYMMDD>` are filled from the tick date, every other one is a declared token.
`tokens` maps each token to a regex (no anchors; values are full-matched and must also be a short word, never an upstream sentence).
`sample` gives one valid value per token; a test renders every row kind with it, so a new file is checked with no test edit.
`blocked` is null or the tag body (`session ...`); render writes ` BLOCKED: <blocked>.` before the SOURCE clause; `text` never writes BLOCKED.
A kind is defined once across all files; no id may equal or hyphen-extend another (except TC-OAUTH-REG-OPEN and LIVE-1-<ITEM>).
A template naming CLAUDE.md, ROADMAP.md, web/, app/overlay/, app/shared/, event text or a new decision must be `BLOCKED: session`.
A rendered row parses as exactly one open ROADMAP row with the expected id and lane, ASCII, LF, at most 700 characters.
