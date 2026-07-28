# SAREF4INMA ↔ OPC UA: two standards that barely overlap

The result for this pair is negative, and the short mapping file is the finding
rather than a shortfall. SAREF4INMA and the OPC UA Device Information companion
specification are close to **complementary**: their shared vocabulary is
essentially *the device, its identification, its state*, and almost everything
either one says beyond that has no counterpart in the other.

[`saref-opcua.sssom.tsv`](saref-opcua.sssom.tsv) records **8 correspondences and 9
asserted absences**. When the absences outnumber the mappings, publishing the
absences is the useful act.

## What is genuinely shared

| SAREF | OPC UA | strength |
|---|---|---|
| `saref:Device` | `uadi:DeviceType` | close |
| `s4inma:ProductionEquipment` | `uadi:DeviceType` | narrower |
| `s4inma:ID`, `s4inma:IRDI` | `uamach:MachineryItemIdentificationType` | close |
| `saref:State` | `uadi:DeviceHealthEnumeration` | related |

The identification row is the most reusable thing in this file. **IEC 61360 IRDIs
are the one currency shared across SAREF4INMA, OPC UA, the AAS and ISA-95.** If you
need these worlds to interoperate, join on semantic identifiers, not on class names.

`uadi:DeviceHealthEnumeration` deserves a note: its values (NORMAL, FAILURE,
CHECK_FUNCTION, OFF_SPEC, MAINTENANCE_REQUIRED) come from NAMUR NE 107 and are the
closest thing to a shared vocabulary of device condition anywhere in this pair.

---

## D1. `saref:Function` is not `uadi:FunctionalGroupType`

**The trap.** Both contain the word "function", and both sit near devices.

**Why it is wrong.** `saref:Function` is what a device is **for**: a capability,
realised by commands, which a device bears whether or not it is exercising it.
`uadi:FunctionalGroupType` is a **folder**. It groups parameters in the address
space so that a browsing client can present them coherently. One is an ontological
commitment about capability; the other is a presentation-layer convenience.

Mapping them makes every device capability into a UI grouping, and every UI grouping
into a claim about what the machine can do.

**What to do instead.** Nothing. SAREF's functional layer has no OPC UA DI
counterpart. It is recorded as an asserted absence in the SSSOM so that integrators
stop looking for one.

## D2. `saref:State` is not a state machine

`uamach:MachineryItemState_StateMachineType` is the **automaton**: the set of states
and the transitions between them. `saref:State` is a **state**: one condition the
device is in. Mapping a state to a state machine is a level error, of the same kind
as mapping a value to its type.

The correspondence is kept at `skos:relatedMatch` rather than dropped, because a
tool walking from a SAREF state to the OPC UA state machine that governs it is doing
something reasonable. It is just not an equivalence.

## D3. Categories: a metamodelling mismatch, not a missing label

SAREF4INMA has `ItemCategory` and `ProductionEquipmentCategory`, which describe a
*type* of item or equipment as a first-class individual carrying its own properties.

OPC UA has no counterpart, and cannot have one at this level: in OPC UA the category
**is** the `ObjectType` in the address space. The type is part of the metamodel, not
part of the data, so it cannot itself be described as data without leaving the
modelling framework.

This is the same class-versus-instance mismatch that makes AAS submodel templates
awkward to align, and it is not fixable by adding mappings. Any integration has to
choose a side and lose something.

## D4. Two topologies that are not the same relation

SAREF4INMA inherits a **spatial** model from SAREF4BLDG: `Factory`, `Site`, `Area`,
`BuildingSpace`. OPC UA DI models **network and device topology**:
`TopologyElementType`, `ConnectionPointType`, `NetworkType`.

Both are "what is connected to what", and they are unrelated. Two devices adjacent
in an OPC UA topology may be in different buildings. Two devices in one `Area` may be
on unrelated networks. Joining these graphs produces a structure that is neither
spatial nor topological and is false in both readings.

## D5. Whole regions with no counterpart in either direction

**In OPC UA DI, invisible to SAREF:** the entire software lifecycle
(`SoftwareType`, `SoftwareLoadingType`, `PrepareForUpdateStateMachineType`,
`SoftwareVersionType`, `CachedLoadingType`), the nameplate interfaces
(`IVendorNameplateType`, `ITagNameplateType`), and the lifetime and wear counters
(`BaseLifetimeIndicationType` and its seven subclasses). SAREF models a device as a
functional thing and says nothing about the firmware running on it, its commercial
identity, or its remaining service life.

**In SAREF4INMA, invisible to OPC UA DI:** batches and lots (`Batch`, `ItemBatch`,
`MaterialBatch`), product identity (`Item`, GTIN identifiers), categories, and the
spatial model. Batch semantics do exist elsewhere in the OPC UA ecosystem, in the
PackML and ISA-95 companion specifications, but they cannot be reached from DI.

## The practical conclusion

Do not build a class-level crosswalk between these two. Build an **identifier-level**
join on IEC 61360 IRDIs, and accept that the device, its identity and its health are
the only things that cross cleanly.

Note also, from [`../cfihos-audit/`](../cfihos-audit/), that both sides of this pair
have a falsifiability rate of **0.00%**: neither SAREF core nor the lifted OPC UA DI
asserts a single disjointness axiom. Nothing you assert between them can be refuted
by a reasoner, so the review has to be human or SHACL-based. That is why this
directory ships an argument instead of a certification run.
