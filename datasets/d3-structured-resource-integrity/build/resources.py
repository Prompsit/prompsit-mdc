#!/usr/bin/env python3
"""D3 resource oracle + validators (deterministic, parser-based).

Scoring rule: the resource SKELETON stays; only values are
translated. One module owns serialization, parsing, the hard-gate scorer, and the
corruption operators (one per failure class) for every format profile that shares
the value-only paradigm: xml (Android resources), json (flat object), properties
(Java), arb (Flutter, carries the non-translatable @@locale metadata field).

No CLDR here - the oracle is the PARSER plus the source skeleton. ASCII-only.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

FORMATS = ("xml", "json", "properties", "arb")
LANGS = ["ca", "es", "fr", "it", "pt-PT", "de", "nl", "pl", "ru"]
SOURCE_LANG = "en"
# ARB @@locale uses BCP-47-ish locale codes
ARB_LOCALE = {"ca": "ca", "es": "es", "fr": "fr", "it": "it", "pt-PT": "pt_PT",
              "de": "de", "nl": "nl", "pl": "pl", "ru": "ru", "en": "en"}

ALL_CLASSES = ["parser_break", "key_path_translated", "schema_changed",
               "value_untranslated",
               "nonvalue_modified_literal", "nonvalue_modified_marked"]
SEVERITY = {"parser_break": "Critical", "key_path_translated": "Major",
            "schema_changed": "Major", "value_untranslated": "Major",
            "nonvalue_modified_literal": "Major", "nonvalue_modified_marked": "Major"}

# Non-translatable values split into two tiers by what signal a real system
# actually has to skip them.
#  - LITERAL (Tier-1): genuinely universal letterless tokens -- pure symbol /
#    number / ratio / degree (16:9, 90) and placeholder-only strings (%1$s).
#    These carry no letters, so any competent system skips them WITHOUT a marker;
#    gated for EVERY format, no signal required.
#  - MARKED (Tier-2): every ALPHABETIC token -- acronyms (DNS/USB/VoLTE) AND
#    brands / proper nouns (Bluetooth, Ethernet, Gmail, ashmem). No engine
#    reliably auto-detects which alphabetic strings are do-not-translate, so they
#    are gated ONLY where an explicit, observable marker is present -- the XML
#    profile, which serializes translatable="false" on non-translatable <string>s
#    (AOSP does this). For json/properties/arb (no native DNT contract) un-marked
#    passthrough is NOT penalized, and we do NOT invent an inline dnt list (that
#    would recreate the D5-2 weakness and overlap D5's glossary track).
_PLACEHOLDER = re.compile(r"%\d*\$?[a-z]|%\d+|\{\w*\}|\$\{\w+\}")


def classify_nontrans(value: str) -> str:
    """'literal' (Tier-1, auto-skippable: no letters -> symbol/number/ratio/
    placeholder) or 'marked' (Tier-2, signal-required: any alphabetic token --
    acronyms AND brands -- no system reliably auto-detects these)."""
    v = value.strip()
    stripped = _PLACEHOLDER.sub("", v)
    if re.fullmatch(r"[\d\W]*", stripped):          # only digits/punct left -> literal
        return "literal"
    return "marked"                                  # any alphabetic token


# the XML profile carries an explicit, observable DNT marker (translatable=false)
MARKER_SIGNALLED_FORMATS = ("xml",)


# --- serialization ------------------------------------------------------------

def _xml_esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _prop_esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace("=", "\\=")


def serialize(fmt: str, entries: list[tuple[str, str]], lang: str,
              nontrans_keys=()) -> str:
    if fmt == "xml":
        nt = set(nontrans_keys)
        body = "".join(
            '  <string name="%s"%s>%s</string>\n'
            % (k, ' translatable="false"' if k in nt else "", _xml_esc(v))
            for k, v in entries)
        return '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n%s</resources>\n' % body
    if fmt == "json":
        return json.dumps({k: v for k, v in entries}, ensure_ascii=False, indent=2)
    if fmt == "properties":
        return "".join("%s=%s\n" % (k, _prop_esc(v)) for k, v in entries)
    if fmt == "arb":
        obj = {"@@locale": ARB_LOCALE[lang]}
        for k, v in entries:
            obj[k] = v
        return json.dumps(obj, ensure_ascii=False, indent=2)
    raise ValueError(fmt)


# --- parsing: text -> (ok, keyvals, meta) ------------------------------------

def parse(fmt: str, text: str):
    try:
        if fmt == "xml":
            root = ET.fromstring(text)
            kv = {s.get("name"): "".join(s.itertext()) for s in root.findall("string")}
            return True, kv, {"root": root.tag}
        if fmt in ("json", "arb"):
            obj = json.loads(text)
            kv, meta = {}, {}
            for k, v in obj.items():
                (meta if k.startswith("@") else kv)[k] = v
            return True, kv, meta
        if fmt == "properties":
            kv = {}
            for line in text.splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                if "=" not in line:
                    return False, {}, {}
                k, v = line.split("=", 1)
                kv[k.strip()] = v
            return True, kv, {}
    except Exception:
        return False, {}, {}
    return False, {}, {}


def _nontrans_by_tier(record: dict) -> dict:
    src = record["src_keyvals"]
    out = {"literal": [], "marked": []}
    for k in record.get("nontrans_keys", []):
        if k in src:
            out[classify_nontrans(src[k])].append(k)
    return out


def has_literal_nonvalue(fmt: str, record: dict) -> bool:
    """Tier-1 hosts: arb @@locale metadata, or any letterless symbol/number/
    placeholder non-translatable value (gated for every format, no signal)."""
    return fmt == "arb" or bool(_nontrans_by_tier(record)["literal"])


def has_marked_nonvalue(fmt: str, record: dict) -> bool:
    """Tier-2 hosts: an alphabetic (acronym/brand/proper-noun) value in a profile
    that carries the explicit DNT marker (XML translatable="false")."""
    return fmt in MARKER_SIGNALLED_FORMATS and bool(_nontrans_by_tier(record)["marked"])


# --- hard-gate scorer ---------------------------------------------------------

def score_item(record: dict, hypothesis: str) -> dict:
    fmt = record["format"]
    ok, kv, meta = parse(fmt, hypothesis)
    src = record["src_keyvals"]
    transl = set(record["translatable_keys"])
    nontrans = set(record.get("nontrans_keys", []))
    want_keys = set(src)

    gates = {"parser_valid": ok}
    if not ok:
        gates.update({"key_path_match": False, "schema_match": False,
                      "value_translated": False,
                      "nonvalue_literal_preserved": False,
                      "nonvalue_marked_preserved": False})
        gates["pass"] = False
        gates["failure_class"] = "parser_break"
        gates["severity"] = "Critical"
        return gates

    # reference values (when the record carries the reference) tell which keys
    # were actually changed by the human; a value legitimately equal to source
    # (proper noun) must not be treated as untranslated.
    ref_kv = {}
    if record.get("reference"):
        _, ref_kv, _ = parse(fmt, record["reference"])
    gates["key_path_match"] = set(kv) == want_keys
    gates["schema_match"] = (len(kv) == len(want_keys)
                             and (fmt != "xml" or meta.get("root") == "resources"))
    gates["value_translated"] = all(
        kv.get(k, "") and kv.get(k) != src[k]
        for k in transl if k in kv and ref_kv.get(k, src[k]) != src[k])
    # tiered non-value preservation. literal/structural -> gated for all
    # formats; marked (alphabetic) -> gated only where the DNT marker is
    # observable (XML).
    lit_ok = marked_ok = True
    if fmt == "arb":  # @@locale is a structural metadata field (Tier-1)
        lit_ok = meta.get("@@locale") == ARB_LOCALE[record["target_lang"]]
    for k in nontrans:
        if k in kv and kv[k] != src[k]:
            if classify_nontrans(src[k]) == "literal":
                lit_ok = False
            elif fmt in MARKER_SIGNALLED_FORMATS:  # un-marked alphabetic not penalized
                marked_ok = False
    gates["nonvalue_literal_preserved"] = lit_ok
    gates["nonvalue_marked_preserved"] = marked_ok

    gates["pass"] = all(v for k, v in gates.items() if k != "pass")
    # classify
    cls = None
    if not gates["key_path_match"]:
        cls = "schema_changed" if not gates["schema_match"] else "key_path_translated"
    elif not gates["schema_match"]:
        cls = "schema_changed"
    elif not gates["value_translated"]:
        cls = "value_untranslated"
    elif not gates["nonvalue_literal_preserved"]:
        cls = "nonvalue_modified_literal"
    elif not gates["nonvalue_marked_preserved"]:
        cls = "nonvalue_modified_marked"
    gates["failure_class"] = cls
    gates["severity"] = SEVERITY.get(cls) if cls else None
    return gates


# --- corruption operators: reference serialization -> wrong hypothesis -------

def corrupt(cls: str, record: dict, ref_text: str):
    fmt = record["format"]
    ok, kv, meta = parse(fmt, ref_text)
    if not ok:
        return None
    if cls == "parser_break":
        if fmt in ("json", "arb"):
            return ref_text[: ref_text.rstrip().rfind("}")]  # drop closing brace
        if fmt == "xml":
            return ref_text.replace("</resources>", "")
        if fmt == "properties":
            return ref_text + '"unterminated\n'  # still parses; instead drop '='
    if cls == "key_path_translated":
        k = next(iter(kv))
        return ref_text.replace('"%s"' % k, '"%s_traducido"' % k, 1) if fmt in ("json", "arb") \
            else ref_text.replace('name="%s"' % k, 'name="%s_traducido"' % k, 1) if fmt == "xml" \
            else re.sub(r"(?m)^%s=" % re.escape(k), "%s_traducido=" % k, ref_text, count=1)
    nt_keys = record.get("nontrans_keys", [])
    if cls == "schema_changed":
        k = next(iter(kv))
        entries = [(kk, vv) for kk, vv in kv.items() if kk != k]  # drop one key
        return serialize(fmt, entries, record["target_lang"], nt_keys)
    if cls == "value_untranslated":
        for k in record["translatable_keys"]:
            if k in kv and kv[k] != record["src_keyvals"][k]:  # the reference changed it
                entries = [(kk, record["src_keyvals"][k] if kk == k else vv)
                           for kk, vv in kv.items()]
                return serialize(fmt, entries, record["target_lang"], nt_keys)
        return None
    if cls in ("nonvalue_modified_literal", "nonvalue_modified_marked"):
        tier = "literal" if cls.endswith("literal") else "marked"
        # Tier-1 structural: corrupt the arb @@locale metadata field
        if tier == "literal" and fmt == "arb":
            return ref_text.replace('"@@locale": "%s"' % ARB_LOCALE[record["target_lang"]],
                                    '"@@locale": "xx"', 1)
        if tier == "marked" and fmt not in MARKER_SIGNALLED_FORMATS:
            return None  # un-marked alphabetic: not a scoreable violation
        for k in nt_keys:
            if k in kv and classify_nontrans(record["src_keyvals"][k]) == tier:
                entries = [(kk, vv + "_x" if kk == k else vv) for kk, vv in kv.items()]
                return serialize(fmt, entries, record["target_lang"], nt_keys)
        return None
    return None


def scoreable_classes(record: dict, ref_text: str) -> list[str]:
    fmt = record["format"]
    out = []
    for cls in ALL_CLASSES:
        if cls == "nonvalue_modified_literal" and not has_literal_nonvalue(fmt, record):
            continue
        if cls == "nonvalue_modified_marked" and not has_marked_nonvalue(fmt, record):
            continue
        c = corrupt(cls, record, ref_text)
        if c is not None and not score_item(record, c)["pass"]:
            out.append(cls)
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("classify:", {v: classify_nontrans(v) for v in
          ["Bluetooth", "DNS", "16:9", "90", "%1$s %2$s", "VoLTE", "ashmem"]})
    # XML with a marked (alphabetic) nontrans (signalled) vs json with the same
    # value (no native marker -> not scoreable there)
    for fmt in ("xml", "json"):
        rec = {"format": fmt, "target_lang": "es",
               "src_keyvals": {"hello": "Hello", "brand": "Bluetooth", "code": "USB"},
               "translatable_keys": ["hello"], "nontrans_keys": ["brand", "code"]}
        ref = serialize(fmt, [("hello", "Hola"), ("brand", "Bluetooth"),
                              ("code", "USB")], "es", rec["nontrans_keys"])
        print("\n[%s] ref pass:" % fmt, score_item(rec, ref)["pass"],
              "| scoreable:", scoreable_classes(rec, ref))
        for c in ALL_CLASSES:
            bad = corrupt(c, rec, ref)
            print("  ", c, "->",
                  "rejected" if bad and not score_item(rec, bad)["pass"]
                  else ("n/a" if bad is None else "MISS"))
