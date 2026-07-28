#!/usr/bin/env python3
"""
Lift the B2MML XML Schema set (the XML rendering of ISA-95 / IEC 62264) into OWL.

WHY A LIFT IS NEEDED, AND WHAT IT COSTS
---------------------------------------
ISA-95 (IEC 62264) has no normative ontology. Its machine-readable form is
B2MML, a set of W3C XML Schemas published by MESA International against
ANSI/ISA-95.00.02 and .00.05. Aligning "ISA-95" to anything in OWL therefore
requires a transformation, and every such published alignment has made one
whether or not it said so. This lift is explicit so the crosswalk built on it
can be argued with.

WHAT IS LIFTED
    xsd:complexType name=X          -> owl:Class
    xsd:extension base=Y            -> rdfs:subClassOf
    xsd:element inside a complexType-> owl:ObjectProperty with domain/range,
                                       when the element's type is a lifted class
                                    -> owl:DatatypeProperty with domain,
                                       when the element's type is an XSD builtin
    maxOccurs="1" (or absent)       -> owl:FunctionalProperty
    minOccurs>0 with maxOccurs=1    -> owl:cardinality 1 restriction

WHAT IS DELIBERATELY NOT LIFTED, AND WHY
    xsd:sequence ORDER. XML Schema fixes element order; OWL has no notion of it.
    Encoding order would invent axioms ISA-95 does not make.

    xsd:choice as owl:disjointWith. This is the tempting one and it is WRONG.
    A choice means "one of these elements appears in this document position",
    which is a serialisation constraint, not a claim that the underlying classes
    have no common instance. Lifting choice to disjointness would manufacture
    exactly the contradiction-capable axioms that metrics/ is measuring, and
    would make ISA-95 look far more axiomatically committed than it is.

THE HONEST CONSEQUENCE
    Because of the paragraph above, the lifted ISA-95 has an Axiomatic Strength
    Index near zero, driven only by cardinality. That is a real property of
    ISA-95-as-published, and it is why the ISA-95 to AAS crosswalk in
    crosswalks/isa95-aas/ cannot be reasoner-certified in any meaningful sense:
    both sides are refutation-inert. That negative result is the finding.

Run:  python lift/b2mml_to_rdf.py
Out:  lift/out/isa95-b2mml-lifted.ttl
"""
from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET

from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS, OWL, XSD

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC_DIR = os.path.join(ROOT, "sources", "b2mml")
OUT_DIR = os.path.join(HERE, "out")
OUT = os.path.join(OUT_DIR, "isa95-b2mml-lifted.ttl")

XS = "{http://www.w3.org/2001/XMLSchema}"
ISA = Namespace("https://w3id.org/tesseract/industrial-crosswalks/isa95-lifted#")

XSD_BUILTINS = {
    "string": XSD.string, "boolean": XSD.boolean, "decimal": XSD.decimal,
    "integer": XSD.integer, "int": XSD.int, "long": XSD.long, "float": XSD.float,
    "double": XSD.double, "dateTime": XSD.dateTime, "date": XSD.date,
    "time": XSD.time, "duration": XSD.duration, "anyURI": XSD.anyURI,
    "normalizedString": XSD.string, "token": XSD.string, "ID": XSD.string,
    "IDREF": XSD.string, "NMTOKEN": XSD.string, "base64Binary": XSD.base64Binary,
}


def strip_ns(t: str | None) -> str:
    if not t:
        return ""
    return t.split(":", 1)[-1]


def main() -> int:
    if not os.path.isdir(SRC_DIR):
        sys.exit(f"Missing {SRC_DIR}. Run: python scripts/fetch_sources.py --relock")
    os.makedirs(OUT_DIR, exist_ok=True)

    files = sorted(f for f in os.listdir(SRC_DIR) if f.endswith(".xsd"))
    g = Graph()
    g.bind("isa95", ISA)
    g.bind("owl", OWL)

    onto = URIRef(str(ISA).rstrip("#"))
    g.add((onto, RDF.type, OWL.Ontology))
    g.add((onto, RDFS.comment, Literal(
        "OWL lift of the B2MML XML Schemas (the XML rendering of ISA-95 / IEC 62264), "
        "produced by lift/b2mml_to_rdf.py in the industrial-ontology-crosswalks "
        "repository. Not a MESA International or ISA artefact. xsd:choice is "
        "deliberately NOT lifted to owl:disjointWith; see the script docstring.")))

    declared: set[str] = set()
    complex_types: list[tuple[str, ET.Element, str]] = []

    for fname in files:
        try:
            root = ET.parse(os.path.join(SRC_DIR, fname)).getroot()
        except ET.ParseError as e:
            print(f"  WARN could not parse {fname}: {e}")
            continue
        for ct in root.findall(XS + "complexType"):
            name = ct.get("name")
            if name:
                complex_types.append((name, ct, fname))
                declared.add(name)

    counts = {"classes": 0, "subclass": 0, "objprop": 0, "dataprop": 0,
              "functional": 0, "choice_skipped": 0, "sequence_skipped": 0}

    for name, ct, fname in complex_types:
        cls = ISA[name]
        g.add((cls, RDF.type, OWL.Class))
        g.add((cls, RDFS.label, Literal(name)))
        g.add((cls, RDFS.isDefinedBy, Literal(fname)))
        counts["classes"] += 1

        # extension base -> subClassOf
        for ext in ct.iter(XS + "extension"):
            base = strip_ns(ext.get("base"))
            if base and base in declared:
                g.add((cls, RDFS.subClassOf, ISA[base]))
                counts["subclass"] += 1

        # count what we are choosing not to lift, so the loss is reported
        counts["choice_skipped"] += len(list(ct.iter(XS + "choice")))
        counts["sequence_skipped"] += len(list(ct.iter(XS + "sequence")))

        for el in ct.iter(XS + "element"):
            ename = el.get("name")
            etype = strip_ns(el.get("type"))
            if not ename:
                continue
            prop = ISA[f"{ename[0].lower()}{ename[1:]}"]
            max_occurs = el.get("maxOccurs", "1")

            if etype in declared:
                g.add((prop, RDF.type, OWL.ObjectProperty))
                g.add((prop, RDFS.range, ISA[etype]))
                counts["objprop"] += 1
            elif etype in XSD_BUILTINS:
                g.add((prop, RDF.type, OWL.DatatypeProperty))
                g.add((prop, RDFS.range, XSD_BUILTINS[etype]))
                counts["dataprop"] += 1
            else:
                continue

            g.add((prop, RDFS.domain, cls))
            g.add((prop, RDFS.label, Literal(ename)))
            if max_occurs == "1":
                if (prop, RDF.type, OWL.FunctionalProperty) not in g:
                    g.add((prop, RDF.type, OWL.FunctionalProperty))
                    counts["functional"] += 1

    g.serialize(destination=OUT, format="turtle")

    print("B2MML (ISA-95 / IEC 62264) -> OWL lift")
    print(f"  schema files read                    {len(files):>6}")
    print(f"  xsd:complexType -> owl:Class         {counts['classes']:>6}")
    print(f"  xsd:extension   -> rdfs:subClassOf   {counts['subclass']:>6}")
    print(f"  elements        -> owl:ObjectProperty{counts['objprop']:>6}")
    print(f"                  -> owl:DatatypeProperty {counts['dataprop']:>3}")
    print(f"  maxOccurs=1     -> owl:FunctionalProperty {counts['functional']:>2}")
    print(f"  triples written: {len(g):,}")
    print(f"\n  DELIBERATELY NOT LIFTED:")
    print(f"    xsd:choice   occurrences skipped   {counts['choice_skipped']:>6}   "
          "(lifting these to owl:disjointWith would fabricate axioms)")
    print(f"    xsd:sequence order skipped         {counts['sequence_skipped']:>6}   "
          "(OWL has no element order)")
    print(f"\n  Wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
