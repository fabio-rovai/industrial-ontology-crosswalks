#!/usr/bin/env python3
"""
Verify that every IRI named in every crosswalk actually exists in the source it
claims to come from.

A crosswalk full of plausible but non-existent IRIs is the easiest thing in this
field to produce and the hardest to notice, because SHACL will happily validate
the shape of a mapping to a class that was never defined. This check closes that
gap: it resolves every subject_id and object_id against the fetched sources and
the lifted ontologies, and fails loudly on anything it cannot find.

Run:  python scripts/verify_iris.py
"""
from __future__ import annotations

import csv
import glob
import os
import sys

from rdflib import Graph, RDF, RDFS, OWL, URIRef

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "sources")
LIFT = os.path.join(ROOT, "lift", "out")

# namespace prefix -> (file, format). Every IRI must fall under one of these.
NAMESPACES = [
    ("http://rds.posccaesar.org/ontology/lis14/rdl/", os.path.join(SRC, "ido-lis14-core.ttl"), "turtle"),
    ("http://ifcowl.openbimstandards.org/IFC4_ADD2#", os.path.join(SRC, "ifc4-add2.ttl"), "turtle"),
    ("http://infohub.siemens-energy.com/CFIHOS#", os.path.join(SRC, "cfihos-v2.0-ido.owl"), None),
    ("https://admin-shell.io/aas/3/2/", os.path.join(SRC, "aas-metamodel.ttl"), "turtle"),
    ("https://saref.etsi.org/core/", os.path.join(SRC, "saref-core-v3.2.1.ttl"), "turtle"),
    ("https://saref.etsi.org/saref4inma/", os.path.join(SRC, "saref4inma-v1.1.2.ttl"), "turtle"),
    ("https://w3id.org/tesseract/industrial-crosswalks/isa95-lifted#",
     os.path.join(LIFT, "isa95-b2mml-lifted.ttl"), "turtle"),
    ("https://w3id.org/tesseract/industrial-crosswalks/opcua-di-lifted#",
     os.path.join(LIFT, "opcua-di-lifted.ttl"), "turtle"),
    ("https://w3id.org/tesseract/industrial-crosswalks/opcua-machinery-lifted#",
     os.path.join(LIFT, "opcua-machinery-lifted.ttl"), "turtle"),
]

_cache: dict[str, set[str]] = {}


def terms(path: str, fmt: str | None) -> set[str]:
    """Every named class or property declared or used in a subClassOf position."""
    if path in _cache:
        return _cache[path]
    if not os.path.exists(path):
        _cache[path] = set()
        return _cache[path]
    g = Graph()
    g.parse(path, format=fmt) if fmt else g.parse(path)
    out: set[str] = set()
    for t in (OWL.Class, RDFS.Class, OWL.ObjectProperty, OWL.DatatypeProperty):
        for s in g.subjects(RDF.type, t):
            if isinstance(s, URIRef):
                out.add(str(s))
    for s, o in g.subject_objects(RDFS.subClassOf):
        for x in (s, o):
            if isinstance(x, URIRef):
                out.add(str(x))
    _cache[path] = out
    return out


def resolve(iri: str) -> tuple[bool, str]:
    for prefix, path, fmt in NAMESPACES:
        if iri.startswith(prefix):
            if not os.path.exists(path):
                return False, f"source missing: {os.path.basename(path)} (run fetch/lift first)"
            return (iri in terms(path, fmt)), os.path.basename(path)
    return False, "no source registered for this namespace"


def read_rows(path: str):
    with open(path) as fh:
        lines, cmap = [], {}
        in_curie = False
        for line in fh:
            if line.startswith("#"):
                s = line[1:].rstrip("\n")
                if s.strip() == "curie_map:":
                    in_curie = True
                    continue
                if in_curie and s.startswith("  ") and ":" in s:
                    k, v = s.strip().split(":", 1)
                    cmap[k.strip()] = v.strip().strip('"')
                    continue
                in_curie = False
            else:
                lines.append(line)
    return cmap, list(csv.DictReader(lines, delimiter="\t"))


def expand(cmap: dict, curie: str) -> str:
    if curie.startswith("http"):
        return curie
    pfx, local = curie.split(":", 1)
    return cmap.get(pfx, "urn:unknown:") + local


def main() -> int:
    files = sorted(glob.glob(os.path.join(ROOT, "crosswalks", "*", "*.sssom.tsv")))
    if not files:
        sys.exit("No SSSOM files found.")
    total = bad = 0
    print(f"{'crosswalk':<26}{'IRIs':>7}{'resolved':>10}{'missing':>9}")
    print("-" * 52)
    failures: list[str] = []
    for path in files:
        name = os.path.basename(path).replace(".sssom.tsv", "")
        cmap, rows = read_rows(path)
        seen: set[str] = set()
        for r in rows:
            for col in ("subject_id", "object_id"):
                v = (r.get(col) or "").strip()
                if v and not v.startswith("skos:") and not v.startswith("semapv:"):
                    seen.add(expand(cmap, v))
        miss = []
        for iri in sorted(seen):
            ok, where = resolve(iri)
            if not ok:
                miss.append(f"    {name}: {iri}  [{where}]")
        total += len(seen)
        bad += len(miss)
        failures.extend(miss)
        print(f"{name:<26}{len(seen):>7}{len(seen) - len(miss):>10}{len(miss):>9}")
    if failures:
        print("\nUNRESOLVED IRIs:")
        print("\n".join(failures))
        print(f"\nFAIL: {bad} of {total} IRIs do not exist in their declared source.")
        return 1
    print(f"\nPASS: all {total} distinct IRIs across {len(files)} crosswalks resolve "
          "against the fetched sources.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
