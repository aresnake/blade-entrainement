# BLADE — V1 Generator Families V0

Date: 2026-08-31
Status: DECIDED

## Selected families

1. **Visserie** — fasteners and threaded mechanical parts.
2. **Transmission** — gears and related rotational mechanical components.
3. **Paliers / roulements** — bearings and bearing-support mechanical components.

## Selection rationale

These three families are selected because the repository already contains mature generators and controls for them (`visserie`, `engrenage`, `roulement`). They provide a coherent mechanical training domain while covering different geometric structures and parameter interactions.

They also minimize external-addon dependence: the existing implementations are suitable for headless-oriented validation, unlike a V1 centered on GUI-only or third-party addon behavior.

## Deferred families

- `geo`: retained as a useful geometric/procedural capability, but not selected as one of the three V1 product families.
- `granit`: retained and protected; its measured metric UV convention is valuable, but it is not a mechanical family.
- `escalier`: retained as the reference Geometry Nodes generator and contract test case, not as a V1 product family.
- furniture / architecture: deferred until the asset acceptance and procedural contracts are stable.

## V1 quality objective

The first release should prove the architecture across a small, coherent set of families rather than maximize the number of generators. Each selected family must eventually provide:

- stable generator identity and version;
- explicit parameter schema and units;
- reproducible recipe;
- build operation;
- artifact-reading controls;
- representative parameter sweep cases;
- machine-readable QC report.

## Non-goal

This document does not set triangle, texel-density or LOD budgets. Those belong to the acceptance baseline and target-specific production decisions.
