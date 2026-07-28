# How checkable are the industrial standards?

Every number here is produced by scripts in this repository against artefacts
fetched by IRI and pinned in [`../SOURCES.lock`](../SOURCES.lock). Reproduce with:

```bash
python scripts/fetch_sources.py --relock
python lift/b2mml_to_rdf.py && python lift/opcua_to_rdf.py
python metrics/axiomatic_asymmetry.py --write
python crosswalks/cfihos-audit/falsifiability.py        # needs a JDK
```

## 1. Axiomatic Strength Index

The ASI counts axioms capable of deriving a contradiction: disjointness, negation,
max and exact cardinality, functional and inverse-functional properties, property
disjointness and asymmetry, and individual identity. It deliberately excludes
`rdfs:subClassOf`, `rdfs:domain`, `rdfs:range`, `someValuesFrom` and
`minCardinality`, which add obligations but cannot on their own derive bottom.

| standard | classes | disjointness | max-card | func/inv | **ASI** | ASI/class | inert? |
|---|---:|---:|---:|---:|---:|---:|:--:|
| IFC4 ADD2 | 1,299 | 2,443 | 1,468 | 1,450 | **5,361** | 4.127 | |
| ISO 15926-2:2003 | 201 | 781 | 137 | 0 | **918** | 4.567 | |
| IDO / ISO 15926-14 | 49 | 15 | 0 | 3 | **18** | 0.367 | |
| SAREF core | 98 | 0 | 12 | 6 | **18** | 0.184 | |
| SAREF4INMA | 34 | 4 | 6 | 0 | **10** | 0.294 | |
| CFIHOS V2.0 (IDO-aligned) | 1,896 | 0 | 0 | 0 | **0** | 0.0 | **INERT** |
| AAS metamodel (IDTA) | 64 | 0 | 0 | 0 | **0** | 0.0 | **INERT** |
| ISA-95 via B2MML (lifted) | 385 | 0 | 0 | 56 | **56** | 0.145 | |
| OPC UA ISA-95 companion (lifted) | 69 | 0 | 0 | 0 | **0** | 0.0 | **INERT** |
| OPC UA I4AAS companion (lifted) | 47 | 0 | 0 | 0 | **0** | 0.0 | **INERT** |
| OPC UA DI (lifted) | 53 | 0 | 0 | 0 | **0** | 0.0 | **INERT** |

**A counting note that matters.** `owl:disjointWith` is symmetric and IFC4
serialises both directions. Counting triples gives 4,886; counting distinct
unordered pairs gives 2,443. This repository counts pairs. Getting this wrong
inflates any ontology that writes symmetry out explicitly, and IFC4 is the one
that does.

## 2. Asymmetry between the two sides of each crosswalk

| pair | ASI high | ASI low | ratio |
|---|---:|---:|---:|
| IDO x IFC4 | 5,361 | 18 | **297.8x** |
| SAREF4INMA x IFC4 | 5,361 | 10 | 536.1x |
| ISO 15926-2 x IFC4 | 5,361 | 918 | 5.8x |
| CFIHOS x IDO | 18 | 0 | **unbounded** |
| SAREF4INMA x AAS | 10 | 0 | **unbounded** |
| CFIHOS x IFC4 | 5,361 | 0 | **unbounded** |

Where one side is inert the ratio is reported as unbounded rather than divided by
a fudged 1.

## 3. Falsifiability rate, and why it reverses the reading above

The ASI is a property of an ontology in the abstract. The operational question is
narrower: **if I ground a concept under the wrong parent, will anything catch me?**

Define the falsifiability rate as the fraction of unordered class pairs `{A, B}`
that cannot share an instance. Ground a concept under both, and if the ontology
entails a contradiction, the mistake is detectable. If not, it ships silently.

| vocabulary | classes | disjointness axioms | pairs | detectable | **falsifiability** |
|---|---:|---:|---:|---:|---:|
| IDO / ISO 15926-14 | 49 | 15 | 1,176 | 893 | **75.94%** |
| ISO 15926-2:2003 | 201 | 781 | 20,100 | 9,408 | **46.81%** |
| IFC4 ADD2 | 1,286 | 2,443 | 826,255 | 94,626 | **11.45%** |
| SAREF core | 95 | 0 | 4,465 | 0 | **0.00%** |
| AAS metamodel | 64 | 0 | 2,016 | 0 | **0.00%** |
| CFIHOS V2.0 (IDO-aligned) | 1,397 | 0 | 975,106 | 0 | **0.00%** |
| OPC UA DI (lifted) | 53 | 0 | 1,378 | 0 | **0.00%** |

Computed in one pass over the hierarchy rather than by brute force: a pair
conflicts exactly when an ancestor of one is declared disjoint from an ancestor of
the other. For IFC4 that is the difference between a single run and 826,255
reasoner invocations.

### The result that matters

**IFC4 has 163 times more disjointness axioms than IDO, and is 6.6 times less
falsifiable.**

Axiom *count* is a bad proxy for checkability. Axiom *placement* is what decides
it. IDO's 15 disjointness axioms sit at the top of a 49-class hierarchy, so they
propagate down and separate three quarters of all class pairs. IFC4's 2,443 sit
between leaf siblings, where they distinguish `IfcWall` from `IfcBeam` and say
nothing about any pair drawn from different branches.

Had this repository stopped at the ASI table, it would have reported the opposite
and misleading conclusion, that IFC4 is the rigorous standard and IDO the loose
one. The falsifiability rate corrects it.

**Design lesson for ontology authors:** a small number of well-placed top-level
disjointness axioms buys far more checkability than thousands of leaf-level ones.
If you are choosing a grounding vocabulary, choose on falsifiability, not on size.

### The four zeroes

CFIHOS, the AAS metamodel, SAREF core and OPC UA DI cannot reject any grounding
whatsoever. No mis-mapping into them is detectable by a description-logic reasoner,
because none of them asserts a single disjointness axiom.

Running a reasoner over an alignment into these vocabularies and reporting that it
is consistent measures the vocabulary, not the alignment. It would return the same
answer for a deliberately absurd mapping. Where this repository publishes a
crosswalk against an inert standard, it says so and relies on SHACL and human
argument instead. See [`../crosswalks/cfihos-audit/`](../crosswalks/cfihos-audit/)
for the empirical demonstration on a real published alignment.

## 4. One standard, two renderings, and they disagree

Before aligning ISA-95 to anything, it is worth asking which ISA-95. Two bodies
render it independently, and the same is true of the AAS.

| standard | rendering A | rendering B | object-model Jaccard | containment B in A |
|---|---|---|---:|---:|
| ISA-95 / IEC 62264 | MESA B2MML (267 concepts) | OPC UA ISA-95 companion (45) | **0.054** | 35.6% |
| AAS | IDTA metamodel RDF (59) | OPC UA I4AAS companion (39) | **0.289** | 56.4% |

Measured after removing scaffolding that belongs to neither object model: B2MML's
OAGIS transaction wrappers (`Acknowledge*`, `Confirm*`, `Show*`) and the OPC UA
rendering's `cdt*` core datatypes. The raw figures before that fairness control are
0.039 and 0.299, so the correction moves the ISA-95 number in the direction of
*more* agreement and the finding survives it.

**Caveat, stated because it limits the claim:** these are name-level comparisons
after normalisation. Concepts that agree in meaning but differ in name will not
match, so these are a lower bound on semantic agreement. What they measure exactly
is whether a tool can join the two renderings by name, which is what integration
projects actually attempt.

## 5. What to do with all this

1. **Choose your grounding vocabulary on falsifiability rate**, not on class count
   or axiom count. IDO at 75.94% is a far better hub than IFC4 at 11.45%, despite
   being 26 times smaller.
2. **Never quote a clean reasoner report against an inert vocabulary as evidence.**
   State the falsifiability rate alongside it or the report means nothing.
3. **Where both sides are inert, do not run a reasoner at all.** Use SHACL over
   instance data, competency questions, and human review. See
   [`../crosswalks/isa95-aas/`](../crosswalks/isa95-aas/).
4. **Name the exact rendering you aligned**, by publisher and version.
5. **If you author an industrial ontology, add top-level disjointness.** It is the
   cheapest quality mechanism available and most of these standards have none.
