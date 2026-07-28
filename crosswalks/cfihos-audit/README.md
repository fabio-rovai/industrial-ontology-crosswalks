# CFIHOS ↔ IDO: an audit, not a rival crosswalk

CFIHOS (the Capital Facilities Information Handover Specification, IOGP) already
has an open OWL rendering aligned to the Industrial Data Ontology, produced by
Abad-Navarro, Fernández-Breis and García-Castro at Universidad de Murcia
([tecnomod-um/cfihos](https://github.com/tecnomod-um/cfihos)), generated
automatically from the official CFIHOS V2.0 Excel specification, with competency
questions, SHACL validation and OQuaRE quality reporting. It is the only open
machine-readable CFIHOS, and building a competing alignment would be a waste of
everyone's time.

So this directory does something else: it measures **how much of that alignment a
reasoner is in a position to check**. The answer turns out to be close to none,
for reasons that have nothing to do with the quality of their work and everything
to do with the vocabularies involved. The same result would hold for any
auto-generated grounding into IDO.

Reproduce:

```bash
python scripts/fetch_sources.py --relock
python crosswalks/cfihos-audit/falsifiability.py     # needs a JDK
```

## What was measured

The published `CORE-CFIHOS-V2.0_ido.owl` reasoned with HermiT:

| check | result |
|---|---|
| CFIHOS-IDO alone, unsatisfiable classes | **0** |
| CFIHOS-IDO merged with the complete IDO | **0** |

A clean bill of health. The question this directory asks is whether that result
carries any information.

## Where the groundings actually go

1,401 grounding edges connect 1,397 CFIHOS classes to IDO. They use **8 of IDO's
49 classes**, and they are distributed like this:

| IDO anchor | edges | share |
|---|---:|---:|
| `ido:Quality` | 772 | 55.1% |
| `ido:PhysicalQuantity` | 616 | 44.0% |
| `ido:InformationObject` | 8 | 0.6% |
| `ido:Role` | 1 | 0.1% |
| `ido:InanimatePhysicalObject` | 1 | 0.1% |
| `ido:PhysicalArtefact` | 1 | 0.1% |
| `ido:FunctionalObject` | 1 | 0.1% |
| `ido:QualityDatum` | 1 | 0.1% |

**99.1% of the grounding lands on two anchors, and `PhysicalQuantity` is a subclass
of `Quality`, so both are inside IDO's `Dependent` branch.** IDO's disjointness
separates branches: `Dependent` from `Object` from `Temporal`, and within `Object`
it separates `InformationObject`, `Location`, `Organization` and `PhysicalObject`.

Almost no grounding edge crosses a boundary that IDO can police. The zero above is
therefore guaranteed by the shape of the alignment before any reasoning happens.
It was not earned.

There is a second reading of the same table, and it is the one an asset-handover
practitioner should care about: CFIHOS exists to describe **equipment**, and the
equipment classes are essentially ungrounded. Four edges reach the physical-object
side of IDO in total. What has been aligned is the property dictionary, not the
asset model.

## Falsifiability rate

The audit generalises the point with a metric. Define the **falsifiability rate**
of a grounding vocabulary as the fraction of unordered class pairs `{A, B}` such
that nothing can be both an `A` and a `B`. If you ground a concept under two
classes and the ontology entails a contradiction, your mistake is detectable. If
not, it ships silently.

| vocabulary | classes | disjointness axioms | falsifiability rate |
|---|---:|---:|---:|
| IDO / ISO 15926-14 | 49 | 15 | **75.94%** |
| ISO 15926-2:2003 | 201 | 781 | 46.81% |
| IFC4 ADD2 | 1,286 | 2,443 | **11.45%** |
| SAREF core | 95 | 0 | **0.00%** |
| AAS metamodel | 64 | 0 | **0.00%** |
| CFIHOS V2.0 (IDO-aligned) | 1,397 | 0 | **0.00%** |
| OPC UA DI (lifted) | 53 | 0 | **0.00%** |

Two things fall out of this table, and the second one contradicts the first
impression.

**One.** Four of these vocabularies have a falsifiability rate of exactly zero. No
mis-grounding into CFIHOS, SAREF, the AAS metamodel or OPC UA DI can ever be
rejected by a reasoner, because none of them asserts a single disjointness axiom.
Running a reasoner over an alignment into these vocabularies and reporting that it
is consistent is not evidence of anything. It is a measurement of the vocabulary,
not of the alignment.

**Two, and more interesting.** IFC4 has **163 times** more disjointness axioms than
IDO and is **6.6 times less** falsifiable. Axiom *count* is a bad proxy for
checkability; axiom *placement* is what matters. IDO's 15 axioms sit at the top of
a 49-class hierarchy and propagate down to almost every pair. IFC's 2,443 sit
between leaf siblings, where they separate `IfcWall` from `IfcBeam` but say nothing
about any pair drawn from different branches.

A small, well-placed set of top-level disjointness axioms buys far more checkability
than thousands of leaf-level ones. That is a design lesson for anyone writing an
industrial ontology, and it is the opposite of what the raw axiom counts suggest.

## What would fix it

Not more mappings. The CFIHOS grounding could be made falsifiable by asserting the
disjointness CFIHOS already implies but never states: an equipment class and a
property class have no common instances, a document and a physical item have no
common instances. Those are uncontroversial claims that the source Excel
specification assumes throughout. Adding them would cost a handful of axioms and
would convert a 0% falsifiability rate into something a reasoner could work with.

This is offered as a suggestion to the CFIHOS ontology authors rather than a
criticism of them: the axioms are absent from the Excel source, so a faithful
automated conversion could not have invented them.

## Citation

If you use this audit, please also cite the ontology being audited:

> F. Abad-Navarro, J. T. Fernández-Breis, A. García-Castro. *Making CFIHOS
> Machine-Interpretable: An IDO-Aligned OWL Ontology for Asset Data
> Interoperability.* (manuscript in preparation)

CFIHOS itself is an IOGP publication. This repository references it through the
Murcia OWL rendering and does not redistribute IOGP material.
