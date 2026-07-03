"""D1 hard-gate validators (deterministic, reference-free where possible)."""
from __future__ import annotations
import re
from collections import Counter
from assets import extract_assets

# html_tag attribute values that are human-readable and translated by design
# (AOO help: <link name="URL notation"> -> "Notació URL"). Structural values
# (href/src/hid/id/class/...) must stay byte-exact; these compare by key only.
TRANSLATABLE_ATTRS = {"name", "title", "alt", "label", "aria-label"}


def _norm_raw(a):
    """Language-invariant skeleton. Tags/placeholders/DNT identical across langs
    => raw as-is. ICU blocks carry translated branch bodies => reduce to
    {var, kw, sorted-branch-keys}."""
    if a.type == "xliff_inline" and (a.raw.startswith("<xliff:g") or a.raw.startswith("</xliff:g")):
        # xliff:g id/example are internal correspondence labels; AOSP uppercases
        # them per-locale. Strip them — what must be preserved is the tag and
        # its inner content, not the label. (<ph name=..> keeps its name.)
        import re as _re
        return _re.sub(r'\s+(?:id|example)="[^"]*"', '', a.raw).lower()
    if a.type == "icu_message":
        m = re.match(r"\{\s*(\w+)\s*,\s*(plural|select|selectordinal)\s*,(.*)\}\s*$", a.raw, re.S)
        if m:
            # CLDR-aware comparison (prescreen finding, 2026-06-12): plural
            # category branches (zero/one/two/few/many) legitimately differ
            # per target language (fr adds 'one', pl/ru use few/many) — a
            # third of ICU references false-positived under source-key equality.
            # Invariant kept: same variable, same keyword, same explicit =N
            # branches, and an 'other' branch present.
            keys = re.findall(r"(=\d+|zero|one|two|few|many|other)\s*\{", m.group(3))
            stable = sorted(k for k in set(keys) if k.startswith("=") or k == "other")
            return "icu:%s:%s:%s" % (m.group(1), m.group(2), ",".join(stable))
    if a.type == "html_tag" and a.attrs:
        # Attribute ORDER is not semantic, and translatable values (name/title/...)
        # differ per language; normalize to tag identity + sorted keys, comparing
        # only structural values. A dropped attribute still changes the key set.
        m = re.match(r"</?\s*([\w:-]+)", a.raw)
        name = m.group(1).lower() if m else a.raw
        items = sorted((k.lower(), "" if k.lower() in TRANSLATABLE_ATTRS else v)
                       for k, v in a.attrs.items())
        return "html:%s:%s" % (name, ",".join('%s=%s' % kv for kv in items))
    return a.raw


def _inventory(src_assets, hyp_assets):
    def bag(assets):
        return Counter((a.type, _norm_raw(a)) for a in assets)
    return bag(src_assets) == bag(hyp_assets)


def _placeholder_syntax(hyp, has_printf=True):
    if hyp.count("{") != hyp.count("}"):
        return False
    # corrupted printf spec ("%1$ s", "% s") only when the source had one; the
    # negative lookahead avoids flagging a literal "%" + word ("50% de", "80% di").
    if has_printf and re.search(r"%\s+\d*\$?\s*[sd](?![a-zA-Z])", hyp):
        return False
    if re.search(r"\{\s+\d+\s*\}|\{\s*\d+\s+\}", hyp):
        return False
    if re.search(r"\{\d+\$\s", hyp):
        return False
    return True


def _nesting(hyp):
    tokens = re.findall(r"</?xliff:g[^>]*>|</?(?:b|i|u|em|strong|a|code|span|g)\b[^>]*>", hyp)
    stack = []
    for tok in tokens:
        if tok.endswith("/>"):
            continue
        m = re.match(r"</?\s*([\w:]+)", tok)
        if not m:
            continue
        name = m.group(1)
        if tok.startswith("</"):
            if not stack or stack[-1] != name:
                return False
            stack.pop()
        else:
            stack.append(name)
    return not stack


def _icu_syntax(hyp, has_icu):
    if not has_icu:
        return True
    m = re.search(r"\{\s*\w+\s*,\s*(?:plural|select|selectordinal)\s*,", hyp)
    if not m:
        return False
    depth = 0
    for i in range(m.start(), len(hyp)):
        if hyp[i] == "{":
            depth += 1
        elif hyp[i] == "}":
            depth -= 1
            if depth == 0:
                block = hyp[m.start(): i + 1]
                return "other" in block or re.search(r"=\d+\s*\{", block) is not None
    return False


def _order(src_assets, hyp_assets):
    def seq(assets):
        return [a.raw for a in assets if not a.paired
                and a.type == "printf_placeholder"
                and not re.search(r"\d\$", a.raw)]
    return seq(src_assets) == seq(hyp_assets)


def _attributes(src_assets, hyp_assets):
    def attrset(assets):
        return Counter(
            (a.type, tuple(sorted((k.lower(), "" if k.lower() in TRANSLATABLE_ATTRS else v)
                                  for k, v in a.attrs.items())))
            for a in assets if a.attrs and a.type == "html_tag")
    return attrset(src_assets) == attrset(hyp_assets)


def _verbatim(src_assets, hyp):
    return all(a.raw in hyp for a in src_assets if a.type == "dnt")


def score_item(source, hypothesis, references=None):
    src_assets = extract_assets(source, references)
    hyp_assets = extract_assets(hypothesis, references)
    types = {a.type for a in src_assets}
    gates = {
        "inventory": _inventory(src_assets, hyp_assets),
        "placeholder_syntax": _placeholder_syntax(hypothesis, "printf_placeholder" in types),
        "nesting": _nesting(hypothesis) if any(a.paired for a in src_assets) else True,
        "icu_syntax": _icu_syntax(hypothesis, "icu_message" in types),
        "order": _order(src_assets, hyp_assets),
        "attributes": _attributes(src_assets, hyp_assets) if any(a.attrs for a in src_assets) else True,
        "verbatim": _verbatim(src_assets, hypothesis) if "dnt" in types else True,
    }
    gates["pass"] = all(gates.values())
    return gates


if __name__ == "__main__":
    s = 'Delete <xliff:g id="n">%1$s</xliff:g> from <b>{folder}</b>?'
    good = 'Eliminar <xliff:g id="n">%1$s</xliff:g> de <b>{folder}</b>?'
    print("good", score_item(s, good))
