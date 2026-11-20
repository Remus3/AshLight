"""`python -m server.al.install <command>`: hands over to cli.main."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
