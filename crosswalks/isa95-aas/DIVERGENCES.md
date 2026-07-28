# ISA-95 ↔ AAS: where the two models genuinely disagree

The crosswalk is [`isa95-aas.sssom.tsv`](isa95-aas.sssom.tsv): **7 correspondences and
11 asserted non-mappings or absences**. When the denials outnumber the mappings by
more than one and a half to one, the denials are the deliverable.

The single sentence that explains the whole pair: **ISA-95 is a domain model and the
AAS metamodel is a container model.** ISA-95 says what a factory contains, equipment,
material, personnel, process segments. The AAS metamodel says how to package
statements about an asset, shells, submodels, typed elements. They meet at exactly
one layer, the property and its semantic definition, and both reach it through
IEC 61360.

Neither side asserts a single disjointness axiom, so **nothing here can be
reasoner-certified** (see [`../../metrics/RESULTS.md`](../../metrics/RESULTS.md)).
Validate with SHACL over instance data and with human review.

---

## D1. An Asset Administration Shell is not the asset

**The trap.** The obvious first move is `isa95:Equipment ≡ aas:AssetAdministrationShell`.
Both are "the machine" in casual conversation.

**Why it is wrong.** An `AssetAdministrationShell` is the **digital representation**
of an asset. The asset itself is referenced from inside it through
`aas:AssetInformation` and its `globalAssetId`. Equating the shell with the
equipment produces three concrete failures:

- deleting a record deletes a pump;
- two shells for one pump, which is normal during handover between an EPC and an
  operator, become two pumps;
- a shell for an asset type and a shell for an asset instance become the same
  physical object.

**What to do instead.** Map ISA-95 `Equipment` to the asset that the shell
*describes*, reached through `aas:AssetInformation`, and map identity through
`aas:SpecificAssetId`. Both routes are in the crosswalk.

This is the representation-versus-referent error, and it is the most common
modelling mistake in Industry 4.0 integration work.

## D2. `OperationsCapability` is not `aas:Capability`

**The trap.** The names match exactly, which makes this the highest-scoring pair for
any lexical matcher and the one a reviewer waves through.

**Why it is wrong.** `aas:Capability` is the implementation-independent **potential**
of an asset to achieve an effect. It is qualitative and timeless: this machine can
weld. An ISA-95 `OperationsCapability` is a **quantity of capability over a stated
time interval**, decomposed into committed, available and unattainable capacity, and
it exists precisely so that a scheduling system can reason about how much welding is
available next Tuesday.

One is a disposition. The other is a scheduled quantity with a clock attached. A tool
that equates them will read "this machine can weld" as "this machine has unlimited
welding capacity for all time".

**What to do instead.** Nothing at class level. If you need capability *and* capacity
in an AAS world, the capacity part belongs in a submodel with its own time-bounded
properties, and the crosswalk records that as an absence.

## D3. AAS does not distinguish a property of a class from a property of an instance

ISA-95 is explicit about the difference between `EquipmentClassProperty` (all pumps of
this class have a rated flow) and `EquipmentProperty` (this pump's rated flow is 40
cubic metres per hour). The distinction drives the whole ISA-95 class model.

The AAS metamodel has one construct, `aas:Property`, and resolves the difference by
convention: a submodel template carries the class-level statement, a submodel instance
carries the value. That convention lives outside the metamodel, so a crosswalk against
the metamodel cannot express it.

The consequence is asymmetric and worth stating plainly. Going ISA-95 to AAS you must
choose a convention and record it somewhere the metamodel cannot see. Going AAS to
ISA-95 you cannot always tell which you have.

## D4. Whole regions of ISA-95 have no AAS counterpart at all

The AAS metamodel contains no concept of:

- **material**, in any form: no material class, definition, lot or sublot, so no
  genealogy and no traceability;
- **personnel**: no person, personnel class, qualification or test specification;
- **operational location**: no enterprise, site, area, work centre or work unit, so no
  plant hierarchy;
- **process segment**: no grouping of the resources a production step needs;
- **scheduling and performance**: ISA-95 Parts 2 and 4 have nothing to map onto.

That is most of ISA-95. All of it is recorded in the crosswalk as an asserted absence
rather than left as a silent gap, because "no mapping found" and "no counterpart
exists" are different claims and only the second one is true here.

The standard answer, that these live in IDTA submodel templates, is correct and does
not help: submodel templates are published separately, are not part of the metamodel,
and each would need its own crosswalk. If someone offers you an ISA-95 to AAS
alignment, ask which submodel templates it covers.

## D5. Which ISA-95, and which AAS?

Measured in [`triangulate.py`](triangulate.py), and the reason this directory exists
at all:

| standard | rendering A | rendering B | object-model Jaccard |
|---|---|---|---:|
| ISA-95 | MESA B2MML (267 concepts) | OPC UA ISA-95 companion (45) | **0.054** |
| AAS | IDTA metamodel RDF (59) | OPC UA I4AAS companion (39) | **0.289** |

Two bodies render ISA-95 independently and agree on about 5% of object-model concept
names. Only 35.6% of the concepts in the smaller OPC UA rendering can be found by name
in MESA's.

This crosswalk is authored against **MESA B2MML lifted by
[`../../lift/b2mml_to_rdf.py`](../../lift/b2mml_to_rdf.py)** and the **IDTA metamodel
RDF**. It does not transfer unchanged to the OPC UA renderings of either standard.

Caveat on those numbers: they are name-level comparisons after normalisation, so they
are a lower bound on semantic agreement. What they measure is whether a tool can join
the renderings by name, which is what integration projects attempt.

---

## The one thing to take away

The only durable join between these two worlds is the **semantic identifier**. Both
sides reach IEC 61360, ISA-95 through class property definitions and the AAS through
`ConceptDescription` and `DataSpecificationIec61360`. IRDIs survive the modelling
differences that class names do not.

Join on identifiers. Do not join on class names.
