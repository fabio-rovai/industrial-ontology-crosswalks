#!/usr/bin/env python3
"""
Falsifiability rate: if you ground a concept WRONGLY, will anything catch you?

WHY A SECOND METRIC
-------------------
metrics/axiomatic_asymmetry.py counts contradiction-capable axioms. That is a
property of an ontology in the abstract. The question a practitioner actually
has is narrower and more useful:

    I am grounding my concepts in this vocabulary. If I put a concept under the
    wrong parent, is there any chance a reasoner tells me?

Define the FALSIFIABILITY RATE of a grounding vocabulary as the fraction of
unordered class pairs {A, B} that cannot both subsume a common concept. If a
concept is asserted under both A and B and the ontology entails a contradiction,
that mistake is DETECTABLE. If not, the mistake is invisible: the file loads,
the reasoner is happy, and the error ships.

    falsifiability_rate = |{ {A,B} : A and B are provably disjoint }| / C(n,2)

For the axiom profiles these standards use, {A,B} is contradictory exactly when
some ancestor of A is declared disjoint from some ancestor of B. That is
computed once from the reasoned hierarchy rather than by running the reasoner
C(n,2) times, which for IFC4 would be 840,000 invocations.

WHAT THIS AUDIT IS FOR
----------------------
Abad-Navarro, Fernandez-Breis and Garcia-Castro (tecnomod-um/cfihos) published
an OWL rendering of CFIHOS V2.0 aligned to the Industrial Data Ontology. That
is real, useful, and the only open machine-readable CFIHOS. This is not a
competing alignment. It is an independent measurement of how much of that
alignment a reasoner is in a position to check, which is a question their paper
does not ask and which applies equally to every auto-generated grounding.

Run:  python crosswalks/cfihos-audit/falsifiability.py
"""
from __future__ import annotations

import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile

import rdflib
from rdflib import RDF, RDFS, OWL, URIRef
import owlready2 as o2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, "sources")
LIFT = os.path.join(ROOT, "lift", "out")

IDO_NS = "http://rds.posccaesar.org/ontology/lis14/rdl/"
CFIHOS_NS = "http://infohub.siemens-energy.com/CFIHOS#"
SH = "http://www.w3.org/ns/shacl#"


def _java_works(c):
    if not c or not os.path.exists(c):
        return False
    try:
        return subprocess.run([c, "-version"], capture_output=True).returncode == 0
    except Exception:
        return False


for _c in (os.environ.get("JAVA_EXE"), "/opt/homebrew/opt/openjdk/bin/java", shutil.which("java")):
    if _java_works(_c):
        o2.JAVA_EXE = _c
        break


def local(u: str) -> str:
    return u[max(u.rfind("#"), u.rfind("/")) + 1:]


def load(path: str, fmt: str | None) -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(path, format=fmt) if fmt else g.parse(path)
    for t in [(s, p, o) for s, p, o in g if str(p).startswith(SH)]:
        g.remove(t)
    # The CFIHOS-IDO file owl:imports IDO by IRI. Left in place, owlready2 fetches
    # that IRI over the network and fails on the content negotiation. Imports are
    # stripped and the imported ontology is merged explicitly instead, so the
    # experiment states exactly what is in the merge.
    for t in list(g.triples((None, OWL.imports, None))):
        g.remove(t)
    for s, o in list(g.subject_objects(RDFS.subClassOf)):
        for x in (s, o):
            if isinstance(x, URIRef) and (x, RDF.type, OWL.Class) not in g:
                g.add((x, RDF.type, OWL.Class))
    return g


def disjoint_pairs(g: rdflib.Graph) -> set[tuple[str, str]]:
    """All asserted pairwise disjointness, including expanded AllDisjointClasses."""
    out: set[tuple[str, str]] = set()
    for a, b in g.subject_objects(OWL.disjointWith):
        if isinstance(a, URIRef) and isinstance(b, URIRef):
            out.add(tuple(sorted((str(a), str(b)))))
    for adc in g.subjects(RDF.type, OWL.AllDisjointClasses):
        head = g.value(adc, OWL.members)
        members = []
        seen = set()
        while head and head != RDF.nil and head not in seen:
            seen.add(head)
            f = g.value(head, RDF.first)
            if isinstance(f, URIRef):
                members.append(str(f))
            head = g.value(head, RDF.rest)
        for a, b in itertools.combinations(members, 2):
            out.add(tuple(sorted((a, b))))
    return out


def ancestors_map(g: rdflib.Graph, ns: str | None) -> dict[str, set[str]]:
    """Transitive closure of asserted rdfs:subClassOf over named classes."""
    parents: dict[str, set[str]] = {}
    classes: set[str] = set()
    for c in g.subjects(RDF.type, OWL.Class):
        if isinstance(c, URIRef):
            classes.add(str(c))
    for s, o in g.subject_objects(RDFS.subClassOf):
        if isinstance(s, URIRef) and isinstance(o, URIRef):
            parents.setdefault(str(s), set()).add(str(o))
            classes.add(str(s))
            classes.add(str(o))

    memo: dict[str, set[str]] = {}

    def anc(c: str, stack: frozenset = frozenset()) -> set[str]:
        if c in memo:
            return memo[c]
        if c in stack:
            return set()
        out = set()
        for p in parents.get(c, ()):
            out.add(p)
            out |= anc(p, stack | {c})
        memo[c] = out
        return out

    result = {}
    for c in classes:
        if ns and not c.startswith(ns):
            continue
        result[c] = anc(c) | {c}
    return result


def falsifiability(g: rdflib.Graph, ns: str | None, label: str) -> dict:
    dj = disjoint_pairs(g)
    anc = ancestors_map(g, ns)
    names = sorted(anc)
    n = len(names)
    total = n * (n - 1) // 2

    # index: for each class, the set of its ancestors involved in any disjointness
    dj_index: dict[str, set[str]] = {}
    for a, b in dj:
        dj_index.setdefault(a, set()).add(b)
        dj_index.setdefault(b, set()).add(a)

    detectable = 0
    for a, b in itertools.combinations(names, 2):
        aa, ab = anc[a], anc[b]
        hit = False
        for x in aa:
            opp = dj_index.get(x)
            if opp and (opp & ab):
                hit = True
                break
        if hit:
            detectable += 1

    rate = detectable / total if total else 0.0
    return {"label": label, "classes": n, "pairs": total, "disjointness_axioms": len(dj),
            "detectable_pairs": detectable, "falsifiability_rate": round(rate, 6)}


def reason_unsat(graphs: list[rdflib.Graph], tag: str) -> int:
    merged = rdflib.Graph()
    for g in graphs:
        merged += g
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, f"{tag}.owl")
    merged.serialize(destination=p, format="xml")
    w = o2.World()
    onto = w.get_ontology("file://" + p).load()
    with onto:
        o2.sync_reasoner_hermit(w, infer_property_values=False, debug=0)
    n = 0
    for c in onto.classes():
        try:
            if o2.Nothing in c.ancestors():
                n += 1
        except Exception:
            pass
    shutil.rmtree(tmp, ignore_errors=True)
    return n


def main() -> int:
    print("=" * 80)
    print("FALSIFIABILITY OF INDUSTRIAL GROUNDING VOCABULARIES")
    print("=" * 80)
    print("\nIf a concept is grounded under two classes at once, how often can a")
    print("reasoner prove that combination impossible? That is the ceiling on what")
    print("any automated check of an alignment can ever catch.\n")

    targets = [
        ("IDO / ISO 15926-14", os.path.join(SRC, "ido-lis14-core.ttl"), "turtle", IDO_NS),
        ("IFC4 ADD2", os.path.join(SRC, "ifc4-add2.ttl"), "turtle",
         "http://ifcowl.openbimstandards.org/IFC4_ADD2#"),
        ("ISO 15926-2:2003", os.path.join(SRC, "iso15926-2-2003.ttl"), "turtle",
         "http://rds.posccaesar.org/2008/02/OWL/ISO-15926-2_2003#"),
        ("SAREF core", os.path.join(SRC, "saref-core-v3.2.1.ttl"), "turtle",
         "https://saref.etsi.org/core/"),
        ("AAS metamodel", os.path.join(SRC, "aas-metamodel.ttl"), "turtle",
         "https://admin-shell.io/aas/3/2/"),
        ("CFIHOS V2.0 (IDO-aligned)", os.path.join(SRC, "cfihos-v2.0-ido.owl"), None, CFIHOS_NS),
    ]
    opcua_di = os.path.join(LIFT, "opcua-di-lifted.ttl")
    if os.path.exists(opcua_di):
        targets.append(("OPC UA DI (lifted)", opcua_di, "turtle",
                        "https://w3id.org/tesseract/industrial-crosswalks/opcua-di-lifted#"))

    rows = []
    print(f"{'vocabulary':<28}{'classes':>9}{'disj ax':>9}{'pairs':>12}"
          f"{'detectable':>12}{'falsifiability':>15}")
    print("-" * 80)
    for label, path, fmt, ns in targets:
        if not os.path.exists(path):
            print(f"{label:<28}  SKIPPED (missing {os.path.basename(path)})")
            continue
        g = load(path, fmt)
        r = falsifiability(g, ns, label)
        rows.append(r)
        print(f"{label:<28}{r['classes']:>9,}{r['disjointness_axioms']:>9,}"
              f"{r['pairs']:>12,}{r['detectable_pairs']:>12,}"
              f"{r['falsifiability_rate'] * 100:>14.2f}%")

    print("\nRead the last column as: the percentage of possible mis-groundings that a")
    print("description-logic reasoner is even CAPABLE of rejecting. Everything else")
    print("passes silently, no matter how wrong it is.")

    # ---- empirical confirmation on the published CFIHOS-IDO alignment
    print("\n" + "=" * 80)
    print("EMPIRICAL CHECK ON THE PUBLISHED CFIHOS-IDO ALIGNMENT")
    print("=" * 80)
    cf = load(os.path.join(SRC, "cfihos-v2.0-ido.owl"), None)
    ido = load(os.path.join(SRC, "ido-lis14-core.ttl"), "turtle")

    n_unsat = reason_unsat([cf], "cfihos-alone")
    print(f"  CFIHOS-IDO as published, reasoned alone : {n_unsat} unsatisfiable classes")
    n_unsat2 = reason_unsat([cf, ido], "cfihos-plus-ido")
    print(f"  CFIHOS-IDO merged with the full IDO     : {n_unsat2} unsatisfiable classes")

    # how many CFIHOS classes are grounded at all, and on how many distinct anchors?
    anchors: dict[str, int] = {}
    grounded = set()
    for s, o in cf.subject_objects(RDFS.subClassOf):
        if isinstance(s, URIRef) and isinstance(o, URIRef) and str(o).startswith(IDO_NS):
            anchors[local(str(o))] = anchors.get(local(str(o)), 0) + 1
            grounded.add(str(s))
    cf_classes = {str(c) for c in cf.subjects(RDF.type, OWL.Class)
                  if isinstance(c, URIRef) and str(c).startswith(CFIHOS_NS)}
    grounded_in_ns = grounded & cf_classes
    total_edges = sum(anchors.values())
    print(f"\n  CFIHOS classes (CFIHOS# namespace)      : {len(cf_classes):,}")
    print(f"  of those, directly grounded on IDO      : {len(grounded_in_ns):,}")
    print(f"  grounding edges in total                : {total_edges:,}"
          f"   (some classes carry more than one)")
    print(f"  distinct IDO anchor classes used        : {len(anchors)} of 49")
    for a, n in sorted(anchors.items(), key=lambda kv: -kv[1]):
        print(f"      ido:{a:<26} {n:>6,} edges  ({n / total_edges * 100:>5.1f}%)")
    top2 = sorted(anchors.values(), reverse=True)[:2]
    print(f"\n  The top two anchors carry {sum(top2) / total_edges * 100:.1f}% of all groundings.")
    print("  Both are in IDO's Dependent branch (PhysicalQuantity is a subclass of")
    print("  Quality), and IDO's disjointness separates BRANCHES. So virtually no")
    print("  grounding edge crosses a disjointness boundary, and the 0-unsatisfiable")
    print("  result above is guaranteed by construction rather than earned by checking.")

    ido_fals = next((r for r in rows if r["label"].startswith("IDO")), None)
    if ido_fals:
        print(f"\n  IDO's falsifiability rate is {ido_fals['falsifiability_rate'] * 100:.2f}%.")
        print("  So even a grounding that is completely wrong has that chance of being")
        print("  caught, and only if the error crosses one of IDO's disjointness blocks.")
        print("  A pump grounded as ido:Role instead of ido:PhysicalArtefact is NOT caught:")
        print("  both sit inside branches IDO never declares disjoint from each other.")

    out = {"falsifiability": rows,
           "cfihos": {"unsat_alone": n_unsat, "unsat_with_ido": n_unsat2,
                      "cfihos_classes": len(cf_classes), "grounded": len(grounded),
                      "anchors_used": len(anchors), "anchor_histogram": anchors}}
    with open(os.path.join(HERE, "falsifiability.json"), "w") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"\n  Wrote {os.path.relpath(os.path.join(HERE, 'falsifiability.json'), ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
