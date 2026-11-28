"""HTML scans for tests through html.parser, never a tag regex.

CodeQL py/bad-tag-filter (decision 0087): a regex does not read HTML the
way a browser does (`</script >`, upper case, attributes on the end tag).
html.parser follows the HTML tokenizer for script elements, so the tests
check what a browser would run.
"""
from html.parser import HTMLParser


class _Scan(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.text = text
        starts = [0]
        for ln in text.split("\n"):   # html.parser counts LF only
            starts.append(starts[-1] + len(ln) + 1)
        self._starts = starts
        self.tags = []      # (name, attrs dict, raw start tag)
        self.scripts = []   # (attrs dict, body text)
        self.cuts = []      # (start, end, kind) of every script / comment
        self._open = None   # (start offset, attrs, [body parts])

    def _off(self):
        line, col = self.getpos()
        return self._starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        raw = self.get_starttag_text() or ""
        amap = {k: (v or "") for k, v in attrs}
        self.tags.append((tag, amap, raw))
        if tag == "script":
            self._open = (self._off(), amap, [])

    def handle_startendtag(self, tag, attrs):
        raw = self.get_starttag_text() or ""
        self.tags.append((tag, {k: (v or "") for k, v in attrs}, raw))

    def handle_data(self, data):
        if self._open is not None:
            self._open[2].append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._open is not None:
            start, amap, parts = self._open
            pos = self._off()
            end = self.text.index(">", pos) + 1
            self.scripts.append((amap, "".join(parts)))
            self.cuts.append((start, end, "script"))
            self._open = None

    def handle_comment(self, data):
        pos = self._off()
        end = self.text.find("-->", pos)
        self.cuts.append((pos, len(self.text) if end < 0 else end + 3,
                          "comment"))


def scan(text):
    s = _Scan(text)
    s.feed(text)
    s.close()
    if s._open is not None:   # an unclosed script runs to the end
        start, amap, parts = s._open
        s.scripts.append((amap, "".join(parts)))
        s.cuts.append((start, len(text), "script"))
        s._open = None
    return s


def tags(text):
    """[(name, attrs, raw start tag)] for every start tag."""
    return scan(text).tags


def scripts(text):
    """[(attrs, body)] for every script element."""
    return scan(text).scripts


def cut(text, comments=True, repl=" ", eat_space=False):
    """text with every script element (and comment) replaced by repl;
    eat_space also drops the whitespace right after a cut script."""
    s = scan(text)
    spans = sorted(c for c in s.cuts if comments or c[2] == "script")
    out, at = [], 0
    for start, end, _kind in spans:
        if start < at:
            continue
        out.append(text[at:start])
        out.append(repl)
        at = end
        if eat_space:
            while at < len(text) and text[at].isspace():
                at += 1
    out.append(text[at:])
    return "".join(out)
