"""Asset extraction and classification for D1 — Inline asset integrity.

Detects inline machine tokens in UI strings and classifies them into the
D1 asset classes (see DATASHEET.md "Asset classes & floors"):

  xliff_inline       <xliff:g id=..>...</xliff:g>            (AOSP production strings)
  html_tag           <b>..</b>, &lt;b&gt;..&lt;/b&gt;, <br/>  (paired and standalone)
  printf_placeholder %s, %1$s, %d, %.2f
  positional_brace   {0}, {1}                                 (Java MessageFormat etc.)
  named_brace        {var}, ${var}, $var                      (single-brace named)
  template_var       {{ var }}                                (i18n double-brace)
  icu_message        {n, plural|select, ...}                  (inline ICU MessageFormat)
  markdown_inline    [text](url), `code`, **bold**
  dnt                URLs, emails, brand/tech terms verbatim in all references

Every asset gets: id, type, raw, paired flag (+ pair id for paired tags).
Deterministic: same input -> same asset inventory.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Asset:
    id: str
    type: str
    raw: str
    paired: bool = False
    pair: str | None = None
    attrs: dict = field(default_factory=dict)
    origin: str = "natural"  # natural | injected_v1 | converted_android_plurals | converted_gettext_plurals

    def to_json(self) -> dict:
        d = {"id": self.id, "type": self.type, "raw": self.raw, "paired": self.paired}
        if self.pair:
            d["pair"] = self.pair
        if self.attrs:
            d["attrs"] = self.attrs
        if self.origin != "natural":
            d["origin"] = self.origin
        return d


# --- regexes -----------------------------------------------------------------

RE_XLIFF_PAIR = re.compile(r"<xliff:g\b([^>]*)>(.*?)</xliff:g>", re.S)
RE_XLIFF_SELF = re.compile(r"<xliff:g\b([^>]*)/>")
RE_PH_SELF = re.compile(r"<ph\s+name=\"[^\"]+\"\s*/>")

_HTML_TAGS = r"(?:b|i|u|em|strong|a|code|span|font|tt|sup|sub|big|small|h1|h2|p|li|ul|ol|div|bold|annotation|emph|ahelp|link|item|alt|variable|menuitem|embedvar|switchinline|caseinline|defaultinline)"
RE_HTML_PAIR = re.compile(rf"<({_HTML_TAGS})(\s[^>]*)?>(.*?)</\1>", re.S | re.I)
RE_HTML_ESC_PAIR = re.compile(rf"&lt;({_HTML_TAGS})(\s[^&]*?)?&gt;(.*?)&lt;/\1&gt;", re.S | re.I)
RE_HTML_SELF = re.compile(r"<br\s*/?>|&lt;br\s*/?&gt;", re.I)

RE_PRINTF = re.compile(r"%(?:\d+\$)?(?:\.\d+)?[sdfeEgGxXc]|%%")
RE_PCT_NUM = re.compile(r"%\d+\b")          # OpenOffice %1 %2
RE_PCT_NAME = re.compile(r"%[A-Z][A-Z_]{2,}\b")  # %PRODUCTNAME
RE_DOLLAR_PAREN = re.compile(r"\$\(\w+\)")     # $(ARG1)
RE_POS_BRACE = re.compile(r"\{(\d+)\}")
RE_TEMPLATE = re.compile(r"\{\{\s*[\w.$-]+\s*\}\}")
RE_NAMED_BRACE = re.compile(r"\{([A-Za-z_][\w.-]*)\}")
RE_DOLLAR_VAR = re.compile(r"\$\{[\w.]+\}|\$[A-Za-z_]\w*\b")

RE_ICU_OPEN = re.compile(r"\{\s*([\w]+)\s*,\s*(plural|select|selectordinal)\s*,")

RE_MD_LINK = re.compile(r"\[[^\]]+\]\([^)\s]+\)")
RE_MD_CODE = re.compile(r"`[^`\n]+`")
RE_MD_BOLD = re.compile(r"\*\*[^*\n]+\*\*")

RE_URL = re.compile(r"https?://[^\s<>\"')]+")
RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")

# Tech/brand lexicon for DNT candidates; confirmed only if verbatim in ALL references.
DNT_LEXICON = {
    "Wi-Fi", "Bluetooth", "USB", "SIM", "eSIM", "VPN", "APN", "NFC", "SD",
    "Ethernet", "HDMI", "DNS", "IP", "IPv4", "IPv6", "MAC", "IMEI", "PIN",
    "PUK", "ORCID", "DOI", "DSpace", "OpenAIRE", "Creative Commons", "PDF",
    "CSV", "XML", "JSON", "OpenGL", "Vulkan", "GDScript", "Mono", "URL",
    "URI", "ID", "MIDI", "GPS", "LDAP", "OTP", "Kerberos", "OpenID",
}
_DNT_RE = re.compile(
    r"\b(" + "|".join(sorted((re.escape(w) for w in DNT_LEXICON), key=len, reverse=True)) + r")\b"
)


def _find_icu_spans(text: str) -> list[str]:
    """Balanced-brace scan for inline ICU plural/select blocks."""
    spans = []
    for m in RE_ICU_OPEN.finditer(text):
        start = m.start()
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    spans.append(text[start : i + 1])
                    break
    return spans


def extract_assets(text: str, references: list[str] | None = None) -> list[Asset]:
    """Extract the asset inventory of a source string.

    `references` (all target-language strings) are used only to *confirm* DNT
    candidates: a DNT asset is recorded only when its surface form appears
    verbatim in every reference.
    """
    assets: list[Asset] = []
    consumed: list[tuple[int, int]] = []
    counter = {"t": 0, "ph": 0, "v": 0, "icu": 0, "md": 0, "dnt": 0}

    def overlaps(s: int, e: int) -> bool:
        return any(not (e <= cs or s >= ce) for cs, ce in consumed)

    def take(s: int, e: int) -> bool:
        if overlaps(s, e):
            return False
        consumed.append((s, e))
        return True

    def take_pair(open_span: tuple[int, int], close_span: tuple[int, int]) -> bool:
        """Consume only the delimiters of a paired asset, leaving the inner
        content free for further extraction (a placeholder inside <b>...</b>
        or <xliff:g>...</xliff:g> is still its own asset)."""
        if overlaps(*open_span) or overlaps(*close_span):
            return False
        consumed.append(open_span)
        consumed.append(close_span)
        return True

    # 1. ICU first (largest spans, may contain braces/placeholders inside)
    for span in _find_icu_spans(text):
        idx = text.find(span)
        if idx >= 0 and take(idx, idx + len(span)):
            counter["icu"] += 1
            assets.append(Asset(f"icu{counter['icu']}", "icu_message", span))

    # 2. XLIFF inline (paired + self-closing)
    for m in RE_XLIFF_PAIR.finditer(text):
        open_raw = f"<xliff:g{m.group(1)}>"
        close_raw = "</xliff:g>"
        open_span = (m.start(), m.start() + len(open_raw))
        close_span = (m.end() - len(close_raw), m.end())
        if take_pair(open_span, close_span):
            counter["t"] += 1
            a = counter["t"]
            counter["t"] += 1
            b = counter["t"]
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
            assets.append(Asset(f"t{a}", "xliff_inline", open_raw, True, f"t{b}", attrs))
            assets.append(Asset(f"t{b}", "xliff_inline", close_raw, True, f"t{a}"))
    for m in RE_XLIFF_SELF.finditer(text):
        if take(*m.span()):
            counter["t"] += 1
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
            assets.append(Asset(f"t{counter['t']}", "xliff_inline", m.group(0), False, attrs=attrs))
    for m in RE_PH_SELF.finditer(text):
        if take(*m.span()):
            counter["t"] += 1
            assets.append(Asset(f"t{counter['t']}", "xliff_inline", m.group(0), False))

    # 3. HTML (literal and entity-escaped), paired then standalone
    for rx, esc in ((RE_HTML_PAIR, False), (RE_HTML_ESC_PAIR, True)):
        for m in rx.finditer(text):
            tag, attrs_raw = m.group(1), (m.group(2) or "")
            if esc:
                open_raw = f"&lt;{tag}{attrs_raw}&gt;"
                close_raw = f"&lt;/{tag}&gt;"
            else:
                open_raw = f"<{tag}{attrs_raw}>"
                close_raw = f"</{tag}>"
            open_span = (m.start(), m.start() + len(open_raw))
            close_span = (m.end() - len(close_raw), m.end())
            if take_pair(open_span, close_span):
                counter["t"] += 1
                a = counter["t"]
                counter["t"] += 1
                b = counter["t"]
                attrs = dict(re.findall(r'(\w+)=(?:"|&quot;)([^"&]*)(?:"|&quot;)', attrs_raw))
                assets.append(Asset(f"t{a}", "html_tag", open_raw, True, f"t{b}", attrs))
                assets.append(Asset(f"t{b}", "html_tag", close_raw, True, f"t{a}"))
    for m in RE_HTML_SELF.finditer(text):
        if take(*m.span()):
            counter["t"] += 1
            assets.append(Asset(f"t{counter['t']}", "html_tag", m.group(0), False))

    # 4. Markdown inline — consume delimiters only (inner content stays free)
    for m in RE_MD_LINK.finditer(text):
        raw = m.group(0)
        idx = raw.rindex("](")
        if take_pair((m.start(), m.start() + 1), (m.start() + idx, m.end())):
            counter["md"] += 1
            assets.append(Asset(f"md{counter['md']}", "markdown_inline", raw))
    for rx, dlen in ((RE_MD_CODE, 1), (RE_MD_BOLD, 2)):
        for m in rx.finditer(text):
            if take_pair((m.start(), m.start() + dlen), (m.end() - dlen, m.end())):
                counter["md"] += 1
                assets.append(Asset(f"md{counter['md']}", "markdown_inline", m.group(0)))

    # 5. Placeholders (printf > template {{}} > positional {0} > named {x} > $var)
    for m in RE_PRINTF.finditer(text):
        if m.group(0) != "%%" and take(*m.span()):
            counter["ph"] += 1
            assets.append(Asset(f"ph{counter['ph']}", "printf_placeholder", m.group(0)))
    for m in RE_PCT_NUM.finditer(text):
        if take(*m.span()):
            counter["ph"] += 1
            assets.append(Asset(f"ph{counter['ph']}", "printf_placeholder", m.group(0)))
    for m in RE_PCT_NAME.finditer(text):
        if take(*m.span()):
            counter["v"] += 1
            assets.append(Asset(f"v{counter['v']}", "named_brace", m.group(0)))
    for m in RE_DOLLAR_PAREN.finditer(text):
        if take(*m.span()):
            counter["v"] += 1
            assets.append(Asset(f"v{counter['v']}", "named_brace", m.group(0)))
    for m in RE_TEMPLATE.finditer(text):
        if take(*m.span()):
            counter["v"] += 1
            assets.append(Asset(f"v{counter['v']}", "template_var", m.group(0)))
    for m in RE_POS_BRACE.finditer(text):
        if take(*m.span()):
            counter["ph"] += 1
            assets.append(Asset(f"ph{counter['ph']}", "positional_brace", m.group(0)))
    for m in RE_NAMED_BRACE.finditer(text):
        if take(*m.span()):
            counter["v"] += 1
            assets.append(Asset(f"v{counter['v']}", "named_brace", m.group(0)))
    for m in RE_DOLLAR_VAR.finditer(text):
        if take(*m.span()):
            counter["v"] += 1
            assets.append(Asset(f"v{counter['v']}", "named_brace", m.group(0)))

    # 6. DNT — URL/email always candidates; lexicon terms confirmed against refs
    dnt_candidates = [m for m in RE_URL.finditer(text)] + [m for m in RE_EMAIL.finditer(text)]
    for m in dnt_candidates:
        if take(*m.span()):
            counter["dnt"] += 1
            assets.append(Asset(f"dnt{counter['dnt']}", "dnt", m.group(0)))
    if references:
        for m in _DNT_RE.finditer(text):
            raw = m.group(0)
            if all(raw in r for r in references) and take(*m.span()):
                counter["dnt"] += 1
                assets.append(Asset(f"dnt{counter['dnt']}", "dnt", raw))

    return assets


# --- derived record fields ---------------------------------------------------

ASSET_CLASS_OF_TYPE = {
    "xliff_inline": "xliff",
    "html_tag": "html_tag",
    "printf_placeholder": "software_placeholder",
    "positional_brace": "software_placeholder",
    "named_brace": "template_variable",
    "template_var": "template_variable",
    "icu_message": "icu_messageformat",
    "markdown_inline": "markdown_inline",
    "dnt": "do_not_translate",
}


def asset_class_tags(assets: list[Asset]) -> list[str]:
    return sorted({ASSET_CLASS_OF_TYPE[a.type] for a in assets})


def expected_invariants(assets: list[Asset]) -> list[str]:
    inv = {"inventory_preserved"}
    types = {a.type for a in assets}
    if types & {"printf_placeholder", "positional_brace", "named_brace", "template_var"}:
        inv.add("placeholder_syntax_valid")
    if any(a.paired for a in assets):
        inv.add("nesting_valid")
    if "icu_message" in types:
        inv.add("icu_syntax_valid")
    if "dnt" in types:
        inv.add("verbatim_preserved")
    if any(a.attrs for a in assets):
        inv.add("attributes_preserved")
    return sorted(inv)


def failure_opportunity_tags(assets: list[Asset]) -> list[str]:
    tags = {"missing_asset", "extra_asset", "corrupted_syntax"}
    if any(a.paired for a in assets):
        tags |= {"invalid_nesting", "moved_paired_tag"}
    n_unpaired = sum(1 for a in assets if not a.paired)
    if n_unpaired >= 2:
        tags.add("wrong_order")
    if any(a.type == "icu_message" for a in assets):
        tags.add("broken_icu")
    if any(a.attrs for a in assets):
        tags.add("lost_attribute")
    if any(a.type == "dnt" for a in assets):
        tags.add("dnt_violation")
    return sorted(tags)


# --- reference positions ------------------------------------------------------

_WORD = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """NFKC + regex word-break. Approximation of ICU word-break (documented)."""
    import unicodedata

    return _WORD.findall(unicodedata.normalize("NFKC", text))


def ref_positions(reference: str, assets: list[Asset]) -> dict[str, int]:
    """Word-token index of each asset occurrence in the reference."""
    import unicodedata

    ref = unicodedata.normalize("NFKC", reference)
    positions: dict[str, int] = {}
    cursor: dict[str, int] = {}
    for a in assets:
        raw = unicodedata.normalize("NFKC", a.raw)
        start = ref.find(raw, cursor.get(raw, 0))
        if start < 0:
            continue
        cursor[raw] = start + len(raw)
        positions[a.id] = len(_WORD.findall(ref[:start]))
    return positions
