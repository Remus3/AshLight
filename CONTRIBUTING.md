# Contributing

Thanks for your interest in AshLight.

- Read the README's "What AshLight never does" first. A change that reads
  game memory, sends input to the game, or watches the clipboard will not be
  accepted.
- The core (`server/`) uses the Python standard library only. The overlay
  (`app/`) pins every npm package to an exact version.
- Every text file is ASCII with LF line endings.
- Run the tests before sending a change:
  `python -m pytest -q` and `npm test --prefix app`.
- Do not copy code from other projects without a license check; projects
  under GPL, AGPL or non-commercial licenses are studied for ideas only.
- By contributing you agree your contribution is licensed under Apache-2.0.
