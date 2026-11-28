Please read [CONTRIBUTING.md](../CONTRIBUTING.md) first. Tick only the boxes
that apply to your change.

## What this changes

<!-- One or two sentences. -->

## Gates

Both must be green before review:

- [ ] `python -m pytest -q`
- [ ] `npm test --prefix app`

## Floor checklist

- [ ] It never reads or writes game memory, injects anything, hooks graphics or touches network traffic.
- [ ] It never sends input to the game: no keys, mouse, chat or macros.
- [ ] It never modifies or writes into a game file or game folder.
- [ ] It reads the clipboard or screen only once per press of an AshLight hotkey, never by watching.
- [ ] It calls no undocumented game endpoint and needs no account, password or session cookie.
- [ ] `server/`, `tools/` and `tests/` use the Python standard library only; npm packages are pinned exactly.
- [ ] Every text file is ASCII with LF line endings; no game art, logos or files.

## How this is merged

Pull requests are proposals: an accepted change is re-applied by the maintainer as their own commit and this pull request is closed with a link to it; you are credited in the release notes.
