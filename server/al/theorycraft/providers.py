"""Build sources behind one interface (BUILD-LIVE, decision 0045).

The per-character build store asks a provider for a character's build; the
dashboard only ever sees the store's snapshot (`providers` list, `source`),
so a new source drops in without a UI change.

- `PasteProvider` ("paste"): what the player pasted (PoB code, character
  JSON, share URL resolved by the caller) or dropped into the character's
  build file. Always configured.
- `GggApiProvider` ("ggg_api"): a stub for a later official-API import
  (OAuth: character equipment, skills, passives). It is NOT configured,
  makes no request, holds no token and never calls a GGG endpoint; fetch()
  raises NotConfigured. Turning it on needs its own decision (OAuth client,
  scopes, rate-limit headers) and lands here with no UI change.
"""

from . import paste


class NotConfigured(RuntimeError):
    """The provider cannot fetch (no client, no grant, or not built yet)."""


class BuildProvider:
    """Interface: `name`, `status()` -> {"name", "configured", "note"},
    `fetch(character)` -> build text for paste.parse (PoB code or
    character JSON), or raises NotConfigured."""

    name = ""
    label = ""

    def status(self):
        return {"name": self.name, "label": self.label, "configured": False,
                "note": None}

    def fetch(self, character):  # pragma: no cover - interface
        raise NotConfigured(self.name)

    @staticmethod
    def parse(text):
        """Text -> model.Build (any pasted format); the store calls it."""
        return paste.parse(text)


class PasteProvider(BuildProvider):
    name = "paste"
    label = "Pasted build"

    def status(self):
        return {"name": self.name, "label": self.label, "configured": True,
                "note": None}

    def fetch(self, character):
        # a paste arrives from the player (POST /api/build-code); there is
        # nothing to fetch
        raise NotConfigured("a pasted build arrives from the player")


class GggApiProvider(BuildProvider):
    """Stub: no OAuth client exists yet. Never sends a request.

    Shape it will fill (research 0033): an OAuth public client with PKCE,
    scope `account:characters`; GET /character/poe2 (the list) and
    /character/poe2/<name> answer {"character": {...}} with equipment,
    jewels, skills (gems + supports) and passives (weapon-set trees and
    quest passives included); there is NO backpack inventory. That answer
    is the character JSON charjson.from_json already reads, so fetch() will
    return it as text and the store parses it like a paste. The paths
    below are documentation only: nothing here opens a connection."""

    name = "ggg_api"
    label = "Path of Exile account (not set up)"
    NOTE = "Not set up. Paste a PoB code instead."
    SCOPE = "account:characters"
    LIST_PATH = "/character/poe2"
    CHARACTER_PATH = "/character/poe2/{name}"
    PROVIDES = ("equipment", "jewels", "skills", "passives")

    def status(self):
        return {"name": self.name, "label": self.label, "configured": False,
                "note": self.NOTE, "scope": self.SCOPE,
                "provides": list(self.PROVIDES)}

    def fetch(self, character):
        raise NotConfigured(self.NOTE)


def default_providers():
    return [PasteProvider(), GggApiProvider()]
