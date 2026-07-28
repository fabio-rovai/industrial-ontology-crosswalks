#!/usr/bin/env python3
"""
Convert every SSSOM crosswalk in this repository to RDF and validate it with SHACL.

Emits, per crosswalk:
  1. Direct SKOS mapping triples, so the file is usable by ordinary tooling.
  2. A reified sssom:Mapping node per correspondence, carrying the predicate,
     confidence, justification, provenance and comment. The reification is what
     makes a crosswalk auditable: a bare skos:closeMatch triple cannot record
     who said it, how sure they were, or why.

Asserted NON-mappings (predicate_modifier = Not) are emitted ONLY as reified
nodes and never as direct SKOS triples, because asserting
`ido:System skos:exactMatch ifc:IfcSystem` in order to deny it would be read as
the mapping by every tool that does not understand the modifier.

Run:  python scripts/sssom_to_rdf.py
"""
from __future__ import annotations

import csv
import glob
import os
import sys
from decimal import Decimal

from rdflib import Graph, Namespace, Literal, URIRef, BNode, RDF, RDFS, XSD

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CW = os.path.join(ROOT, "crosswalks")
SHAPES = os.path.join(ROOT, "shapes", "crosswalk-shapes.ttl")

SSSOM = Namespace("https://w3id.org/sssom/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")
CWNS = Namespace("https://w3id.org/tesseract/industrial-crosswalks/")


def read_sssom(path: str) -> tuple[dict, list[dict]]:
    """Parse the commented YAML-ish header and the TSV body."""
    meta: dict = {}
    curie: dict[str, str] = {}
    body: list[str] = []
    in_curie = False
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                stripped = line[1:].rstrip("\n")
                if stripped.strip() == "curie_map:":
                    in_curie = True
                    continue
                if in_curie and stripped.startswith("  ") and ":" in stripped:
                    k, v = stripped.strip().split(":", 1)
                    curie[k.strip()] = v.strip().strip('"')
                    continue
                in_curie = False
                if ":" in stripped:
                    k, v = stripped.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"')
            else:
                body.append(line)
    rows = list(csv.DictReader(body, delimiter="\t"))
    meta["_curie_map"] = curie
    return meta, rows


def expand(curie_map: dict[str, str], value: str) -> URIRef:
    if value.startswith("http://") or value.startswith("https://"):
        return URIRef(value)
    pfx, local = value.split(":", 1)
    if pfx not in curie_map:
        raise KeyError(f"prefix '{pfx}' missing from curie_map (value: {value})")
    return URIRef(curie_map[pfx] + local)


def convert(path: str) -> tuple[Graph, dict]:
    meta, rows = read_sssom(path)
    cmap = meta["_curie_map"]
    g = Graph()
    g.bind("skos", SKOS)
    g.bind("sssom", SSSOM)
    g.bind("prov", PROV)
    for pfx, ns in cmap.items():
        g.bind(pfx, Namespace(ns))

    set_id = URIRef(meta.get("mapping_set_id", "urn:mapping-set"))
    creator = expand(cmap, meta.get("creator_id", "orcid:0000-0000-0000-0000"))
    g.add((set_id, RDF.type, SSSOM.MappingSet))
    g.add((set_id, SSSOM.mapping_set_id, set_id))
    g.add((set_id, SSSOM.mapping_set_version, Literal(meta.get("mapping_set_version", "0.1.0"))))
    g.add((set_id, SSSOM.license, URIRef(meta.get("license", "https://creativecommons.org/licenses/by/4.0/"))))
    g.add((set_id, RDFS.label, Literal(meta.get("mapping_set_title", os.path.basename(path)))))
    if meta.get("comment"):
        g.add((set_id, RDFS.comment, Literal(meta["comment"])))

    stats = {"positive": 0, "negative": 0}
    for i, r in enumerate(rows):
        if not r.get("subject_id") or not r.get("object_id"):
            continue
        subj = expand(cmap, r["subject_id"])
        obj = expand(cmap, r["object_id"])
        pred = expand(cmap, r["predicate_id"])
        modifier = (r.get("predicate_modifier") or "").strip()
        negative = modifier.lower() == "not"

        node = URIRef(f"{set_id}/mapping/{i:03d}")
        g.add((node, RDF.type, SSSOM.Mapping))
        g.add((node, SSSOM.subject_id, subj))
        g.add((node, SSSOM.object_id, obj))
        g.add((node, SSSOM.predicate_id, pred))
        g.add((node, SSSOM.mapping_justification,
               expand(cmap, r.get("mapping_justification", "semapv:ManualMappingCuration"))))
        g.add((node, SSSOM.confidence,
               Literal(Decimal(r.get("confidence") or "0.5"), datatype=XSD.decimal)))
        g.add((node, PROV.wasAttributedTo, creator))
        g.add((node, RDFS.comment, Literal(r.get("comment", ""))))
        g.add((node, SSSOM.mapping_set_id, set_id))
        if r.get("subject_label"):
            g.add((node, SSSOM.subject_label, Literal(r["subject_label"])))
        if r.get("object_label"):
            g.add((node, SSSOM.object_label, Literal(r["object_label"])))

        if negative:
            g.add((node, SSSOM.predicate_modifier, Literal("Not")))
            stats["negative"] += 1
            # deliberately NO direct SKOS triple: see module docstring
        else:
            g.add((subj, pred, obj))
            stats["positive"] += 1

    return g, stats


def main() -> int:
    try:
        from pyshacl import validate as shacl_validate
    except ImportError:
        sys.exit("pyshacl not installed. pip install -r requirements.txt")

    shapes = Graph()
    shapes.parse(SHAPES, format="turtle")

    files = sorted(glob.glob(os.path.join(CW, "*", "*.sssom.tsv")))
    if not files:
        sys.exit("No SSSOM files found under crosswalks/.")

    all_ok = True
    print(f"{'crosswalk':<28}{'positive':>10}{'asserted-not':>14}{'SHACL':>10}")
    print("-" * 62)
    for path in files:
        name = os.path.basename(os.path.dirname(path))
        g, stats = convert(path)
        out = path.replace(".sssom.tsv", ".ttl")
        g.serialize(destination=out, format="turtle")

        conforms, _, text = shacl_validate(
            g, shacl_graph=shapes, inference="none", abort_on_first=False,
            allow_infos=True, allow_warnings=True, advanced=True,
        )
        all_ok &= conforms
        print(f"{name:<28}{stats['positive']:>10}{stats['negative']:>14}"
              f"{'PASS' if conforms else 'FAIL':>10}")
        if not conforms:
            for line in text.splitlines():
                if line.strip().startswith(("Message:", "Focus Node:", "Value Node:")):
                    print(f"      {line.strip()}")

    print("\nWrote a .ttl beside each .sssom.tsv (SKOS triples + reified sssom:Mapping nodes).")
    print("Asserted non-mappings are emitted ONLY as reified nodes, never as SKOS triples,")
    print("so no tool can mistake a denial for an assertion.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
