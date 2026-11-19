"""TC-PRESS-BUILD (F-042, ruling Q-02): the item key loads a copied build.

The item-key press sends the core the text of its ONE clipboard read
(decision 0003; app/eval_hotkey.js). `classify(text)` sorts that text with
paste.detect, without decoding: "build" (a PoB code or character JSON),
"link" (a share link) or "item" (anything else). `load(core, text, at)`
then:

- build: loads it for the character being played (store.load_code, which
  keeps the replaced file as one undo copy) and publishes a "Build loaded"
  card; text that only looks like a code and does not decode returns None,
  so the press is the item check as before;
- link: loads it only with web data on (core.load_share_url: opt-in, host
  allow-list, size cap, one fetch); with web data off it makes no request
  and answers with the existing refusal words of POST /api/build-code;
- item: returns None (the item check and price check run as today).

The card is an eval card whose parts hold cardparts/buildload.py's value
(it answers without an item). A build press asks for no price check and
adds no price-watch row (core.eval_press). Nothing here reads the
clipboard or the screen, or sends anything to the game; build text stays
in memory apart from the build file the paste box writes too.
"""

from .. import webfetch
from . import cardparts, codec, live, model, paste
from .cardparts import buildload

KINDS = ("build", "link", "item")
SOURCE = "press"  # BuildStore.source of a build the item key loaded
# the existing refusal words of POST /api/build-code (server/al/http.py)
WEB_DATA_OFF = ("web data is off: turn it on to load share links, or paste the "
                "build code itself")
SHARE_FETCH_FAILED = ("AshLight couldn't fetch that share link. Check the link, "
                      "or paste the build code itself.")
LOADED_ERROR = "build loaded"  # state.EVAL_ERROR_TEXT keys
REFUSED_ERROR = "share link not loaded"


def classify(text):
    """'build', 'link' or 'item' for the pressed text (no decoding)."""
    if not isinstance(text, str) or not text.strip():
        return "item"
    kind = paste.detect(text)
    if kind in ("code", "json"):
        return "build"
    if kind == "url":
        return "link"
    return "item"


def _loaded(core, build, kind):
    return {"build_press": True, "status": "loaded", "kind": kind,
            "character": getattr(core.builds, "character", None),
            "class_name": build.class_name, "ascendancy": build.ascendancy,
            "level": build.level, "replaced": bool(getattr(core.builds, "replaced", False))}


def _refused(reason, error, **extra):
    return dict({"build_press": True, "status": "refused", "kind": "url",
                 "reason": reason, "error": error}, **extra)


def _load_link(core, text):
    try:
        build = core.load_share_url(text)
    except webfetch.WebDataOff:
        return _refused("web_data_off", WEB_DATA_OFF, web_data=False)
    except webfetch.UrlNotAllowed as e:
        return _refused("not_supported", f"share link not supported: {e}")
    except webfetch.FetchError:
        return _refused("fetch_failed", SHARE_FETCH_FAILED)
    except (codec.CodeError, model.BuildError) as e:
        return _refused("not_a_build", str(e))
    return _loaded(core, build, "url")


def card(doc):
    """The eval card (live.compact shape) for a press doc."""
    value_parts = cardparts.compute({"build_press": doc}, found=[buildload])
    loaded = doc.get("status") == "loaded"
    name = (buildload.describe(value_parts.get(buildload.NAME)) if loaded
            else "Share link")
    result = {"ok": False, "error": LOADED_ERROR if loaded else REFUSED_ERROR,
              "item": {"name": name}, "build_loaded": loaded}
    return dict(live.compact(result), upgrade=None, value=None, waystone=None,
                parts=value_parts)


def load(core, text, at=None):
    """Load the build the pressed text holds and publish its card; returns
    the press doc, or None when the text is an item (or a code that does not
    decode), so the caller runs the item check."""
    kind = classify(text)
    if kind == "item":
        return None
    if kind == "build":
        try:
            build = core.builds.load_code(text, source=SOURCE)
        except (codec.CodeError, model.BuildError):
            return None  # it only looked like a build: the item check answers
        doc = _loaded(core, build, paste.detect(text))
    else:
        doc = _load_link(core, text)
    core.state.set_eval(card(doc), at=at)
    return doc
