"""AshLight core: Client.txt tailer -> parser -> event bus -> state -> HTTP/SSE.

A companion app for Path of Exile 2. It only reads the game's Client.txt log
(after the user's opt-in) and never touches the game process or sends input.
"""

VERSION = "0.1.0"
NAME = "AshLight"
DISCLAIMER = ("This product isn't affiliated with or endorsed by Grinding Gear "
              "Games in any way.")
