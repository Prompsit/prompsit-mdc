#!/usr/bin/env python3
"""D4 document oracle + validators (deterministic, parser-based).

Scoring rule at the DOCUMENT level: the document tree is
preserved and round-trips; only the text is translated. The structure (block
sequence, table shape, links/images, segment map) is language-independent, so the
validator compares a hypothesis document's structural signature against the SOURCE
signature - reference-light. Text/translation quality is out of D4's scope.

Profile: rich HTML (headings, paragraphs, lists, a table, a link, an image).

The document TEXT is real human translation (D1 core, license inherited); only the
structural scaffolding is fixed by a template. ASCII-only.
"""
from __future__ import annotations

import re
from collections import Counter
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

LANGS = ["ca", "es", "fr", "it", "pt-PT", "de", "nl", "pl", "ru"]
SOURCE_LANG = "en"
VOID = {"img", "br", "hr"}
STRUCTURAL = {"h1", "h2", "p", "ul", "ol", "li", "table", "tr", "td", "th", "a", "img"}

ALL_CLASSES = ["lost_or_duplicated_node", "block_order_change",
               "table_cell_corruption", "broken_link_image", "roundtrip_failure"]
SEVERITY = {"lost_or_duplicated_node": "Major", "block_order_change": "Major",
            "table_cell_corruption": "Major", "broken_link_image": "Major",
            "roundtrip_failure": "Critical"}

LINK_HREF = "https://example.org/docs/guide"
IMG_SRC = "images/diagram.png"


def build_html(segs: list[str], href: str = LINK_HREF, src: str = IMG_SRC,
               variant: int = 0) -> str:
    """13 text segments -> a structurally rich HTML document.

    ``variant`` reorders the body blocks (the <h2>+<p> pair stays adjacent so the
    block-order corruption operator still has a target) to give the population a
    diversity of structural signatures instead of a single template; every variant
    keeps all five corruptible anchors (a <p>, a <li>, an <h2>+<p> pair, a 2x2
    <table>, a link and an image)."""
    s = [_esc(x) for x in segs]
    h1 = "<h1>%s</h1>" % s[0]
    p1 = "<p>%s</p>" % s[1]
    h2p = "<h2>%s</h2>\n<p>%s</p>" % (s[2], s[3])
    ul = "<ul>\n<li>%s</li>\n<li>%s</li>\n<li>%s</li>\n</ul>" % (s[4], s[5], s[6])
    table = ("<table>\n<tr><td>%s</td><td>%s</td></tr>\n"
             "<tr><td>%s</td><td>%s</td></tr>\n</table>") % (s[7], s[8], s[9], s[10])
    linkp = '<p><a href="%s">%s</a></p>' % (href, s[11])
    img = '<img src="%s" alt="%s"/>' % (src, s[12])
    orders = [
        [p1, h2p, ul, table, linkp, img],
        [h2p, p1, ul, table, linkp, img],
        [p1, h2p, table, ul, linkp, img],
        [p1, h2p, ul, linkp, table, img],
    ]
    body = "\n".join(orders[variant % len(orders)])
    return "<html><body>\n%s\n%s\n</body></html>\n" % (h1, body)


def _esc(t: str) -> str:
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def _xml_ok(html: str) -> bool:
    """Strict well-formedness: the document must parse as XML (catches broken
    attributes / unclosed tags that the lenient html.parser would swallow)."""
    try:
        ET.fromstring(html)
        return True
    except Exception:
        return False


# --- structural signature -----------------------------------------------------

class _Sig(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.seq = []          # block-order tags (table internals excluded)
        self.tags = []         # all structural tags (for the node multiset)
        self.stack = []
        self.balanced = True
        self.targets = []      # href + src (non-translatable)
        self.segments = 0
        self._td_per_tr = []
        self._cur_tr = 0
        self._in_tr = False
        self._tables = []      # (rows, cols)
        self._tr_count = 0

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag in STRUCTURAL:
            self.tags.append(tag)
            if tag not in ("tr", "td", "th"):  # table internals scored separately
                self.seq.append(tag)
        if tag == "a" and "href" in d:
            self.targets.append("href:" + d["href"])
        if tag == "img" and "src" in d:
            self.targets.append("src:" + d["src"])
        if tag == "table":
            self._tr_count = 0
            self._cols = None
        if tag == "tr":
            self._tr_count += 1
            self._cur_tr = 0
            self._in_tr = True
        if tag in ("td", "th") and self._in_tr:
            self._cur_tr += 1
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)  # void; not pushed

    def handle_endtag(self, tag):
        if tag == "tr":
            self._in_tr = False
            if not hasattr(self, "_cols") or self._cols is None:
                self._cols = self._cur_tr
        if tag == "table":
            self._tables.append((self._tr_count, getattr(self, "_cols", 0) or 0))
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.balanced = False
        else:
            self.stack.pop()

    def handle_data(self, data):
        if data.strip():
            self.segments += 1


def signature(html: str) -> dict:
    p = _Sig()
    try:
        p.feed(html)
        p.close()
    except Exception:
        return {"ok": False}
    balanced = p.balanced and not p.stack
    return {"ok": True, "balanced": balanced,
            "multiset": dict(Counter(p.tags)), "sequence": list(p.seq),
            "tables": [list(t) for t in p._tables], "targets": sorted(p.targets),
            "segments": p.segments}


# --- hard-gate scorer (compare hypothesis to SOURCE structure) ---------------

def score_item(record: dict, hypothesis: str) -> dict:
    src = record["source_signature"]
    hyp = signature(hypothesis)
    gates = {"roundtrip_valid": bool(hyp.get("ok") and hyp.get("balanced")
                                     and _xml_ok(hypothesis))}
    if not gates["roundtrip_valid"]:
        gates.update({"tree_match": False, "block_order": False,
                      "table_cells": False, "links_images": False, "pass": False,
                      "failure_class": "roundtrip_failure", "severity": "Critical"})
        return gates
    gates["tree_match"] = hyp["multiset"] == src["multiset"]
    gates["block_order"] = list(hyp["sequence"]) == list(src["sequence"])
    gates["table_cells"] = _astuple(hyp["tables"]) == _astuple(src["tables"])
    gates["links_images"] = frozenset(hyp["targets"]) == frozenset(src["targets"])
    gates["segment_map"] = hyp["segments"] == src["segments"]
    gates["pass"] = all(v for k, v in gates.items() if k != "pass")
    cls = None
    if not gates["tree_match"] or not gates["segment_map"]:
        cls = "lost_or_duplicated_node"
    elif not gates["block_order"]:
        cls = "block_order_change"
    elif not gates["table_cells"]:
        cls = "table_cell_corruption"
    elif not gates["links_images"]:
        cls = "broken_link_image"
    gates["failure_class"] = cls
    gates["severity"] = SEVERITY.get(cls) if cls else None
    return gates


def _astuple(x):
    return tuple(tuple(t) for t in x)


# --- corruption operators -----------------------------------------------------

def corrupt(cls: str, ref_html: str):
    if cls == "roundtrip_failure":
        return ref_html.replace("</p>", "", 1)  # unclosed <p>
    if cls == "lost_or_duplicated_node":
        return re.sub(r"<li>.*?</li>\n", "", ref_html, count=1)  # drop a list item
    if cls == "block_order_change":
        # swap the <h2>..</h2> block with the following <p>..</p>
        m = re.search(r"(<h2>.*?</h2>)\n(<p>.*?</p>)", ref_html, re.S)
        if not m:
            return None
        return ref_html.replace(m.group(0), m.group(2) + "\n" + m.group(1), 1)
    if cls == "table_cell_corruption":
        # count-preserving shape change: 2x2 -> rows of 3 and 1 (cells moved, not lost)
        return re.sub(
            r"<tr><td>(.*?)</td><td>(.*?)</td></tr>\n<tr><td>(.*?)</td><td>(.*?)</td></tr>",
            r"<tr><td>\1</td><td>\2</td><td>\3</td></tr>\n<tr><td>\4</td></tr>",
            ref_html, count=1, flags=re.S)
    if cls == "broken_link_image":
        return ref_html.replace('href="%s"' % LINK_HREF,
                                'href="%s-broken"' % LINK_HREF, 1)
    return None


def scoreable_classes(record: dict, ref_html: str) -> list[str]:
    out = []
    for cls in ALL_CLASSES:
        c = corrupt(cls, ref_html)
        if c is not None and not score_item(record, c)["pass"]:
            out.append(cls)
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    segs = ["Title", "Intro paragraph", "Section", "Body text",
            "First item", "Second item", "Third item",
            "Cell A", "Cell B", "Cell C", "Cell D", "See the guide", "Diagram alt"]
    en = build_html(segs)
    rec = {"source_signature": signature(en)}
    print("ref pass:", score_item(rec, en)["pass"])
    print("scoreable:", scoreable_classes(rec, en))
    for c in ALL_CLASSES:
        bad = corrupt(c, en)
        r = score_item(rec, bad) if bad else {"pass": None}
        print(c, "->", "rejected" if bad and not r["pass"] else "MISS", "| class:", r.get("failure_class"))
