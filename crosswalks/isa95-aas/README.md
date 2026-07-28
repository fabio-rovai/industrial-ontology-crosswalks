# ISA-95 ↔ AAS: which ISA-95, and which AAS?

**The crosswalk is [`isa95-aas.sssom.tsv`](isa95-aas.sssom.tsv): 7 correspondences and
11 asserted non-mappings or absences, with the argument in
[`DIVERGENCES.md`](DIVERGENCES.md).** The denials outnumber the mappings because the
two models meet at exactly one layer, the property and its IEC 61360 definition, and
ISA-95's material, personnel, location, process-segment and scheduling models have no
counterpart in the AAS metamodel at all.

This page is the measurement behind that shape: before aligning ISA-95 to anything,
it is worth asking which ISA-95.

"Crosswalk ISA-95 to the Asset Administration Shell" presupposes that there is one
ISA-95 and one AAS to align. There are at least two of each, published by different
bodies, and they do not agree.

| standard | rendering | publisher | classes | ASI | falsifiable? |
|---|---|---|---:|---:|---|
| ISA-95 / IEC 62264 | B2MML XML Schemas | MESA International | 385 | 56 | barely |
| ISA-95 / IEC 62264 | OPC UA ISA-95 companion NodeSet | OPC Foundation | 69 | 0 | **no** |
| AAS | metamodel RDF | IDTA | 64 | 0 | **no** |
| AAS | OPC UA I4AAS companion NodeSet | OPC Foundation | 47 | 0 | **no** |

Reproduce:

```bash
python scripts/fetch_sources.py --relock
python lift/b2mml_to_rdf.py && python lift/opcua_to_rdf.py
python crosswalks/isa95-aas/triangulate.py
```

## How far apart the two ISA-95s are

Comparing concept names after normalisation, and after removing the scaffolding
that belongs to neither standard's object model (B2MML's OAGIS transaction
wrappers, `Acknowledge*`/`Confirm*`/`Show*`; and the OPC UA rendering's `cdt*`
core datatypes):

| | B2MML | OPC UA ISA-95 |
|---|---:|---:|
| object-model concepts | 267 | 45 |
| shared | 16 | 16 |
| Jaccard agreement | **0.054** | |
| of its own concepts found in the other | 6.0% | **35.6%** |

Even reading it in the direction most favourable to agreement, only about a third
of the concepts in the OPC Foundation's ISA-95 rendering can be found by name in
MESA's. The shared core is small and predictable: equipment, material, personnel,
physical asset, and their property and class variants. That is ISA-95 Part 2's
object model and nothing else.

The AAS pair is closer but still not close: Jaccard **0.289**, with 56.4% of the
I4AAS concepts findable in the IDTA metamodel.

**Caveat, stated plainly.** These are name-level comparisons after normalisation.
Two concepts that mean the same thing under different names will not match, so
these numbers are a *lower bound* on semantic agreement. What they measure exactly
is whether a tool can join the two renderings by name, which is what integration
projects actually attempt.

## Why there is no reasoner experiment here (but there is still a crosswalk)

Three of the four renderings have an Axiomatic Strength Index of zero and a
falsifiability rate of zero. The fourth, B2MML, scores 56, entirely from
cardinality introduced by `maxOccurs="1"`, and has no disjointness at all.

So there is no reasoner experiment to run on this pair. Any alignment between any
of these four artefacts will be pronounced consistent and coherent regardless of
how wrong it is. That is not a limitation of this repository; it is the state of
the standards, and it is why the crosswalk here is validated by SHACL and by
argument rather than certified by a reasoner as the ISO 15926-14 to IFC4 pair is. See [`../cfihos-audit/`](../cfihos-audit/) for the falsifiability
argument in full.

## The lift, and one temptation resisted

Both sides required a transformation before any of this could be measured, and
those transformations are the real content of this directory:

- [`../../lift/b2mml_to_rdf.py`](../../lift/b2mml_to_rdf.py)
- [`../../lift/opcua_to_rdf.py`](../../lift/opcua_to_rdf.py)

The temptation worth naming: **`xsd:choice` looks like disjointness and is not.**
A choice says "one of these elements appears at this position in the document". It
does not say the underlying classes have no common instance. Lifting choice to
`owl:disjointWith` would have raised B2MML's Axiomatic Strength Index dramatically
and produced a satisfying reasoner experiment built on axioms ISA-95 never asserted.
The lift counts the choices it skips and reports them, so the decision is visible
rather than buried.

## What to do if you actually need this join

1. **Say which renderings you are aligning**, by version and publisher. A crosswalk
   against B2MML V0700 is not a crosswalk against the OPC UA ISA-95 companion spec.
2. **Do not rely on a reasoner to catch errors.** It cannot. Use SHACL over instance
   data, competency questions, or a human review protocol.
3. **Prefer IEC 61360 IRDIs as the join key** where both sides carry them. Semantic
   identifiers survive the rendering differences that class names do not, and they
   are the one currency shared across ISA-95, the AAS, OPC UA and SAREF4INMA.
4. **Treat the OPC Foundation's I4AAS NodeSet as prior art**, not as a competitor.
   It is the closest thing to an official ISA-95-adjacent AAS binding that exists.
