"""Web-data opt-in sentence (UX-WEBDATA-SENTENCE-TRUE, decisions 0013, 0072).

The one sentence the player reads beside the web-data switch (Settings,
Reading and web data) and in the build link recovery before its confirm
click. It lists every request the switch allows, so the consent is given
to a true list. The core picks the wording by copy kind: an installed copy
with release polling off (server/al/ninja.py RELEASE_POLLING, decision
0072) asks poe.ninja for nothing, a checkout fetches prices. GET / POST
/api/web-data publish the picked sentence as "sentence"; web/panels/
webdata.js and web/tc.js show it as it is (textContent only), and
web/index.html holds no copy of it. Any change to either sentence bumps
server/al/updates.py WORDING_VERSION so earlier opt-ins acknowledge the new
wording once (ruling Q-21). Copy sheet: docs/design/copy/webdata.md;
tests/test_webdata_sentence.py pins both strings. Stdlib only.
"""

_HEAD = ("Off unless you turn it on. When on, AshLight downloads game data "
         "(item bases, gems, the passive tree) from public GitHub pages once a "
         "day. It opens a build link you paste, once. It checks GitHub once a "
         "day for a new AshLight; a new version downloads by itself and "
         "installs at a later start. ")
_TAIL = ("It never asks the trade site anything. It sends no account, password "
         "or cookie, and never touches the game.")

# an installed copy while ninja.RELEASE_POLLING is off (decision 0072)
NINJA_NONE = ("AshLight asks poe.ninja for nothing in this copy. Prices show as "
              "a trade link you open. ")
# a checkout (or a release once RELEASE_POLLING is on)
NINJA_PRICES = ("It fetches currency and item prices from poe.ninja, currency "
                "hourly, the rest every 3 hours. ")

SENTENCE_INSTALLED = _HEAD + NINJA_NONE + _TAIL
SENTENCE_CHECKOUT = _HEAD + NINJA_PRICES + _TAIL


def sentence(ninja_blocked):
    """The opt-in sentence: SENTENCE_INSTALLED when poe.ninja is never
    asked in this copy (ninja_blocked true), else SENTENCE_CHECKOUT."""
    return SENTENCE_INSTALLED if ninja_blocked else SENTENCE_CHECKOUT
