"""One paste box, any build format (TC-JSON ZERO-CLICK: no import dialog).

`detect(text)` names the format of pasted text without decoding it:
"json" (character JSON, starts with "{"), "url" (a share URL, recognized,
not fetched: TC-URL), "code" (a PoB2 share code) or "unknown".
`parse(text)` returns a model.Build for any of them and raises the same
errors the code path does (codec.CodeError / ShareUrlError, model.BuildError;
a bad JSON paste raises charjson.CharJsonError, a BuildError).
"""

from . import charjson, codec, model

FORMATS = ("json", "url", "code", "unknown")


def detect(text):
    if charjson.looks_like_json(text):
        return "json"
    return codec.classify(text)


def parse(text):
    if detect(text) == "json":
        return charjson.from_json(text)
    return model.from_code(text)
