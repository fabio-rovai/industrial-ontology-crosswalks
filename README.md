# Industrial ontology crosswalks

**Open crosswalks between four pairs of industrial data standards, and the
measurement that explains why crosswalks like these fail.**

Maintained by [Tesseract Academy](https://gov.tesseract.academy).

## At a glance

- **Four crosswalk pairs**: ISO 15926-14 to IFC4, ISA-95 to the Asset
  Administration Shell, CFIHOS to ISO 15926-14, and SAREF4INMA to OPC UA.
- **Four of the seven standards measured cannot reject a mis-mapping at all.**
  CFIHOS, the AAS metamodel, SAREF core and OPC UA Device Information assert zero
  disjointness axioms, so a reasoner has nothing to contradict. A clean
  consistency report against them is not evidence.
- **IFC4 has 163x more disjointness axioms than ISO 15926-14 and is 6.6x less
  checkable** (falsifiability 11.45% against 75.94%). Axiom count is a bad proxy
  for rigour; axiom placement decides it.
- **Every correspondence in the flagship crosswalk passes validation alone, and
  the set collapses 29 classes when asserted together.** 29 of the 276 possible
  pairs are jointly unsafe. Per-mapping review cannot detect this by construction.
- **21 of 24 candidate axioms survive reasoner certification** with 0 new
  unsatisfiable classes, 0 conservativity violations and 1,038 cross-ontology
  entailments retained.

Nothing here is redistributed from a standards body. Every source is fetched by
IRI and pinned by sha256 in [`SOURCES.lock`](SOURCES.lock).

## Reproduce it

```bash
pip install -r requirements.txt
python scripts/fetch_sources.py --relock          # 23 artefacts, by IRI
python lift/b2mml_to_rdf.py                       # ISA-95 XSD  -> OWL
python lift/opcua_to_rdf.py                       # 5 OPC UA NodeSets -> OWL
python metrics/axiomatic_asymmetry.py --write     # the ASI table
python crosswalks/cfihos-audit/falsifiability.py  # falsifiability + CFIHOS audit (JDK)
python scripts/sssom_to_rdf.py                    # SSSOM -> RDF + SHACL validation
python reasoning/certify_bridge.py                # the four experiments (JDK, ~2h)
```

## What is here

| Path | What it is |
|---|---|
| [`crosswalks/ido-ifc/`](crosswalks/ido-ifc/) | The flagship. 24 correspondences and 8 asserted non-mappings between the ISO 15926-14 line and IFC4, plus [`DIVERGENCES.md`](crosswalks/ido-ifc/DIVERGENCES.md), which is the part worth reading. |
| [`crosswalks/cfihos-audit/`](crosswalks/cfihos-audit/) | An independent audit of a published third-party CFIHOS alignment, and the falsifiability metric. |
| [`crosswalks/isa95-aas/`](crosswalks/isa95-aas/) | Why this pair ships an argument instead of a mapping table: two official ISA-95 renderings agree on 5.4% of their object-model concepts. |
| [`crosswalks/saref-opcua/`](crosswalks/saref-opcua/) | 8 correspondences and 9 asserted absences. The absences outnumber the mappings, and that is the finding. |
| [`metrics/`](metrics/) | The Axiomatic Strength Index harness and [`RESULTS.md`](metrics/RESULTS.md). |
| [`lift/`](lift/) | ISA-95 and OPC UA ship schemas, not ontologies. These are the transformations, including what they refuse to do. |
| [`reasoning/`](reasoning/) | The crosswalk promoted to OWL and certified with HermiT. Four experiments, all reproducible. |
| [`shapes/`](shapes/) | SHACL shapes that reject a lazy crosswalk, including this author's own first draft. |

## The argument, in order

### 1. Lexical alignment is not weak here, it is useless

Exact normalised token overlap between the real published ontologies:

| pair | shared class names |
|---|---:|
| CFIHOS V2.0 x IFC4 ADD2 | **1** |
| ISO 15926-14 x IFC4 ADD2 | 7 |
| SAREF4INMA x IFC4 ADD2 | 3 |
| ISO 15926-2 x IFC4 ADD2 | 5 |

Across 1,397 and 1,286 classes, CFIHOS and IFC4 share exactly one name:
`PhysicalQuantity`. And as [`DIVERGENCES.md`](crosswalks/ido-ifc/DIVERGENCES.md)
shows, that one is a false friend.

### 2. Most of these standards cannot tell you that you are wrong

An ontology can only prove a mapping impossible if it holds an axiom capable of
deriving a contradiction. The **falsifiability rate** is the fraction of class
pairs that provably cannot share an instance, and it is the ceiling on what any
automated check can catch.

| vocabulary | classes | disjointness | falsifiability |
|---|---:|---:|---:|
| ISO 15926-14 (IDO) | 49 | 15 | **75.94%** |
| ISO 15926-2:2003 | 201 | 781 | 46.81% |
| IFC4 ADD2 | 1,286 | 2,443 | **11.45%** |
| SAREF core | 95 | 0 | **0.00%** |
| AAS metamodel | 64 | 0 | **0.00%** |
| CFIHOS V2.0 (IDO-aligned) | 1,397 | 0 | **0.00%** |
| OPC UA DI (lifted) | 53 | 0 | **0.00%** |

Two conclusions. The four zeroes mean a reasoner check against those vocabularies
measures the vocabulary, not the alignment. And IFC4, despite 163 times more
disjointness than IDO, is 6.6 times less checkable, because its axioms sit between
leaf siblings while IDO's sit at the top of the hierarchy and propagate.

Had this repository stopped at counting axioms it would have reported the opposite
and misleading conclusion. See [`metrics/RESULTS.md`](metrics/RESULTS.md).

### 3. Correspondences are safe alone and lethal together

Both flagship sources are natively coherent: 0 unsatisfiable classes each, and 0
merged with no bridge. So all damage below belongs to the crosswalk.

| experiment | asserted | new unsatisfiable | invented subsumptions |
|---|---|---:|---:|
| E3 ablation | each correspondence alone | **0**, all 24 | **0**, all 24 |
| E3b pairwise | each of 276 pairs | 29 pairs unsafe | |
| E2 naive | all 24 together | **29** | **91** |
| E4 certified | 21 reasoner-chosen axioms | **0** | **0** |

The classes destroyed include `IfcSite`, `IfcBuilding`, `IfcBuildingStorey` and
`IfcSpace`: the spatial spine of IFC, which is exactly what a plant-to-building
handover needs. One invented subsumption entails that every process stream is a
manufactured article.

**The smallest unit of failure is a pair of mappings, not a mapping.** Any review
process that examines correspondences one at a time is structurally blind to this.

### 4. What survives

An orientation search asks the reasoner, per correspondence, whether equivalence,
one direction, the other direction, or nothing is safe given everything already
accepted. The result is
[`reasoning/ido-ifc-bridge-certified.ttl`](reasoning/ido-ifc-bridge-certified.ttl):
21 axioms, 10 full equivalences and 11 one-directional, passing relative
coherence, conservativity and anti-triviality.

The strongest correspondence in the set is one no label matcher would find. IDO
declares `Actual` disjoint from `Specified`. IFC declares `IfcObject` disjoint
from `IfcTypeObject`. Two committees, one from process industry and one from
construction, working decades apart, independently drew the same line between the
thing as designed and the thing as built, and independently made it exclusive.

**Start a crosswalk at the matching disjointness, not the matching labels.**

## Sources

All open, all fetched by IRI, none redistributed. Full list with checksums in
[`SOURCES.lock`](SOURCES.lock).

- **IDO / ISO 15926-14**: POSC Caesar, `rds.posccaesar.org/ontology/lis14/ont/core`
- **ISO 15926-2:2003**: OWL rendering mirrored by NIST, `usnistgov/iso15926`
- **IFC4 ADD2 (ISO 16739)**: `buildingsmart-community/ifcOWL`. The
  standards.buildingsmart.org OWL URLs return HTTP 403 to automated clients.
- **CFIHOS V2.0**: `tecnomod-um/cfihos`, generated from the IOGP Excel
  specification by Abad-Navarro, Fernandez-Breis and Garcia-Castro. Not an IOGP
  artefact, and no IOGP material is restated here.
- **Asset Administration Shell**: IDTA, `admin-shell-io/aas-specs`
- **ISA-95 / IEC 62264**: MESA International B2MML XML Schemas, plus the OPC
  Foundation ISA-95 companion NodeSet
- **OPC UA**: OPC Foundation core, DI, Machinery, ISA-95 and I4AAS NodeSets
- **SAREF and SAREF4INMA**: ETSI

## Status and honesty about scope

This is a **candidate-for-review** crosswalk set, version 0.1.0, published so that
people working across these standards start from something concrete and arguable
rather than from nothing. The correspondences are hand-authored and the confidence
values are a curator's judgement, stated as such and not presented as computed
scores.

Two pairs deliberately ship arguments rather than mapping tables, because building
a mapping table where both sides are refutation-inert would produce something that
looks authoritative and could never be checked. Saying so is the more useful
contribution.

Corrections and disagreements are welcome as issues. The measurements are all
reproducible, so a disagreement about a number can be settled by running the code.

## Related

- [ies-hqdm-crosswalk](https://github.com/fabio-rovai/ies-hqdm-crosswalk): the same
  reasoner-certification method applied to UK defence data.
- [open-ontologies](https://github.com/fabio-rovai/open-ontologies): the engine
  behind the alignment and validation primitives.
- Course: *Running Open Ontologies: Build, Validate and Certify a Standards
  Crosswalk*, on [tesseract.academy](https://tesseract.academy).
- Case study: [gov.tesseract.academy/research/industrial-ontology-crosswalks](https://gov.tesseract.academy/research/industrial-ontology-crosswalks)

## Licence

CC BY 4.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

Cite via [CITATION.cff](CITATION.cff). If you use the CFIHOS audit, please also
cite the ontology it audits (see
[`crosswalks/cfihos-audit/README.md`](crosswalks/cfihos-audit/README.md)).
