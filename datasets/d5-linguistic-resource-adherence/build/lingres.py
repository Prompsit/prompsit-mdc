#!/usr/bin/env python3
"""D5 linguistic-resource oracle + validators (deterministic).

Scoring rule: a provided glossary and translation memory must
be RESPECTED. Each item embeds a real terminology pair (CLDR display names via
Babel - territories / languages / currencies, Unicode license) into a neutral
`[...]` slot of a real human-translated carrier (D1 core). The provided resources
(glossary entry and/or TM match) are metadata shown to the system; the hard gate
is uniform: the slot term(s) must equal the prescribed target term.

The six failure classes are the six ways a real pipeline violates that gate:
glossary required-missing / forbidden / inconsistent, TM exact-ignored,
bad-fuzzy-copied, glossary-vs-TM conflict mishandled. ASCII-only.
"""
from __future__ import annotations

import re

from babel import Locale

LANGS = ["ca", "es", "fr", "it", "pt-PT", "de", "nl", "pl", "ru"]
SOURCE_LANG = "en"
_LOC = {"en": "en_US", "ca": "ca_ES", "es": "es_ES", "fr": "fr_FR", "it": "it_IT",
        "pt-PT": "pt_PT", "de": "de_DE", "nl": "nl_NL", "pl": "pl_PL", "ru": "ru_RU"}

ALL_CLASSES = ["required_term_missing", "forbidden_term_used", "inconsistent_term",
               "approved_tm_ignored", "conflict_mishandled", "fuzzy_discernment"]
SEVERITY = {c: "Major" for c in ALL_CLASSES}
KIND_CLASSES = {
    "glossary": ["required_term_missing", "forbidden_term_used", "inconsistent_term"],
    "tm_exact": ["approved_tm_ignored"],
    "tm_fuzzy": ["fuzzy_discernment"],   # anti-correlated with adherence
    "conflict": ["conflict_mishandled"],
}

# Resources with different delivery contracts are scored in separate tracks and
# never collapsed into one headline number.
#  - glossary : forced terminology (vendor-specific contract: Google/DeepL/MS
#               dictionaries; many engines, incl. prompsit, have none).
#  - tm       : exact translation-memory reuse (universal TMX contract).
#  - conflict : glossary-vs-TM precedence; needs glossary-over-TM, a feature
#               TM-only systems lack -> reported apart, never in the headline.
#  - quality  : fuzzy-match discernment. A stale 85% match must NOT be copied;
#               this is a quality rule, anti-correlated with verbatim reuse, so it
#               is NOT an adherence metric.
KIND_TRACK = {"glossary": "glossary", "tm_exact": "tm",
              "conflict": "conflict", "tm_fuzzy": "quality"}
TRACKS = ["glossary", "tm", "conflict", "quality"]
HEADLINE_TRACKS = ["glossary", "tm"]


def track_for(kind: str) -> str:
    return KIND_TRACK[kind]

_SLOT_RE = re.compile(r"\[([^\[\]]*)\]")


# --- terminology bank (real, CLDR via Babel) ---------------------------------

def term_bank():
    """[(en_term, {lang: term})] with distinct translations across >=6 langs."""
    loc = {k: Locale.parse(v) for k, v in _LOC.items()}
    out = []
    seen = set()
    for attr in ("territories", "languages", "currencies"):
        en_map = getattr(loc["en"], attr)
        for code in sorted(en_map):
            en = en_map.get(code)
            if not en or not (3 <= len(en) <= 28) or en in seen:
                continue
            tr = {}
            ok = True
            for k in LANGS:
                v = getattr(loc[k], attr).get(code)
                if not v:
                    ok = False
                    break
                tr[k] = v
            if not ok:
                continue
            diff = sum(1 for k in LANGS if tr[k] != en)
            if diff == len(LANGS):  # term differs from en in every target -> all classes scoreable
                seen.add(en)
                out.append((en, tr))
    return out


# --- slot helpers -------------------------------------------------------------

def slot(text: str):
    m = list(_SLOT_RE.finditer(text))
    return m[-1].group(1) if m else None


def slot_terms(text: str):
    s = slot(text)
    return [t.strip() for t in s.split("|")] if s is not None else []


def make_slot(term: str, repeated: bool) -> str:
    return "[%s]" % ((term + " | " + term) if repeated else term)


def term_in(term: str, text: str) -> bool:
    """Word-boundary occurrence of a term anywhere in text."""
    return bool(term) and re.search(r"(?<!\w)%s(?!\w)" % re.escape(term), text) is not None


# --- hard-gate scorer ---------------------------------------------------------

def score_item(record: dict, hypothesis: str) -> dict:
    ref_term = record["ref_term"]
    terms = slot_terms(hypothesis)
    present = bool(terms) and all(t for t in terms)
    consistent = len(set(terms)) <= 1
    correct = present and all(t == ref_term for t in terms)
    # forbidden terms must be absent from the WHOLE hypothesis, not just the slot
    forbidden = [t for t in record.get("forbidden_terms", []) if t and t != ref_term]
    forbidden_present = any(term_in(t, hypothesis) for t in forbidden)
    forbidden_absent = not forbidden_present
    gates = {"term_present": present, "term_consistent": consistent,
             "term_correct": correct, "forbidden_absent": forbidden_absent,
             "pass": correct and forbidden_absent}
    cls = None
    if not gates["pass"]:
        wrong = next((t for t in terms if t != ref_term), None)
        if not present:
            cls = "required_term_missing"
        elif not consistent:
            cls = "inconsistent_term"
        elif not forbidden_absent:
            cls = "forbidden_term_used"
        elif wrong == record.get("en_term"):
            cls = "required_term_missing"
        elif wrong == record.get("stale_term"):
            cls = record["kind"] == "conflict" and "conflict_mishandled" or "fuzzy_discernment"
        else:
            # a wrong term that is neither the English source nor a stale/conflict
            # term: attribute by the resource kind it violated rather than always
            # 'forbidden_term_used' (tm_exact => the approved TM match was ignored).
            cls = {"tm_exact": "approved_tm_ignored",
                   "tm_fuzzy": "fuzzy_discernment"}.get(record.get("kind"), "forbidden_term_used")
    gates["failure_class"] = cls
    gates["severity"] = SEVERITY.get(cls) if cls else None
    return gates


# --- corruption operators (one per class) ------------------------------------

def corrupt(cls: str, record: dict):
    """Return a wrong hypothesis (carrier + wrong slot), or None if N/A."""
    base = record["reference"].rsplit(" [", 1)[0]
    ref_term = record["ref_term"]
    rep = record["repeated"]
    en = record.get("en_term")
    other = record.get("other_term")
    stale = record.get("stale_term")
    if cls == "required_term_missing":
        return base + " " + make_slot(en, rep) if en and en != ref_term else None
    if cls == "forbidden_term_used":
        return base + " " + make_slot(other, rep) if other and other != ref_term else None
    if cls == "inconsistent_term":
        if not rep or not other or other == ref_term:
            return None
        return base + " [%s | %s]" % (ref_term, other)
    if cls == "approved_tm_ignored":
        return base + " " + make_slot(other or en, rep) if (other or en) else None
    if cls == "fuzzy_discernment":
        return base + " " + make_slot(stale, rep) if stale and stale != ref_term else None
    if cls == "conflict_mishandled":
        return base + " " + make_slot(stale, rep) if stale and stale != ref_term else None
    return None


def scoreable_classes(record: dict) -> list[str]:
    out = []
    for cls in KIND_CLASSES[record["kind"]]:
        c = corrupt(cls, record)
        if c is not None and not score_item(record, c)["pass"]:
            out.append(cls)
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    bank = term_bank()
    print("term bank size:", len(bank))
    print("sample:", bank[0][0], "->", {k: bank[0][1][k] for k in ["es", "fr", "ru"]})
    en_t, tr = bank[0]
    other = bank[1][1]["es"]
    rec = {"kind": "glossary", "target_lang": "es", "ref_term": tr["es"],
           "en_term": en_t, "other_term": other, "stale_term": bank[2][1]["es"],
           "repeated": True, "reference": "Carrier text [%s | %s]" % (tr["es"], tr["es"])}
    print("ref pass:", score_item(rec, rec["reference"])["pass"])
    for c in scoreable_classes(rec):
        bad = corrupt(c, rec)
        print(c, "->", "rejected" if bad and not score_item(rec, bad)["pass"] else "MISS")
