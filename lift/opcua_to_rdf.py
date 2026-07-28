#!/usr/bin/env python3
"""
Lift the OPC UA core NodeSet2 type layer into OWL.

WHY A LIFT IS NEEDED, AND WHAT IT COSTS
---------------------------------------
OPC UA does not ship an ontology. It ships an address-space model in a bespoke
XML schema (UANodeSet). Any crosswalk claiming to align "OPC UA" to an OWL
ontology has silently done a transformation first, and the honesty of the
crosswalk depends entirely on the honesty of that transformation. So this lift
is a first-class, inspectable artefact rather than a hidden preprocessing step.

WHAT IS LIFTED
    UAObjectType     -> owl:Class
    UAVariableType   -> owl:Class            (typed values are still types)
    UADataType       -> owl:Class            (marked with ua:isDataType)
    UAReferenceType  -> owl:ObjectProperty
    HasSubtype       -> rdfs:subClassOf / rdfs:subPropertyOf
    Symmetric="true" -> owl:SymmetricProperty
    InverseName      -> a paired owl:ObjectProperty with owl:inverseOf

WHAT IS DELIBERATELY NOT LIFTED, AND WHY
    UAObject / UAVariable / UAMethod instances. These are the address-space
    INSTANCE layer (912 + 3369 + 462 nodes in the core NodeSet). Lifting them
    into a TBox would inflate the class count and misrepresent instances as
    types, which is exactly the error this repository is about.

    Modelling rules that are prose in Part 3 (for example that a HasComponent
    target must be an Object, Variable or Method). These are not expressible
    from the NodeSet alone without hand-encoding, and hand-encoding them here
    would put axioms into "OPC UA" that OPC UA never asserted.

THE HONEST CONSEQUENCE
    The lifted ontology carries almost no contradiction-capable axiom, because
    the source carries almost none. Run metrics/axiomatic_asymmetry.py against
    the output and it scores near zero. That is a true measurement of OPC UA's
    address-space model, not a defect of this lift. See metrics/RESULTS.md.

Run:  python lift/opcua_to_rdf.py
Out:  lift/out/opcua-core-lifted.ttl
"""
from __future__ import annotations

import os
import re
import sys
import xml.etree.ElementTree as ET

from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS, OWL, XSD

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(HERE, "out")

NS_XML = "{http://opcfoundation.org/UA/2011/03/UANodeSet.xsd}"

# Each NodeSet gets its own namespace so a merged graph keeps provenance.
# The core NodeSet is infrastructure (Server, Folder, namespace metadata); the
# DOMAIN semantics live in the companion specifications, which is why DI and
# Machinery are lifted separately and are the ones the SAREF crosswalk targets.
NODESETS = {
    "core": ("opcua-nodeset2.xml", "opcua-core-lifted.ttl",
             "OPC UA core: infrastructure and base types."),
    "di": ("opcua-di-nodeset2.xml", "opcua-di-lifted.ttl",
           "OPC UA Device Information companion spec: the device semantics."),
    "machinery": ("opcua-machinery-nodeset2.xml", "opcua-machinery-lifted.ttl",
                  "OPC UA Machinery companion spec."),
    "isa95": ("opcua-isa95-nodeset2.xml", "opcua-isa95-lifted.ttl",
              "OPC UA ISA-95 companion spec: the OPC Foundation's own ISA-95 rendering."),
    "i4aas": ("opcua-i4aas-nodeset2.xml", "opcua-i4aas-lifted.ttl",
              "OPC UA I4AAS companion spec: the OPC Foundation's own AAS mapping."),
}


def ns_for(key: str) -> Namespace:
    return Namespace(f"https://w3id.org/tesseract/industrial-crosswalks/opcua-{key}-lifted#")

TYPE_TAGS = {
    "UAObjectType": "class",
    "UAVariableType": "class",
    "UADataType": "datatype_class",
    "UAReferenceType": "property",
}


def clean(bn: str) -> str:
    """BrowseName is 'ns:Name' or 'Name'; make a safe local name."""
    name = bn.split(":", 1)[-1]
    name = re.sub(r"[^0-9A-Za-z_]", "_", name)
    if name and name[0].isdigit():
        name = "_" + name
    return name


def lift_one(key: str) -> dict:
    fname, outname, blurb = NODESETS[key]
    SRC = os.path.join(ROOT, "sources", fname)
    OUT = os.path.join(OUT_DIR, outname)
    UA = ns_for(key)
    if not os.path.exists(SRC):
        sys.exit(f"Missing {SRC}. Run: python scripts/fetch_sources.py --relock")
    os.makedirs(OUT_DIR, exist_ok=True)

    tree = ET.parse(SRC)
    root = tree.getroot()

    # pass 1: NodeId -> (kind, local name, element)
    nodes: dict[str, tuple[str, str, ET.Element]] = {}
    for tag, kind in TYPE_TAGS.items():
        for el in root.findall(NS_XML + tag):
            nid = el.get("NodeId")
            bn = el.get("BrowseName")
            if not nid or not bn:
                continue
            nodes[nid] = (kind, clean(bn), el)

    g = Graph()
    g.bind("ua", UA)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)

    onto = URIRef(str(UA).rstrip("#"))
    g.add((onto, RDF.type, OWL.Ontology))
    g.add((onto, RDFS.comment, Literal(
        f"OWL lift of the {blurb} TYPE layer, produced by lift/opcua_to_rdf.py in the "
        "industrial-ontology-crosswalks repository. Not an OPC Foundation artefact. "
        "The instance layer is deliberately excluded; see the script docstring.")))

    counts = {"class": 0, "datatype_class": 0, "property": 0,
              "subclass": 0, "subproperty": 0, "inverse": 0, "symmetric": 0, "abstract": 0}

    for nid, (kind, name, el) in nodes.items():
        iri = UA[name]
        if kind in ("class", "datatype_class"):
            g.add((iri, RDF.type, OWL.Class))
            counts["class" if kind == "class" else "datatype_class"] += 1
            if kind == "datatype_class":
                g.add((iri, UA["isDataType"], Literal(True)))
        else:
            g.add((iri, RDF.type, OWL.ObjectProperty))
            counts["property"] += 1
            if el.get("Symmetric") == "true":
                g.add((iri, RDF.type, OWL.SymmetricProperty))
                counts["symmetric"] += 1
            inv = el.find(NS_XML + "InverseName")
            if inv is not None and inv.text:
                inv_iri = UA[clean(inv.text)]
                g.add((inv_iri, RDF.type, OWL.ObjectProperty))
                g.add((iri, OWL.inverseOf, inv_iri))
                counts["inverse"] += 1

        g.add((iri, RDFS.label, Literal(name)))
        if el.get("IsAbstract") == "true":
            g.add((iri, UA["isAbstract"], Literal(True)))
            counts["abstract"] += 1
        dn = el.find(NS_XML + "DisplayName")
        if dn is not None and dn.text and dn.text != name:
            g.add((iri, RDFS.label, Literal(dn.text)))
        doc = el.find(NS_XML + "Documentation")
        if doc is not None and doc.text:
            g.add((iri, RDFS.seeAlso, URIRef(doc.text.strip())))
        g.add((iri, UA["nodeId"], Literal(nid)))

        # HasSubtype with IsForward=false points at the PARENT
        refs = el.find(NS_XML + "References")
        if refs is None:
            continue
        for r in refs.findall(NS_XML + "Reference"):
            if r.get("ReferenceType") != "HasSubtype":
                continue
            target = (r.text or "").strip()
            if target not in nodes:
                continue
            _, pname, _ = nodes[target]
            parent = UA[pname]
            if r.get("IsForward") == "false":
                if kind == "property":
                    g.add((iri, RDFS.subPropertyOf, parent))
                    counts["subproperty"] += 1
                else:
                    g.add((iri, RDFS.subClassOf, parent))
                    counts["subclass"] += 1
            else:
                if kind == "property":
                    g.add((parent, RDFS.subPropertyOf, iri))
                    counts["subproperty"] += 1
                else:
                    g.add((parent, RDFS.subClassOf, iri))
                    counts["subclass"] += 1

    g.serialize(destination=OUT, format="turtle")
    counts["triples"] = len(g)
    counts["out"] = os.path.relpath(OUT, ROOT)
    return counts


def main() -> int:
    which = sys.argv[1:] or list(NODESETS)
    print("OPC UA NodeSet2 -> OWL lift (TYPE layer only)\n")
    hdr = (f"{'nodeset':<12}{'classes':>9}{'datatypes':>11}{'refprops':>10}"
           f"{'subClassOf':>12}{'inverse':>9}{'triples':>10}")
    print(hdr)
    print("-" * len(hdr))
    for key in which:
        if key not in NODESETS:
            sys.exit(f"Unknown nodeset '{key}'. Choose from: {', '.join(NODESETS)}")
        c = lift_one(key)
        print(f"{key:<12}{c['class']:>9,}{c['datatype_class']:>11,}{c['property']:>10,}"
              f"{c['subclass']:>12,}{c['inverse']:>9,}{c['triples']:>10,}")
    print("\n  Instance nodes (UAObject/UAVariable/UAMethod) are NOT lifted.")
    print("  The results carry almost no disjointness, because OPC UA asserts almost none.")
    print("  Core is infrastructure; DOMAIN semantics live in DI and Machinery.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
