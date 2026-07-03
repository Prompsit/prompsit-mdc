#!/usr/bin/env python3
"""D2 hard-gate validators (deterministic).

The scored invariant is locale-form conformance: the entity rendering in the
hypothesis must be a locale-legal form for the target locale (correctness logic
B). Whitespace-class differences (NBSP vs NNBSP grouping) are legal and absorbed
by cldr_oracle.norm, so they never flip a correct output (the K2 guard).

score_entity scores one rendered entity; score_item extracts the entity from a
full hypothesis sentence (neutral `[...]` slot) and scores it. ASCII-only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cldr_oracle as o  # noqa: E402

_SLOT_RE = re.compile(r"\[([^\[\]]*)\]")

SEVERITY = {
    # format track (headline)
    "wrong_decimal_separator": "Major",
    "wrong_grouping": "Minor",
    "mis_converted_datetime": "Major",
    "broken_currency_format": "Major",
    "wrong_unit_format": "Minor",
}


def value_from_semantic(entity: dict):
    k, s = entity["kind"], entity["semantic"]
    if k == "number":
        return s["value"]
    if k == "currency":
        return (s["amount"], s["code"])
    if k == "date":
        return s["iso"]
    if k == "unit":
        return (s["amount"], s["unit"])
    raise ValueError(k)


def score_entity(entity: dict, target_lang: str, hyp_render: str,
                 track: str = "format") -> dict:
    """Gate result for one entity rendering within `track` (format=headline,
    conversion=opt-in). The official hard gate is locale_form_conformant;
    classify which failure class it matches for severity / diagnostics."""
    kind = entity["kind"]
    value = value_from_semantic(entity)
    accepted = entity.get("accepted_variants")
    ok = o.conform(kind, value, target_lang, hyp_render, accepted, track=track)
    matched = None
    if not ok:
        for cls in o.class_by_kind(kind, track):
            c = o.corrupt(cls, kind, value, target_lang, track)
            if c is not None and o.norm(c) == o.norm(hyp_render):
                matched = cls
                break
    return {
        "locale_form_conformant": ok,
        "failure_class": matched,
        "severity": None if ok else SEVERITY.get(matched, "Major"),
        "track": track,
        "pass": ok,
    }


def _extract(hyp_text: str) -> str | None:
    m = list(_SLOT_RE.finditer(hyp_text))
    return m[-1].group(1) if m else None


def score_item(record: dict, hypothesis: str) -> dict:
    """Score a full hypothesis sentence against a reference record (single entity).
    The record's `track` (default "format") selects the headline formatting gate
    or the opt-in conversion gate."""
    entity = record["entities"][0]
    track = record.get("track", "format")
    hyp_render = _extract(hypothesis)
    if hyp_render is None:
        return {"locale_form_conformant": False, "failure_class": "missing_entity",
                "severity": "Critical", "track": track, "pass": False}
    return score_entity(entity, record["target_lang"], hyp_render, track)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    # the reference passes, a swapped-decimal corruption fails
    ent = {"kind": "number", "semantic": {"value": 1234567.5},
           "accepted_variants": o.accepted_variants("number", 1234567.5, "es")}
    ref = o.render("number", 1234567.5, "es")
    bad = o.corrupt("wrong_decimal_separator", "number", 1234567.5, "es")
    print("ref :", score_entity(ent, "es", ref))
    print("bad :", score_entity(ent, "es", bad))
    # NBSP-vs-NNBSP legality (fr grouping) must NOT flip
    frv = o.render("number", 1234567.5, "fr")
    frv_nbsp = frv.replace(chr(0x202F), chr(0xA0))  # NNBSP -> NBSP (legal)
    entf = {"kind": "number", "semantic": {"value": 1234567.5},
            "accepted_variants": o.accepted_variants("number", 1234567.5, "fr")}
    print("fr nbsp:", score_entity(entf, "fr", frv_nbsp))
