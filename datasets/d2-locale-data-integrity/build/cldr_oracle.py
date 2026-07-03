#!/usr/bin/env python3
"""D2 CLDR oracle (Babel) - single source of truth for locale-data rendering.

For each (entity kind, locale) this module produces three things, mirroring the
role D1's assets.py + validators.py play for inline tokens:

  1. the canonical CLDR rendering (the reference value in the target locale);
  2. the set of locale-LEGAL accepted variants - whitespace-class equivalence
     (regular space / NBSP / NNBSP / thin space are interchangeable for
     grouping), short/medium/long date forms, currency symbol vs ISO code -
     consumed by K2 to bound validator false positives;
  3. corruption operators that emit a WRONG rendering, one per D2 failure class,
     consumed by the contrastive pack and the K1 engine panel.

Scoring rule: the value must ADAPT to the target locale.
Formatting (decimal/grouping/date/currency rendering and localized unit symbols)
is deterministic from CLDR and scored here. The underlying semantic value is
preserved.

Babel bundles CLDR; the (babel, cldr) version pair is recorded in the manifest.
PyICU is deliberately avoided (Windows install pain). ASCII-only source.
"""
from __future__ import annotations

import datetime
import re

import babel
from babel.numbers import (format_currency, format_decimal,
                           get_currency_precision, get_currency_symbol)
from babel.dates import format_date
from babel.units import format_unit

# en-US source -> 9 target locales. D2 is keyed by LOCALE (a language code alone
# underspecifies separators/dates/currency); langs match the D1 core rectangle.
SOURCE_LANG = "en"
SOURCE_LOCALE = "en_US"
LOCALES = {
    "ca": "ca_ES", "es": "es_ES", "fr": "fr_FR", "it": "it_IT", "pt-PT": "pt_PT",
    "de": "de_DE", "nl": "nl_NL", "pl": "pl_PL", "ru": "ru_RU",
}
TARGET_LANGS = list(LOCALES)
KINDS = ("number", "date", "currency", "unit")

BABEL_VERSION = babel.__version__
try:  # CLDR version bundled with this Babel
    from babel.localedata import _cldr_version  # type: ignore
    CLDR_VERSION = _cldr_version
except Exception:  # pragma: no cover - attribute name varies across babel
    CLDR_VERSION = "bundled-with-babel-%s" % BABEL_VERSION

# whitespace chars CLDR / real systems use interchangeably for digit grouping
_WS = "".join(chr(c) for c in (0x20, 0xA0, 0x202F, 0x2009))  # space NBSP NNBSP thin
_WS_RE = re.compile("[" + _WS + "]")


def norm(s: str) -> str:
    """Comparison key: collapse every space-class char to one ASCII space. A
    system that emits NBSP where CLDR emits NNBSP is still locale-legal, so the
    grouping whitespace must not drive a false positive (the K2 risk)."""
    return _WS_RE.sub(" ", s).strip()


def _loc(lang: str) -> str:
    return SOURCE_LOCALE if lang == SOURCE_LANG else LOCALES[lang]


def _to_date(value):
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(value)


def quantize_currency(amount: float, code: str) -> float:
    """Round an amount to the currency's CLDR fraction digits. Keeps the
    surface a FAITHFUL rendering of semantic.amount: a JPY amount (0 digits) is
    integral, so `format_currency(amount, JPY, en_US)` is lossless and the
    reference target render no longer depends on a precision the input never
    shows."""
    return round(amount, get_currency_precision(code))


# --- rendering (reference) ----------------------------------------------------

def render(kind: str, value, lang: str, track: str = "format") -> str:
    """Canonical CLDR rendering of an entity in `lang` (the reference).

    Unit values are rendered AS-IS in the target locale's CLDR form (number
    separators + localized unit symbol, e.g. ru `5 mi` -> the same semantic
    value formatted for ru)."""
    loc = _loc(lang)
    if kind == "number":
        return format_decimal(value, locale=loc)
    if kind == "currency":
        amount, code = value
        return format_currency(amount, code, locale=loc)
    if kind == "date":
        return format_date(_to_date(value), format="medium", locale=loc)
    if kind == "unit":
        amount, unit = value
        return format_unit(amount, unit, length="short", locale=loc)
    raise ValueError("unknown kind %r" % kind)


# --- accepted (locale-legal) variants -----------------------------------------

def accepted_variants(kind: str, value, lang: str, track: str = "format") -> list[str]:
    """All renderings a correct localizer may legally produce. norm() absorbs
    grouping-whitespace differences, so variants enumerate only genuinely
    distinct legal forms (date length, currency symbol vs ISO code, unit
    short/long)."""
    loc = _loc(lang)
    out = [render(kind, value, lang, track)]
    if kind == "date":
        d = _to_date(value)
        for fmt in ("short", "long"):
            out.append(format_date(d, format=fmt, locale=loc))
    elif kind == "currency":
        amount, code = value
        sym = get_currency_symbol(code, locale=loc)
        out.append(format_currency(amount, code, locale=loc).replace(sym, code))
    elif kind == "unit":
        amount, unit = value
        out.append(format_unit(amount, unit, length="long", locale=loc))
    seen, uniq = set(), []
    for s in out:
        k = norm(s)
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    return uniq


def conform(kind: str, value, lang: str, hyp: str,
            accepted: list[str] | None = None, track: str = "format") -> bool:
    """True iff hypothesis rendering is a locale-legal form for this entity."""
    acc = accepted if accepted is not None else accepted_variants(kind, value, lang, track)
    return norm(hyp) in {norm(a) for a in acc}


def _unit_symbol(amount, unit, loc: str) -> str:
    """The locale unit symbol alone (the short-form rendering minus its formatted
    number), e.g. ru `кг`, de `km`. Used to detect locales that localize the
    symbol (ru/Cyrillic) for the wrong_unit_format class. Returns "" if the
    number token cannot be isolated (class then does not apply)."""
    full = format_unit(amount, unit, length="short", locale=loc)
    num = format_decimal(amount, locale=loc)
    return full.replace(num, "").strip() if num in full else ""


# --- corruption operators: one per failure class, emit a WRONG rendering ------
# Each returns a wrong string, or None if the class does not apply to this
# entity/locale. Callers verify wrongness with conform().

def _swap_decimal(s: str) -> str:
    if re.search(r"\d,\d", s):
        return re.sub(r"(\d),(\d)", r"\1.\2", s)
    if re.search(r"\d\.\d", s):
        return re.sub(r"(\d)\.(\d)", r"\1,\2", s)
    return s


def corrupt(cls: str, kind: str, value, lang: str, track: str = "format"):
    ref = render(kind, value, lang, track)
    src = render(kind, value, SOURCE_LANG, track)  # unlocalized en-US form
    # --- format-track classes (headline) --------------------------------------
    if cls == "wrong_decimal_separator":
        out = _swap_decimal(ref)
        return out if out != ref else None
    if cls == "wrong_grouping":
        # drop ONLY a grouping separator sitting between digits (not the space
        # before a unit symbol or currency sign)
        out = re.sub("(?<=\\d)[" + _WS + "](?=\\d)", "", ref)  # NBSP/NNBSP grouping
        out = re.sub(r"(?<=\d)\.(?=\d{3}(\D|$))", "", out)      # '.' grouping
        return out if norm(out) != norm(ref) else None
    if cls == "mis_converted_datetime":
        if kind != "date":
            return None
        return src if norm(src) != norm(ref) else None  # en-US month-first form
    if cls == "broken_currency_format":
        if kind != "currency":
            return None
        return src if norm(src) != norm(ref) else None  # "$1,234.50" in target
    if cls == "wrong_unit_format":
        # FORMAT failure: target-locale number, but the SOURCE (en) unit symbol
        # kept un-localized (ru `5 км` -> `5 km`). Applies only to locales that
        # localize the symbol; None elsewhere (de/es/.. share the Latin symbol).
        if kind != "unit" or lang == SOURCE_LANG:
            return None
        amount, unit = value  # value AS-IS (no conversion in the format track)
        ref_sym = _unit_symbol(amount, unit, _loc(lang))
        src_sym = _unit_symbol(amount, unit, SOURCE_LOCALE)
        if not ref_sym or not src_sym or norm(ref_sym) == norm(src_sym):
            return None
        out = ref.replace(ref_sym, src_sym)
        return out if norm(out) != norm(ref) else None
    return None


FORMAT_CLASS_BY_KIND = {
    "number": ["wrong_decimal_separator", "wrong_grouping"],
    "currency": ["wrong_decimal_separator", "wrong_grouping", "broken_currency_format"],
    "date": ["mis_converted_datetime"],
    "unit": ["wrong_decimal_separator", "wrong_grouping", "wrong_unit_format"],
}
FORMAT_CLASSES = ["wrong_decimal_separator", "wrong_grouping",
                  "mis_converted_datetime", "broken_currency_format",
                  "wrong_unit_format"]
ALL_CLASSES = FORMAT_CLASSES
TRACK_CLASSES = {"format": FORMAT_CLASSES}
CLASS_BY_KIND = FORMAT_CLASS_BY_KIND


def class_by_kind(kind: str, track: str = "format") -> list[str]:
    return FORMAT_CLASS_BY_KIND.get(kind, [])


def scoreable_classes(kind: str, value, lang: str, track: str = "format") -> list[str]:
    """Classes that yield a genuinely-wrong corruption for this entity+locale
    within `track`."""
    out = []
    for cls in class_by_kind(kind, track):
        c = corrupt(cls, kind, value, lang, track)
        if c is not None and not conform(kind, value, lang, c, track=track):
            out.append(cls)
    return out


if __name__ == "__main__":  # smoke (run with PYTHONUTF8=1 on Windows)
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("babel", BABEL_VERSION, "cldr", CLDR_VERSION)
    samples = [("number", 1234567.5), ("currency", (1234.5, "EUR")),
               ("date", "2026-03-09"), ("unit", (5, "length-mile"))]
    for lang in [SOURCE_LANG] + TARGET_LANGS:
        cells = [f"{k}={render(k, v, lang)!r}" for k, v in samples]
        print(f"{lang:6} " + "  ".join(cells))
    print()
    for k, v in samples:
        cov = {lang: scoreable_classes(k, v, lang) for lang in TARGET_LANGS}
        print(f"scoreable[format] {k}: es={cov['es']} ru={cov['ru']} de={cov['de']}")
    # wrong_unit_format fires where the symbol localizes (ru).
    uv = (1234.5, "mass-pound")
    print("unit FORMAT ru:", render("unit", uv, "ru", "format"),
          scoreable_classes("unit", uv, "ru", "format"))
    print("unit FORMAT de:", render("unit", uv, "de", "format"),
          scoreable_classes("unit", uv, "de", "format"))
    print("JPY quantize 7.5 ->", quantize_currency(7.5, "JPY"),
          "| EUR 49.999 ->", quantize_currency(49.999, "EUR"))
