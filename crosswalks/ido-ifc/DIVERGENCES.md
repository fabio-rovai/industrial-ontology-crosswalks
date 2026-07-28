# IDO ↔ IFC4: where the two models genuinely disagree

Read this before the mapping table. The correspondences in
[`ido-ifc.sssom.tsv`](ido-ifc.sssom.tsv) are the easy part. The content is here:
the pairs that look alignable, are not, and will silently corrupt a plant-to-building
handover if a tool treats them as equal.

Everything below is measured, not argued. Reproduce with:

```bash
python scripts/fetch_sources.py --relock
python reasoning/certify_bridge.py        # needs a JDK
```

Raw output is in [`../../reasoning/results.json`](../../reasoning/results.json).

## The headline: no individual correspondence is faulty, and the set is catastrophic

Both sources are natively coherent. Reasoned alone, IDO has **0** unsatisfiable
classes and IFC4 ADD2 has **0**. Merged with no bridge, still **0**. So every defect
below is attributable to the crosswalk and to nothing else, which is a cleaner
experimental setup than most alignment work gets.

| experiment | what was asserted | new unsatisfiable classes | invented subsumptions |
|---|---|---:|---:|
| E1 baseline | nothing | 0 | 0 |
| E3 ablation | each correspondence **alone** | **0**, for all 24 | **0**, for all 24 |
| E2 naive | all 24 **together**, as `owl:equivalentClass` | **29** | **91** |
| E4 certified | 21 axioms, orientation chosen by the reasoner | **0** | **0** |

Every one of the 24 correspondences passes validation when checked on its own.
Assert them together and 29 IFC classes lose all possible instances, while the
merge invents 91 subsumptions that neither standard states, 17 of them internal
to IDO and 74 internal to IFC.

This matters beyond this pair. Reviewing a crosswalk correspondence by
correspondence, which is what mapping review, most alignment tooling and OAEI-style
evaluation all do, **cannot detect this class of fault by construction**. The
smallest unit of failure is a pair of mappings, not a mapping.

### The minimal conflict sets, located

Experiment E3b tests all C(24,2) = 276 pairs of equivalences. **29 pairs are
jointly unsafe**, every one of which passes single-edge validation. Four of them
destroy classes outright:

| pair | new unsatisfiable | what dies |
|---|---:|---|
| `PhysicalObject≡IfcProduct` + `Location≡IfcSpatialElement` | **20** | `IfcBuilding`, `IfcBuildingStorey`, `IfcExternalSpatialElement`, `IfcRelContainedInSpatialStructure`, ... |
| `InformationObject≡IfcPropertyDefinition` + `InformationObject≡IfcPropertySetDefinition` | **6** | the whole `IfcPropertyTemplate` branch |
| `ScalarQuantityDatum≡IfcQuantityLength` + `ScalarQuantityDatum≡IfcQuantityArea` | **3** | both quantity classes and the IDO datum class |
| `PhysicalObject≡IfcProduct` + `Site≡IfcSite` | **2** | `IfcSite` and `ido:Site` |

The remaining 25 pairs produce no unsatisfiability but invent subsumptions
internal to one of the sources, which is the quieter and arguably more dangerous
failure: nothing looks broken, and the merged graph now entails things neither
standard says. The worst offender is
`QualityDatum≡IfcPhysicalQuantity` + `InformationObject≡IfcPropertySetDefinition`
at 45 invented subsumptions.

The last row of the table is the mechanism spelled out in D3 below, confirmed by
measurement rather than argued: neither edge is at fault, and the pair is fatal.

Among the invented IDO-internal subsumptions are `ido:PhysicalObject ⊑ ido:Actual`,
`ido:Stream ⊑ ido:PhysicalArtefact` and `ido:Feature ⊑ ido:Actual`. None is asserted
by POSC Caesar. The second is plainly false: a stream is the fluid, and a physical
artefact is manufactured. A downstream tool reasoning over the merged graph would
conclude that every stream is a manufactured article.

The classes destroyed include `IfcSite`, `IfcBuilding`, `IfcBuildingStorey`,
`IfcSpace`, `IfcExternalSpatialElement` and the whole `IfcPropertyTemplate` branch.
That is not an obscure corner of IFC. It is the spatial spine of the schema, which
is precisely what a plant-to-building handover needs.

---

## D1. `ido:Object` is not `IfcObject`

**The trap.** The names are identical and both sit near the top of their model.

**Why it is wrong.** IDO declares `Object`, `Temporal` and `Dependent` mutually
disjoint, so an IDO `Object` explicitly **excludes** activities. IFC puts
`IfcProcess` **under** `IfcObject`, so an `IfcObject` explicitly **includes** them.
Asserting equivalence makes every process simultaneously an IDO `Object` and an IDO
`Temporal`, which IDO forbids.

**What to do instead.** Map the as-built axis, not the name:
`ido:Actual ≡ IfcObject` is certified safe, because both are the occurrence side of
their model's occurrence/type split.

## D2. `ido:System` is not `IfcSystem`

**The trap.** Identical names, and both mean roughly "a functional assembly".

**Why it is wrong.** This is a structural incompatibility, not a wording problem.
IDO puts `System` under `FunctionalObject`, and **does not declare `FunctionalObject`
disjoint from `PhysicalObject`**. That is deliberate: one pump is legitimately both a
functional object and a physical object. IFC puts `IfcSystem` under `IfcGroup`, and
**declares `IfcGroup` disjoint from `IfcProduct`**, one of a six-way disjoint
partition of `IfcObject` covering Product, Process, Actor, Control, Group and Resource.

So the moment you map `ido:PhysicalObject` to `IfcProduct` (which is the obvious and
correct move) and `ido:System` to `IfcSystem`, any individual that IDO permits to be
both becomes unsatisfiable. The disagreement is about whether function and physical
substance can inhere in one thing. IDO says yes; IFC says no.

**What to do instead.** The certified bridge keeps `IfcSystem ⊑ ido:System`, one
direction only. An IFC system is an IDO system; the converse fails.

## D3. `ido:Site` is not `IfcSite`

**The trap.** Identical names, both meaning "the place the facility is".

**Why it is wrong.** IDO puts `Site` under `Location`, and declares `Location`
disjoint from `PhysicalObject`, `InformationObject` and `Organization`. A location in
IDO is not a physical thing. IFC puts `IfcSite` under `IfcSpatialStructureElement`
and thence `IfcProduct`, so in IFC a site **is** a physical product with geometry and
placement. The two sit on opposite sides of IDO's own disjointness.

This is not a defect in either standard. It is the process-industry convention
(space is a frame of reference) meeting the building convention (space is a modelled
object with geometry). The orientation search **rejects this pair entirely**: no
direction of it is safe once the rest of the bridge is in place.

## D4. `ido:PhysicalQuantity` is not `IfcPhysicalQuantity`

**The trap.** The most seductive pair in the set, and the one a lexical matcher
scores highest. My own token matcher proposed it.

**Why it is wrong.** IDO `PhysicalQuantity` is a `Quality`, and thence a `Dependent`:
it is the length **borne by** the pipe. `IfcPhysicalQuantity` is a recorded
measurement value, an `IfcQuantityLength` carrying a number. IDO already has a class
for that and it is `QualityDatum`, sitting under `InformationObject` and thence
`Object`. Since IDO declares `Dependent` disjoint from `Object`, the two cannot be
equated.

This is the quality/datum conflation, and IDO is explicit that it exists to avoid it:
`QualityDatum` is documented as inspired by the Information Artifact Ontology's
measurement datum.

**What to do instead.** `ido:QualityDatum ≡ IfcPhysicalQuantity`. Certified safe,
and in the SSSOM.

## D5. `ido:Event` is not `IfcEvent`

**The trap.** Identical names, both temporal.

**Why it is wrong.** IDO's own definition of `Event` says it "doesn't need to be
temporally connected", and gives the example of several switch-on occurrences of a
heater across a week represented as **one** event individual. It is a scattered
temporal aggregate. `IfcEvent` is a discrete trigger in a process, declared disjoint
from `IfcTask` and `IfcProcedure`.

A scattered aggregate of occurrences is not a trigger point. Equating them makes a
week of heater cycles into a single instantaneous trigger.

**What to do instead.** The certified bridge keeps `IfcEvent ⊑ ido:Event`. Every IFC
event is an IDO event; the converse fails because IDO events may be scattered.

## D6. `ido:Stream` is not `IfcFlowSegment`

**The trap.** Both are what a process engineer points at when they say "the flow".

**Why it is wrong.** IDO `Stream` is under `InanimatePhysicalObject`: it is the fluid
in motion, the matter itself. `IfcFlowSegment` is under `IfcDistributionFlowElement`:
it is the pipe. Contents versus container.

Handover tooling that equates them will attach fluid properties (composition,
temperature, phase) to pipework, and pipe properties (material, diameter, insulation)
to the fluid. Nothing in either schema stops it, because neither model asserts the
disjointness that would catch it.

**What to do instead.** `IfcFlowSegment ⊑ ido:Stream` is what the orientation search
certifies as safe, but read that as a logical convenience rather than an
endorsement: the honest answer is that these two should be related by a
`contains`-style property, which SKOS cannot express. This is a case for EDOAL.

## D7. IDO's realisable branch has no IFC counterpart at all

IDO carries `Potential`, and under it `Disposition`, `Capability`, `Function`,
`Interest` and `Role`. This is the vocabulary for what a thing is **for**, and for
what it is **able to do**, independent of whether it is currently doing it.

IFC has none of this. It has predefined type enumerations (`IfcPumpTypeEnum` and
friends) that name a pump as a pump, but no class for the disposition a pump bears,
and no way to say that a valve is capable of isolating a line without asserting that
it is currently isolating one.

This is a **capability gap**, and it is recorded in the SSSOM as an asserted absence
rather than left as a silent hole, because "no mapping found" and "no counterpart
exists" are different claims and only the second one is true here.

The practical consequence: any handover that needs to carry function or capability
from a plant model into a building model has to extend IFC with property sets, and
those property sets are then outside the schema's own semantics and invisible to
IFC-aware tooling.

---

## What the reasoner kept

21 of 24 correspondences survive certification, at these strengths:

- **Full equivalence (10):** `Actual`/`IfcObject`, `Specified`/`IfcTypeObject`,
  `Person`/`IfcPerson`, `Organization`/`IfcOrganization`,
  `UnitOfMeasure`/`IfcNamedUnit`, `QualityDatum`/`IfcPhysicalQuantity`,
  `ScalarQuantityDatum`/`IfcQuantityLength`, `Compound`/`IfcMaterial`,
  `Interval`/`IfcTimePeriod`, `Quality`/`IfcProperty`.
- **One direction only (11):** `ido:Scale ⊑ IfcNamedUnit`, plus ten of the form IFC-into-IDO,
  including `IfcProcess ⊑ ido:Activity`,
  `IfcProduct ⊑ ido:PhysicalObject`, `IfcElement ⊑ ido:PhysicalArtefact`,
  `IfcPropertyDefinition ⊑ ido:InformationObject`,
  `IfcFeatureElement ⊑ ido:Feature`, `IfcActor ⊑ ido:Role`,
  `IfcSystem ⊑ ido:System`, `IfcEvent ⊑ ido:Event`,
  `IfcFlowSegment ⊑ ido:Stream`.
- **Rejected outright (3):** `Site`/`IfcSite` (D3),
  `Location`/`IfcSpatialElement` (the same category clash one level up),
  and `ScalarQuantityDatum`/`IfcQuantityArea` (IFC declares the quantity
  subclasses disjoint, so only one of them can be equated to IDO's single
  scalar datum class).

The certified bridge is [`../../reasoning/ido-ifc-bridge-certified.ttl`](../../reasoning/ido-ifc-bridge-certified.ttl):
0 new unsatisfiable classes, 0 conservativity violations, and it still entails
1,038 cross-ontology subsumptions, so it has not been trivially emptied.

## The finding that generalises

The strongest correspondence in the set is the one nobody would have found by
looking at names. IDO declares `Actual` disjoint from `Specified`. IFC declares
`IfcObject` disjoint from `IfcTypeObject`. Two committees, one from process
industry and one from construction, working decades apart, independently drew the
same line between the thing as designed and the thing as built, and independently
decided it was exclusive.

That is where a crosswalk between industrial standards should start: not at the
matching labels, but at the matching disjointness.
