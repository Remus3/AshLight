"""GGG-DOCS-WATCH step (decision 0044): the daily GGG developer docs read,
in front of the HALT test, so it runs even while the loop is HALTed. The
read goes through the Deps seam docs_watch (tools/ggg_docs_watch.safe_check),
so the test kit keeps the network away. Moved here unchanged by AUTO-01."""


def pre_halt(tick):
    return tick.d.docs_watch(tick.root, tick.d.clock())
