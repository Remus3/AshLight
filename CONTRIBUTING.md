# Contributing

Thanks for your interest in AshLight. Questions and bugs: open an issue and
pick a template. Security problems go privately, see [SECURITY.md](SECURITY.md).

- Read the README's
  ["What AshLight never does"](README.md#what-ashlight-never-does) first. A change that reads
  game memory, sends input to the game, or watches the clipboard will not be
  accepted.
- The core (`server/`) uses the Python standard library only. The overlay
  (`app/`) pins every npm package to an exact version.
- Every text file is ASCII with LF line endings.
- Run the tests before sending a change:
  `python -m pytest -q` and `npm test --prefix app`. The tests need
  pytest 9 or newer; the hash-pinned install line below sets it up:
  `python -m pip install --require-hashes -r requirements-dev.txt`.
- `powershell -ExecutionPolicy Bypass -File scripts\build.ps1` runs the
  test suite and writes a build stamp. It is the dev gate, not a player
  step, so the README quick start leaves it out.
- Do not copy code from other projects without a license check; projects
  under GPL, AGPL or non-commercial licenses are studied for ideas only.
- By contributing you agree your contribution is licensed under Apache-2.0.

## How a pull request is handled

- A pull request is a proposal. Nothing is merged on GitHub: when a change
  is accepted, the maintainer re-applies it locally as their own commit, so
  it passes the same gates as every other commit, and the pull request is
  closed with a link to that commit. You are credited in the release notes.
- The git hooks in `.githooks/` (tests, identity check, leak sweep) are the
  maintainer's gates. A clone does not install them and you do not need
  them: CI runs the same checks on every pull request.

## For maintainers

- `.claude/settings.json` holds hooks for the maintainer's AI coding
  assistant. They apply only to Claude Code users, and only after Claude
  Code's trust prompt for this folder is accepted; otherwise nothing reads
  them.
