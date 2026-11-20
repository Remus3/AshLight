"""AshLight's installer package (REL-INSTALL-HOME, finding F-050, DEP-09,
decision 0059; docs/plan/05-deployment.md "Installed-mode layout").

Run as `python -m server.al.install <command>` in a checkout, or
`<python> <payload>/boot.py server.al.install <command>` in an install.

- cli.py: the ONE fixed command table; each command lives in its own
  module here, loaded only when it runs. Later installer packages add a
  module and never edit the table.
- home.py: the home layout, and the marker <home>/install.json (schema 1)
  read / write / switch, each write read back; version folders and the
  cleanup plan.
- status.py: the `status` command.

This package runs only in the installer's own process. The running core
never imports it (a static test in tests/test_install_home.py checks
core.py, http.py and state.py). It never reads or writes a game folder
and reads no registry; standard library only.
"""
