#!/usr/bin/env python3
"""
Axiomatic asymmetry: measure whether a standard's ontology can be contradicted
at all, and what that means for crosswalking it.

THE CLAIM
---------
A crosswalk is usually presented as a symmetric artefact: standard A relates to
standard B. Logically it is not symmetric, because the two sides rarely carry
comparable amounts of contradiction-capable axiom.

An OWL ontology can only make a class unsatisfiable if it contains at least one
axiom capable of deriving the bottom concept. In the profile these standards
actually use, those are:

    disjointness      owl:disjointWith, owl:AllDisjointClasses, owl:disjointUnionOf
    negation          owl:complementOf
    counting          owl:maxCardinality, owl:cardinality, and their qualified forms
    property function owl:FunctionalProperty, owl:InverseFunctionalProperty
    property algebra  owl:AsymmetricProperty, owl:IrreflexiveProperty,
                      owl:propertyDisjointWith
    identity          owl:AllDifferent, owl:differentFrom

Call the count of these the Axiomatic Strength Index (ASI). If a TBox has
ASI = 0, then adding any set of subsumption or equivalence axioms between named
classes cannot make any class unsatisfiable: there is no path to bottom. Such an
ontology is REFUTATION-INERT. It will pass every consistency check and every
coherence check you ever run against it, not because the modelling is right but
because nothing in it can be wrong.

The consequence for crosswalking: when a rich ontology is aligned to an inert
one, every unsatisfiability the merge produces surfaces on the rich side. The
inert side looks clean. Practitioners read that as "our standard is fine and
theirs is broken", when what they measured was the asymmetry of the axioms, not
the quality of the model.

This module measures ASI per standard and the asymmetry ratio per pair.
reasoning/ then tests the inertness claim empirically with HermiT rather than
resting on the argument above.

Usage:
    python metrics/axiomatic_asymmetry.py                # table to stdout
    python metrics/axiomatic_asymmetry.py --write        # also refresh RESULTS.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

from rdflib import Graph, RDF, RDFS, OWL, URIRef, BNode

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "sources")

# label -> (filename, rdf format or None to sniff, one-line provenance)
ONTOLOGIES: list[tuple[str, str, str | None, str]] = [
    ("IDO / ISO 15926-14", "ido-lis14-core.ttl", "turtle", "POSC Caesar, LIS14 core"),
    ("ISO 15926-2:2003", "iso15926-2-2003.ttl", "turtle", "NIST mirror of the PCA OWL rendering"),
    ("IFC4 ADD2", "ifc4-add2.ttl", "turtle", "ifcOWL, ISO 16739"),
    ("CFIHOS V2.0 (IDO)", "cfihos-v2.0-ido.owl", None, "tecnomod-um, generated from IOGP Excel"),
    ("AAS metamodel", "aas-metamodel.ttl", "turtle", "IDTA, RDF rendering of the UML metamodel"),
    ("SAREF core", "saref-core-v3.2.1.ttl", "turtle", "ETSI"),
    ("SAREF4INMA", "saref4inma-v1.1.2.ttl", "turtle", "ETSI, industry and manufacturing"),
]

# Cardinality predicates that can force a contradiction. Note that minCardinality
# and someValuesFrom are deliberately EXCLUDED: they can only ever add
# obligations, never derive bottom on their own.
CARDINALITY_PREDS = [
    OWL.maxCardinality,
    OWL.cardinality,
    OWL.maxQualifiedCardinality,
    OWL.qualifiedCardinality,
]

CONTRADICTION_CAPABLE_TYPES = [
    OWL.FunctionalProperty,
    OWL.InverseFunctionalProperty,
    OWL.AsymmetricProperty,
    OWL.IrreflexiveProperty,
]


def load(path: str, fmt: str | None) -> Graph:
    g = Graph()
    if fmt:
        g.parse(path, format=fmt)
    else:
        g.parse(path)
    return g


def named_classes(g: Graph) -> set[URIRef]:
    cls = set(g.subjects(RDF.type, OWL.Class)) | set(g.subjects(RDF.type, RDFS.Class))
    for s, o in g.subject_objects(RDFS.subClassOf):
        if isinstance(s, URIRef):
            cls.add(s)
        if isinstance(o, URIRef):
            cls.add(o)
    cls -= {OWL.Thing, OWL.Nothing, RDFS.Resource, RDFS.Class, OWL.Class}
    return {c for c in cls if isinstance(c, URIRef)}


def _list_len(g: Graph, head) -> int:
    n, seen = 0, set()
    while head and head != RDF.nil and head not in seen:
        seen.add(head)
        n += 1
        head = g.value(head, RDF.rest)
    return n


def profile(g: Graph) -> dict:
    """Count every axiom family, splitting contradiction-capable from the rest."""
    p: dict[str, int] = {}

    p["classes"] = len(named_classes(g))
    p["subclass_axioms"] = sum(1 for _ in g.triples((None, RDFS.subClassOf, None)))
    p["equivalent_class"] = sum(1 for _ in g.triples((None, OWL.equivalentClass, None)))
    p["object_properties"] = sum(1 for _ in g.subjects(RDF.type, OWL.ObjectProperty))
    p["datatype_properties"] = sum(1 for _ in g.subjects(RDF.type, OWL.DatatypeProperty))
    p["domain"] = sum(1 for _ in g.triples((None, RDFS.domain, None)))
    p["range"] = sum(1 for _ in g.triples((None, RDFS.range, None)))
    p["restrictions"] = sum(1 for _ in g.subjects(RDF.type, OWL.Restriction))
    p["inverse_of"] = sum(1 for _ in g.triples((None, OWL.inverseOf, None)))

    # --- contradiction-capable families ---
    # owl:disjointWith is symmetric and IFC4 asserts BOTH directions, so counting
    # triples double-counts it (4,886 triples are 2,443 distinct pairs). Count
    # distinct unordered pairs instead, or the comparison across ontologies is
    # skewed toward whichever one happens to serialise symmetry explicitly.
    dj_pairs: set[tuple[str, str]] = set()
    for a, b in g.subject_objects(OWL.disjointWith):
        if isinstance(a, URIRef) and isinstance(b, URIRef):
            dj_pairs.add(tuple(sorted((str(a), str(b)))))
    for adc in g.subjects(RDF.type, OWL.AllDisjointClasses):
        head = g.value(adc, OWL.members)
        members, seen = [], set()
        while head and head != RDF.nil and head not in seen:
            seen.add(head)
            f = g.value(head, RDF.first)
            if isinstance(f, URIRef):
                members.append(str(f))
            head = g.value(head, RDF.rest)
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                dj_pairs.add(tuple(sorted((members[i], members[j]))))
    p["disjointness"] = len(dj_pairs)
    p["disjoint_union"] = sum(1 for _ in g.triples((None, OWL.disjointUnionOf, None)))
    p["complement"] = sum(1 for _ in g.triples((None, OWL.complementOf, None)))
    p["cardinality_max"] = sum(sum(1 for _ in g.triples((None, pred, None))) for pred in CARDINALITY_PREDS)
    p["functional_props"] = sum(
        sum(1 for _ in g.subjects(RDF.type, t)) for t in CONTRADICTION_CAPABLE_TYPES
    )
    p["property_disjoint"] = sum(1 for _ in g.triples((None, OWL.propertyDisjointWith, None)))
    p["identity"] = (
        sum(1 for _ in g.subjects(RDF.type, OWL.AllDifferent))
        + sum(1 for _ in g.triples((None, OWL.differentFrom, None)))
    )

    p["ASI"] = (
        p["disjointness"]
        + p["disjoint_union"]
        + p["complement"]
        + p["cardinality_max"]
        + p["functional_props"]
        + p["property_disjoint"]
        + p["identity"]
    )
    p["refutation_inert"] = p["ASI"] == 0
    # ASI normalised per named class: the honest comparator, since IFC4 is 26x
    # bigger than IDO and raw counts would just re-measure size.
    p["ASI_per_class"] = round(p["ASI"] / p["classes"], 3) if p["classes"] else 0.0
    return p


PAIRS = [
    ("IDO / ISO 15926-14", "IFC4 ADD2", "crosswalks/ido-ifc"),
    ("CFIHOS V2.0 (IDO)", "IDO / ISO 15926-14", "crosswalks/cfihos-audit"),
    ("SAREF4INMA", "AAS metamodel", "crosswalks/isa95-aas"),
    ("SAREF4INMA", "IFC4 ADD2", "crosswalks/saref-opcua"),
    ("ISO 15926-2:2003", "IFC4 ADD2", "crosswalks/ido-ifc"),
    ("CFIHOS V2.0 (IDO)", "IFC4 ADD2", "crosswalks/cfihos-audit"),
]


def asymmetry(a: dict, b: dict) -> dict:
    hi, lo = max(a["ASI"], b["ASI"]), min(a["ASI"], b["ASI"])
    return {
        "asi_high": hi,
        "asi_low": lo,
        # unbounded when one side is inert: report it as such rather than
        # dividing by a fudged 1 and pretending the number means something.
        "ratio": None if lo == 0 else round(hi / lo, 1),
        "inert_side": lo == 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="refresh metrics/RESULTS.md and metrics/asi.json")
    args = ap.parse_args()

    profiles: dict[str, dict] = {}
    provenance: dict[str, str] = {}
    for label, fname, fmt, prov in ONTOLOGIES:
        path = os.path.join(SRC, fname)
        if not os.path.exists(path):
            sys.exit(f"Missing {path}. Run: python scripts/fetch_sources.py --relock")
        profiles[label] = profile(load(path, fmt))
        provenance[label] = prov

    cols = [
        ("classes", "classes"),
        ("disjointness", "disjoint"),
        ("cardinality_max", "max-card"),
        ("functional_props", "func/inv"),
        ("complement", "compl"),
        ("ASI", "ASI"),
        ("ASI_per_class", "ASI/class"),
    ]
    head = f"{'standard':<22}" + "".join(f"{lbl:>12}" for _, lbl in cols) + f"{'inert?':>9}"
    lines = [head, "-" * len(head)]
    for label, _, _, _ in ONTOLOGIES:
        p = profiles[label]
        row = f"{label:<22}"
        for key, _ in cols:
            v = p[key]
            row += f"{v:>12,}" if isinstance(v, int) else f"{v:>12}"
        row += f"{'INERT' if p['refutation_inert'] else '-':>9}"
        lines.append(row)

    lines.append("")
    lines.append(f"{'pair':<44}{'ASI high':>10}{'ASI low':>10}{'ratio':>10}")
    lines.append("-" * 74)
    for a, b, _ in PAIRS:
        r = asymmetry(profiles[a], profiles[b])
        ratio = "UNBOUNDED" if r["inert_side"] else f"{r['ratio']}x"
        lines.append(f"{a + '  x  ' + b:<44}{r['asi_high']:>10,}{r['asi_low']:>10,}{ratio:>10}")

    out = "\n".join(lines)
    print(out)

    inert = [lbl for lbl, p in profiles.items() if p["refutation_inert"]]
    print(f"\nRefutation-inert standards ({len(inert)}): {', '.join(inert) if inert else 'none'}")
    print("No set of class-level correspondences can make any class in those ontologies")
    print("unsatisfiable. A clean reasoner report against them is not evidence.")

    if args.write:
        with open(os.path.join(HERE, "asi.json"), "w") as fh:
            json.dump({"profiles": profiles, "provenance": provenance}, fh, indent=2, sort_keys=True)
            fh.write("\n")
        with open(os.path.join(HERE, "asi-table.txt"), "w") as fh:
            fh.write(out + "\n")
        print("\nWrote metrics/asi.json and metrics/asi-table.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
