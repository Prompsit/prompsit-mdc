#!/usr/bin/env python3
"""Contrastive corruption pack for the core dev split.

For every dev record and every applicable error class, produce a minimal
corrupted variant of the human reference and VERIFY with the real D1
validators that the targeted gate actually fails (verify-or-skip — no
unverified example ships). Dev split only: corrupting test/hidden references in
a public file would leak the held-out references.

Output: data/contrastive.dev.jsonl
  {item_id, target_lang, error_class, corrupted_reference,
   failed_gates (observed), expected_gate}
"""
import json, re, sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "build"))
from validators import score_item

TAG_PAIR = re.compile(r"<(b|i|u|em|strong|a|code|span|g|xliff:g)\b[^>]*>")
GATE_OF = {
    "missing_asset": "inventory",
    "extra_asset": "inventory",
    "corrupted_syntax": "placeholder_syntax",
    "invalid_nesting": "nesting",
    "moved_paired_tag": "nesting",
    "wrong_order": "order",
    "lost_attribute": "attributes",
    "broken_icu": "icu_syntax",
    "dnt_violation": "verbatim",
}

def find_in_ref(rec, ref, types=None, need_pair=False, need_attrs=False):
    for a in rec["assets"]:
        if types and a["type"] not in types:
            continue
        if need_pair and not a.get("paired"):
            continue
        if need_attrs and not a.get("attrs"):
            continue
        if a["raw"] and a["raw"] in ref:
            yield a

def corrupt(rec, ref, cls):
    """Return corrupted ref or None (operator not applicable)."""
    if cls == "missing_asset":
        for a in find_in_ref(rec, ref):
            return ref.replace(a["raw"], "", 1)
    if cls == "extra_asset":
        for a in find_in_ref(rec, ref, types={"printf_placeholder",
                "named_brace", "positional_brace", "template_var"}):
            i = ref.find(a["raw"])
            return ref[:i] + a["raw"] + " " + ref[i:]
    if cls == "corrupted_syntax":
        out = re.sub(r"%(\d*\$?[sd])", r"% \1", ref, count=1)
        if out == ref:
            out = re.sub(r"\{(\d+)\}", r"{ \1 }", ref, count=1)
        if out == ref:
            out = re.sub(r"\{([A-Za-z_][\w.-]*)\}", r"{ \1 }", ref, count=1)
        return out if out != ref else None
    if cls in ("invalid_nesting", "moved_paired_tag"):
        for a in find_in_ref(rec, ref, need_pair=True):
            if not a["raw"].startswith("<") or a["raw"].startswith("</"):
                continue
            close = next((b["raw"] for b in rec["assets"]
                          if b["id"] == a.get("pair")), None)
            if close and close in ref and ref.find(a["raw"]) < ref.find(close):
                i, j = ref.find(a["raw"]), ref.find(close)
                # swap open and close -> </x> ... <x>
                return ref[:i] + close + ref[i+len(a["raw"]):j] + a["raw"] + ref[j+len(close):]
    if cls == "wrong_order":
        # the order gate tracks only NON-positional printf placeholders
        # (%s, %d ... without N$); positional ones are legally reorderable
        import re as _re
        seen = []
        for a in find_in_ref(rec, ref, types={"printf_placeholder"}):
            if _re.search(r"\d\$", a["raw"]):
                continue
            if a["raw"] not in [s["raw"] for s in seen]:
                seen.append(a)
            if len(seen) == 2:
                x, y = seen[0]["raw"], seen[1]["raw"]
                i, j = ref.find(x), ref.find(y)
                if i < 0 or j < 0 or i == j:
                    return None
                if i > j:
                    x, y, i, j = y, x, j, i
                return ref[:i] + y + ref[i+len(x):j] + x + ref[j+len(y):]
        return None
    if cls == "lost_attribute":
        for a in find_in_ref(rec, ref, need_attrs=True):
            m = re.match(r"<([\w:]+)", a["raw"])
            if m and not a["raw"].startswith("</"):
                bare = "<%s>" % m.group(1)
                if a["raw"] != bare:
                    return ref.replace(a["raw"], bare, 1)
    if cls == "broken_icu":
        # drop the ICU block's final closing brace -> unbalanced braces,
        # the icu_syntax gate's depth scan never closes (an 'other'-keyword
        # drop is NOT sufficient: =N{...} branches keep the gate green)
        k = ref.rfind("}")
        if k < 0:
            return None
        return ref[:k] + ref[k+1:]
    if cls == "dnt_violation":
        for a in find_in_ref(rec, ref, types={"dnt"}):
            raw = a["raw"]
            mut = raw.lower() if raw.lower() != raw else raw.upper()
            if mut == raw:
                mut = raw[:-1] if len(raw) > 2 else raw + "x"
            return ref.replace(raw, mut, 1)
    return None

def main():
    recs = [json.loads(l) for l in open(PKG / "data" / "dev.jsonl",
                                        encoding="utf-8")]
    out, skipped = [], {"not_applicable": 0, "gate_not_tripped": 0}
    for r in recs:
        refs5 = None  # references list only needed for DNT extraction context
        for cls in r["failure_opportunity_tags"]:
            bad = corrupt(r, r["reference"], cls)
            if bad is None or bad == r["reference"]:
                skipped["not_applicable"] += 1
                continue
            gates = score_item(r["source"], bad, refs5)
            target = GATE_OF[cls]
            if gates.get(target, True):
                skipped["gate_not_tripped"] += 1
                continue
            out.append({"item_id": r["item_id"],
                        "target_lang": r["target_lang"],
                        "error_class": cls,
                        "expected_gate": target,
                        "failed_gates": sorted(k for k, v in gates.items()
                                               if k != "pass" and not v),
                        "corrupted_reference": bad})
    with open(PKG / "data" / "contrastive.dev.jsonl", "w",
              encoding="utf-8", newline="\n") as fh:
        for o in out:
            fh.write(json.dumps(o, ensure_ascii=False) + "\n")
    import collections
    per = collections.Counter(o["error_class"] for o in out)
    print(json.dumps({"pairs": len(out), "per_class": dict(per),
                      "skipped": skipped,
                      "dev_records": len(recs)}, indent=1))

if __name__ == "__main__":
    main()
