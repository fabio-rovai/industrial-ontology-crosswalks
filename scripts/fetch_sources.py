#!/usr/bin/env python3
"""
Fetch every source standard by IRI into sources/.

This repository does NOT redistribute any standards body's artefact. It records
where each one lives, pulls it on demand, and pins the sha256 of what it got so
that every number in metrics/RESULTS.md is reproducible and falsifiable.

Usage:
    python scripts/fetch_sources.py            # fetch all, verify against SOURCES.lock
    python scripts/fetch_sources.py --relock   # refetch and rewrite SOURCES.lock
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "sources")
LOCK = os.path.join(ROOT, "SOURCES.lock")

# key -> (url, filename, accept-header or None, licence note)
SOURCES: dict[str, tuple[str, str, str | None, str]] = {
    "ido": (
        "https://rds.posccaesar.org/ontology/lis14/ont/core",
        "ido-lis14-core.ttl",
        "text/turtle",
        "Industrial Data Ontology (LIS14 core), POSC Caesar Association. "
        "The ISO 15926-14 standardisation-track rendering.",
    ),
    "iso15926-2": (
        "https://raw.githubusercontent.com/usnistgov/iso15926/master/standards/pca/ISO-15926-2_2003.ttl",
        "iso15926-2-2003.ttl",
        None,
        "ISO 15926-2:2003 data model, OWL rendering mirrored by NIST (usnistgov/iso15926).",
    ),
    "ifc": (
        "https://raw.githubusercontent.com/buildingsmart-community/ifcOWL/master/IFC4_ADD2.ttl",
        "ifc4-add2.ttl",
        None,
        "ifcOWL IFC4_ADD2 (ISO 16739). buildingSMART community mirror; the "
        "standards.buildingsmart.org OWL URLs return HTTP 403 to automated clients.",
    ),
    "aas": (
        "https://raw.githubusercontent.com/admin-shell-io/aas-specs/master/schemas/rdf/rdf-ontology.ttl",
        "aas-metamodel.ttl",
        None,
        "Asset Administration Shell metamodel, RDF rendering. IDTA / admin-shell-io.",
    ),
    "saref-core": (
        "https://saref.etsi.org/core/v3.2.1/saref.ttl",
        "saref-core-v3.2.1.ttl",
        "text/turtle",
        "SAREF core v3.2.1. ETSI, BSD-3-Clause-style ETSI licence.",
    ),
    "saref4inma": (
        "https://saref.etsi.org/saref4inma/v1.1.2/saref4inma.ttl",
        "saref4inma-v1.1.2.ttl",
        "text/turtle",
        "SAREF extension for industry and manufacturing v1.1.2. ETSI.",
    ),
    "opcua-nodeset": (
        "https://raw.githubusercontent.com/OPCFoundation/UA-Nodeset/latest/Schema/Opc.Ua.NodeSet2.xml",
        "opcua-nodeset2.xml",
        None,
        "OPC UA core NodeSet2. OPC Foundation. XML, not OWL: see lift/ for the RDF lift.",
    ),
    "opcua-di": (
        "https://raw.githubusercontent.com/OPCFoundation/UA-Nodeset/latest/DI/Opc.Ua.Di.NodeSet2.xml",
        "opcua-di-nodeset2.xml",
        None,
        "OPC UA Device Information (DI) companion specification NodeSet. OPC Foundation. "
        "This, not the core NodeSet, is where device semantics live.",
    ),
    "opcua-machinery": (
        "https://raw.githubusercontent.com/OPCFoundation/UA-Nodeset/latest/Machinery/Opc.Ua.Machinery.NodeSet2.xml",
        "opcua-machinery-nodeset2.xml",
        None,
        "OPC UA Machinery companion specification NodeSet. OPC Foundation.",
    ),
    "opcua-isa95": (
        "https://raw.githubusercontent.com/OPCFoundation/UA-Nodeset/latest/ISA-95/Opc.ISA95.NodeSet2.xml",
        "opcua-isa95-nodeset2.xml",
        None,
        "OPC UA ISA-95 companion specification NodeSet. OPC Foundation. An INDEPENDENT "
        "rendering of ISA-95 alongside MESA's B2MML, which makes triangulation possible: "
        "two bodies rendering the same standard need not agree.",
    ),
    "opcua-i4aas": (
        "https://raw.githubusercontent.com/OPCFoundation/UA-Nodeset/latest/I4AAS/Opc.Ua.I4AAS.NodeSet2.xml",
        "opcua-i4aas-nodeset2.xml",
        None,
        "OPC UA I4AAS companion specification NodeSet: the OPC Foundation's own mapping of "
        "the Asset Administration Shell into OPC UA. Prior art for the ISA-95 to AAS join.",
    ),
    "cfihos-ido": (
        "https://raw.githubusercontent.com/tecnomod-um/cfihos/main/ontology/CORE-CFIHOS-V2.0_ido.owl",
        "cfihos-v2.0-ido.owl",
        None,
        "CFIHOS V2.0 OWL aligned to IDO, by Abad-Navarro, Fernandez-Breis and "
        "Garcia-Castro (tecnomod-um/cfihos). Third-party rendering generated from "
        "the official IOGP CFIHOS Excel specification; NOT an IOGP artefact. "
        "This repository audits it, and does not restate IOGP material.",
    ),
}

# B2MML XSD set: fetched as a group because ISA-95 semantics are spread over files.
B2MML_BASE = "https://raw.githubusercontent.com/MESAInternational/B2MML-BatchML/master/Schema/"
B2MML_FILES = [
    "B2MML-Common.xsd",
    "B2MML-Equipment.xsd",
    "B2MML-Material.xsd",
    "B2MML-Personnel.xsd",
    "B2MML-PhysicalAsset.xsd",
    "B2MML-ProcessSegment.xsd",
    "B2MML-OperationsDefinition.xsd",
    "B2MML-OperationsSchedule.xsd",
    "B2MML-OperationsPerformance.xsd",
    "B2MML-OperationsCapability.xsd",
    "B2MML-OperationalLocation.xsd",
]


def _get(url: str, accept: str | None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "industrial-ontology-crosswalks/0.1"})
    if accept:
        req.add_header("Accept", accept)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def fetch_all() -> dict[str, dict]:
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(OUT, "b2mml"), exist_ok=True)
    got: dict[str, dict] = {}

    for key, (url, fname, accept, note) in SOURCES.items():
        dest = os.path.join(OUT, fname)
        print(f"  fetching {key:<14} -> {fname}", flush=True)
        data = _get(url, accept)
        with open(dest, "wb") as fh:
            fh.write(data)
        got[key] = {
            "url": url,
            "file": fname,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "licence_note": note,
        }

    for fname in B2MML_FILES:
        dest = os.path.join(OUT, "b2mml", fname)
        print(f"  fetching b2mml        -> {fname}", flush=True)
        data = _get(B2MML_BASE + fname, None)
        with open(dest, "wb") as fh:
            fh.write(data)
        got[f"b2mml/{fname}"] = {
            "url": B2MML_BASE + fname,
            "file": f"b2mml/{fname}",
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "licence_note": "B2MML, the XML rendering of ISA-95 / IEC 62264. MESA International.",
        }
    return got


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--relock", action="store_true", help="rewrite SOURCES.lock from what was fetched")
    args = ap.parse_args()

    print("Fetching sources by IRI (nothing here is redistributed):")
    got = fetch_all()

    if args.relock or not os.path.exists(LOCK):
        with open(LOCK, "w") as fh:
            json.dump(got, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"\nWrote {LOCK} ({len(got)} artefacts).")
        return 0

    with open(LOCK) as fh:
        locked = json.load(fh)

    drift = []
    for key, meta in got.items():
        if key not in locked:
            drift.append(f"  NEW      {key}")
        elif locked[key]["sha256"] != meta["sha256"]:
            drift.append(
                f"  CHANGED  {key}\n"
                f"           locked {locked[key]['sha256'][:16]}  now {meta['sha256'][:16]}"
            )
    for key in locked:
        if key not in got:
            drift.append(f"  MISSING  {key}")

    if drift:
        print("\nUpstream drift detected (the standards moved under us):")
        print("\n".join(drift))
        print("\nRe-run with --relock to accept, then re-run metrics/ to refresh the numbers.")
        return 1

    print(f"\nAll {len(got)} artefacts match SOURCES.lock. Numbers in metrics/ are reproducible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
