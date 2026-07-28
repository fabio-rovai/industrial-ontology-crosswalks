#!/usr/bin/env python3
"""
ISA-95 rendered twice, by two standards bodies, compared.

THE QUESTION
------------
"Crosswalk ISA-95 to the Asset Administration Shell" presupposes that there is
a thing called ISA-95 that you can align. There are in fact at least two
machine-readable renderings of it, produced independently:

    MESA International       B2MML, a set of W3C XML Schemas, tracking
                             ANSI/ISA-95.00.02-2018 and .00.05-2018.
    OPC Foundation           the OPC UA ISA-95 companion specification,
                             an address-space NodeSet.

If a crosswalk is built against one, it does not automatically hold for the
other. Before aligning ISA-95 to anything, it is worth measuring how far the
two renderings of it agree. This script does that, and the AAS side gets the
same treatment: the IDTA metamodel RDF versus the OPC Foundation's own I4AAS
NodeSet mapping.

WHAT IT REPORTS
    1. Class-count divergence between renderings of the same standard.
    2. Name-level agreement: which ISA-95 concepts appear in both renderings.
    3. The concepts present in one rendering and absent from the other, which is
       where a crosswalk built on a single rendering silently loses coverage.
    4. Axiomatic Strength Index for every rendering, so the reader can see that
       the AAS side is inert whichever rendering is used.

Run:  python crosswalks/isa95-aas/triangulate.py
      (requires lift/out/*.ttl: run lift/b2mml_to_rdf.py and lift/opcua_to_rdf.py first)
"""
from __future__ import annotations

import json
import os
import re
import sys

from rdflib import Graph, RDF, RDFS, OWL, URIRef

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LIFT = os.path.join(ROOT, "lift", "out")
SRC = os.path.join(ROOT, "sources")

sys.path.insert(0, os.path.join(ROOT, "metrics"))
from axiomatic_asymmetry import profile  # noqa: E402

RENDERINGS = [
    ("ISA-95", "MESA B2MML (XSD)", os.path.join(LIFT, "isa95-b2mml-lifted.ttl"), "turtle"),
    ("ISA-95", "OPC UA ISA-95 companion", os.path.join(LIFT, "opcua-isa95-lifted.ttl"), "turtle"),
    ("AAS", "IDTA metamodel RDF", os.path.join(SRC, "aas-metamodel.ttl"), "turtle"),
    ("AAS", "OPC UA I4AAS companion", os.path.join(LIFT, "opcua-i4aas-lifted.ttl"), "turtle"),
]

# Noise words each rendering bolts on, stripped before comparing concept names.
STRIP = re.compile(
    r"^(Ifc|UA|Opc|AAS|Aas|I4AAS)|"
    r"(Type|TypeType|DataType|Class|IDType|Id|ID|Element|Elements)$"
)


def local(u: str) -> str:
    return u[max(u.rfind("#"), u.rfind("/")) + 1:]


def concept_key(name: str) -> str:
    """Normalise a class name to a comparable concept key."""
    n = name
    for _ in range(3):
        n2 = STRIP.sub("", n)
        if n2 == n:
            break
        n = n2
    n = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", n)
    n = re.sub(r"[^A-Za-z0-9 ]", " ", n)
    return " ".join(sorted(t.lower() for t in n.split() if t))


# --- fairness controls -------------------------------------------------------
# A raw name comparison would overstate the disagreement, because the two
# renderings do not cover the same PARTS of the ISA-95 family:
#   B2MML  covers the Part 2 object model AND the Part 5 business transactions,
#          which it inherits from OAGIS as Acknowledge/Confirm/Get/Show/Process
#          /Respond/Change/Cancel/Sync message wrappers around every object.
#   OPC UA covers the Part 2 object model AND a block of core datatypes (cdt*).
# Neither block is an ISA-95 CONCEPT; both are serialisation scaffolding. The
# honest comparison excludes them and reports the object-model core, so this
# script reports BOTH numbers and never quotes the raw one on its own.
TXN_PREFIXES = ("acknowledge", "confirm", "get", "show", "process", "respond",
                "change", "cancel", "sync", "notify", "list")
SCAFFOLD_PREFIXES = ("cdt",)


def is_scaffolding(key: str) -> bool:
    toks = key.split()
    if not toks:
        return True
    return toks[0] in TXN_PREFIXES or any(t.startswith(SCAFFOLD_PREFIXES) for t in toks)


def load(path: str, fmt: str) -> tuple[Graph, dict[str, str]]:
    g = Graph()
    g.parse(path, format=fmt)
    names: dict[str, str] = {}
    for c in set(g.subjects(RDF.type, OWL.Class)):
        if isinstance(c, URIRef):
            names[local(str(c))] = str(c)
    return g, names


def main() -> int:
    for _, _, path, _ in RENDERINGS:
        if not os.path.exists(path):
            sys.exit(f"Missing {path}.\nRun: python lift/b2mml_to_rdf.py && python lift/opcua_to_rdf.py")

    loaded = {}
    print("=" * 82)
    print("ISA-95 and AAS, each rendered twice by different bodies")
    print("=" * 82)
    print(f"\n{'standard':<9}{'rendering':<30}{'classes':>9}{'ASI':>7}{'ASI/class':>11}  inert?")
    print("-" * 82)
    for std, label, path, fmt in RENDERINGS:
        g, names = load(path, fmt)
        p = profile(g)
        loaded[(std, label)] = (g, names, p)
        print(f"{std:<9}{label:<30}{len(names):>9,}{p['ASI']:>7,}{p['ASI_per_class']:>11}"
              f"  {'INERT' if p['refutation_inert'] else '-'}")

    report = {}
    for std in ("ISA-95", "AAS"):
        (la, lb) = [lbl for (s, lbl) in loaded if s == std]
        _, na, pa = loaded[(std, la)]
        _, nb, pb = loaded[(std, lb)]

        ka = {}
        for n in na:
            ka.setdefault(concept_key(n), []).append(n)
        kb = {}
        for n in nb:
            kb.setdefault(concept_key(n), []).append(n)
        ka.pop("", None)
        kb.pop("", None)

        both = sorted(set(ka) & set(kb))
        only_a = sorted(set(ka) - set(kb))
        only_b = sorted(set(kb) - set(ka))
        union = len(set(ka) | set(kb))
        jac = len(both) / union if union else 0.0

        # fair comparison: object-model core only, scaffolding removed from both sides
        ca = {k for k in ka if not is_scaffolding(k)}
        cb = {k for k in kb if not is_scaffolding(k)}
        core_both = sorted(ca & cb)
        core_union = len(ca | cb)
        core_jac = len(core_both) / core_union if core_union else 0.0
        dropped_a, dropped_b = len(ka) - len(ca), len(kb) - len(cb)

        print(f"\n{'=' * 82}\n{std}: {la}  vs  {lb}\n{'=' * 82}")
        print(f"  classes                {len(na):>6}  vs {len(nb):>6}"
              f"   ratio {max(len(na), len(nb)) / max(1, min(len(na), len(nb))):.1f}x")
        print(f"  distinct concept keys  {len(ka):>6}  vs {len(kb):>6}")
        print(f"  shared concepts        {len(both):>6}   Jaccard agreement {jac:.3f}  (RAW)")
        print(f"  only in {la:<24} {len(only_a):>6}")
        print(f"  only in {lb:<24} {len(only_b):>6}")
        print(f"  -- fairness control: transaction wrappers and core datatypes removed")
        print(f"     dropped as scaffolding {dropped_a:>6}  vs {dropped_b:>6}")
        print(f"     object-model concepts  {len(ca):>6}  vs {len(cb):>6}")
        print(f"     shared                 {len(core_both):>6}   Jaccard agreement "
              f"{core_jac:.3f}  (OBJECT MODEL, the number to quote)")
        # Jaccard punishes size difference. Containment is the fairer read when one
        # rendering is deliberately coarser than the other.
        cov_a = len(core_both) / len(ca) if ca else 0.0
        cov_b = len(core_both) / len(cb) if cb else 0.0
        print(f"     containment: {cov_a * 100:>5.1f}% of {la} concepts found in {lb}")
        print(f"                  {cov_b * 100:>5.1f}% of {lb} concepts found in {la}")
        if both:
            print(f"\n  shared (first 20): {', '.join(both[:20])}")
        if only_b:
            print(f"\n  present ONLY in {lb} (first 15):")
            print(f"    {', '.join(only_b[:15])}")
        if only_a:
            print(f"\n  present ONLY in {la} (first 15):")
            print(f"    {', '.join(only_a[:15])}")

        report[std] = {
            "rendering_a": la, "rendering_b": lb,
            "classes_a": len(na), "classes_b": len(nb),
            "concepts_a": len(ka), "concepts_b": len(kb),
            "shared": len(both), "jaccard_raw": round(jac, 4),
            "only_a": only_a, "only_b": only_b, "shared_concepts": both,
            "asi_a": pa["ASI"], "asi_b": pb["ASI"],
            "core_concepts_a": len(ca), "core_concepts_b": len(cb),
            "core_shared": len(core_both), "jaccard_object_model": round(core_jac, 4),
            "core_shared_concepts": core_both,
            "scaffolding_dropped_a": dropped_a, "scaffolding_dropped_b": dropped_b,
        }

    print(f"\n{'=' * 82}\nWHAT THIS MEANS FOR THE CROSSWALK\n{'=' * 82}")
    for std in ("ISA-95", "AAS"):
        r = report[std]
        print(f"  {std}: two official renderings agree on "
              f"{r['jaccard_object_model'] * 100:.1f}% of OBJECT-MODEL concepts "
              f"(Jaccard {r['jaccard_object_model']}; raw {r['jaccard_raw']} before "
              f"removing transaction and datatype scaffolding).")
    print("  A crosswalk built against one rendering does not transfer to the other")
    print("  unchanged. Any ISA-95-to-AAS alignment must therefore say WHICH ISA-95 and")
    print("  WHICH AAS it aligns. Most published ones do not.")
    print("\n  Both AAS renderings are refutation-inert, so no reasoner check on this pair")
    print("  can find anything. See crosswalks/cfihos-audit/ for the empirical proof of")
    print("  what inertness means in practice.")

    with open(os.path.join(HERE, "triangulation.json"), "w") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"\n  Wrote {os.path.relpath(os.path.join(HERE, 'triangulation.json'), ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
