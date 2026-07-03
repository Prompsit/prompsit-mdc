"""Oracle-derived legal_moves and legal-variation generators."""
from __future__ import annotations
import re

POSITIONAL = re.compile(r"%\d+\$[sdfeEgGxXc]|\{\d+\}")
_PROTECT = re.compile(
    r"<[^>]+>|&lt;[^&]*&gt;|%\d*\$?[sdfeEgGxXc]|%[A-Z_][A-Z_]+|\{\d+\}|\{\{[^}]*\}\}|\$\([^)]*\)"
)


def legal_moves(assets):
    moves = []
    for a in assets:
        if a.type in ("printf_placeholder", "positional_brace") and POSITIONAL.fullmatch(a.raw):
            moves.append(a.id)
        elif a.type == "xliff_inline" and not a.paired:
            moves.append(a.id)
        elif a.type == "html_tag" and not a.paired:
            moves.append(a.id)
        elif a.paired and a.pair and a.id < (a.pair or ""):
            moves.append(a.id)
    return moves


def _outside_assets(text, fn):
    parts, last, changed = [], 0, False
    for m in _PROTECT.finditer(text):
        seg = fn(text[last:m.start()])
        changed = changed or seg != text[last:m.start()]
        parts.append(seg); parts.append(m.group(0)); last = m.end()
    seg = fn(text[last:])
    changed = changed or seg != text[last:]
    parts.append(seg)
    out = "".join(parts)
    return out if changed else None


def v_positional_swap(text):
    toks = [m.group(0) for m in POSITIONAL.finditer(text)]
    distinct = list(dict.fromkeys(toks))
    if len(distinct) < 2:
        return None
    a, b = distinct[0], distinct[1]
    ia, ib = text.find(a), text.find(b)
    if ia < 0 or ib < 0 or ia == ib:
        return None
    if ia > ib:
        a, b, ia, ib = b, a, ib, ia
    return text[:ia] + b + text[ia + len(a):ib] + a + text[ib + len(b):]


def v_fr_typography(text):
    return _outside_assets(text, lambda s: re.sub(r"(?<=\S)([:;!?»])", " \\1", s).replace("«", "« "))


def v_quotes(text):
    def repl(s):
        if s.count('"') >= 2:
            i = s.find('"'); j = s.find('"', i + 1)
            return s[:i] + "«" + s[i + 1:j] + "»" + s[j + 1:]
        return s
    return _outside_assets(text, repl)


def v_icu_branch_reorder(text):
    m = re.search(r"(one\s*\{[^{}]*\})(\s*)(other\s*\{[^{}]*\})", text)
    if not m:
        return None
    return text[:m.start()] + m.group(3) + m.group(2) + m.group(1) + text[m.end():]


GENERATORS = {
    "positional_swap": v_positional_swap,
    "fr_typography": v_fr_typography,
    "guillemets": v_quotes,
    "icu_branch_reorder": v_icu_branch_reorder,
}
