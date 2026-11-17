"""POLICY-WORDING-WATCH: the overlay / macro wording watch record.

Research 0029 keeps a dated log of re-reads of GGG's developer docs policy
wording, each diffed against the verified quotes in research 0001. These
tests keep the record honest: every 0001 verified quote is carried in the
0029 baseline, every log entry names a source URL, a date and a verdict,
and the pending 1.0 trigger stays on file until it is run.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R0001 = ROOT / "docs" / "research" / "0001-ggg-tool-policy.md"
R0029 = ROOT / "docs" / "research" / "0029-policy-wording-watch.md"
INDEX = ROOT / "docs" / "research" / "README.md"

DOCS_URL = "https://www.pathofexile.com/developer/docs"
ENTRY = re.compile(
    r"^- (\d{4}-\d{2}-\d{2}) \| trigger=([^|]+?) \| verdict=(UNCHANGED|CHANGED|PENDING)"
    r" \| source=(\S+)")


def verified_quotes():
    """Quoted strings in the bullets of 0001's 'Verified quotes' section,
    up to its 'Consequences' paragraph."""
    text = R0001.read_text(encoding="ascii")
    start = text.index("## Verified quotes")
    end = text.index("Consequences that bind", start)
    quotes = []
    for line in text[start:end].splitlines():
        if line.startswith("- "):
            quotes.extend(re.findall(r'"([^"]+)"', line))
    return quotes


def entries():
    return [m.groups() for m in
            (ENTRY.match(l) for l in R0029.read_text(encoding="ascii").splitlines())
            if m]


class PolicyWordingWatchTest(unittest.TestCase):
    def test_record_exists_and_is_indexed(self):
        self.assertTrue(R0029.is_file(), "research 0029 watch record missing")
        self.assertIn("0029-policy-wording-watch.md", INDEX.read_text(encoding="ascii"))

    def test_0001_has_quotes_to_watch(self):
        self.assertGreaterEqual(len(verified_quotes()), 9)

    def test_baseline_carries_every_0001_quote_verbatim(self):
        body = R0029.read_text(encoding="ascii")
        missing = [q for q in verified_quotes() if q not in body]
        self.assertEqual(missing, [], "0001 verified quotes absent from the 0029 baseline")

    def test_log_has_a_dated_read_with_source(self):
        done = [e for e in entries() if e[2] in ("UNCHANGED", "CHANGED")]
        self.assertTrue(done, "no completed re-read in the watch log")
        for date, _trigger, _verdict, source in done:
            self.assertTrue(source.startswith(DOCS_URL), source)
            self.assertRegex(date, r"^20\d\d-\d\d-\d\d$")

    def test_changed_verdict_carries_a_diff(self):
        body = R0029.read_text(encoding="ascii")
        for date, _t, verdict, _s in entries():
            if verdict == "CHANGED":
                self.assertIn("### Diff " + date, body)

    def test_one_point_zero_trigger_on_file(self):
        triggers = " ".join(e[1] for e in entries())
        self.assertIn("1.0 notes", triggers)

    def test_floor_proposals_route_to_main(self):
        body = R0029.read_text(encoding="ascii")
        self.assertIn("MAIN", body)
        self.assertIn("never self-edited", body)


if __name__ == "__main__":
    unittest.main()
