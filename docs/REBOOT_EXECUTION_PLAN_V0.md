# BLADE Reboot — Execution Plan V0

Date: 2026-08-31
Status: ACTIVE

## Objective
Turn the existing BLADE training corpus into a reproducible, testable, versioned system before expanding the generator library.

## Execution order

1. **Preservation** — import the four infrastructure modules (`atelier`, `renfort`, `projet`, `banc`) and the `mobilier_paris` deliverables into the repository. No overwrite of existing tracked files. Production `.blend` files remain local when larger than transport limits; scripts, manifests, reports and source assets are versioned.
2. **Runtime proof** — execute a minimal `renfort.lancer()` headless job using `visserie.controle()`. Required evidence: JSON verdict, MCP call returning before 5 s, GUI remains responsive, child process exits cleanly.
3. **Baseline QC** — run the current 52-test bench on Blender 5.2. Separate headless-safe tests from GUI-dependent tests. Record every failure with cause; do not repair tests merely to make them green.
4. **Contract proof** — adapt `visserie` and `escalier` to the V0 generator contract without special cases in the orchestrator. The current contract already exists in `docs/BLADE_GENERATOR_CONTRACT_V0.md`. fileciteturn37file0L2-L2
5. **Canonical representation decision** — compare recipe-first and Geometry-Nodes-first against four requirements: reproducibility, post-generation editing, inspectability/QC, and headless execution. Record one decision before implementing the registry.
6. **V1 families** — select three families using objective criteria: existing generator maturity, mechanical usefulness, parameter richness, QC measurability, and independence from fragile external addons.
7. **Acceptance baseline** — keep Fab criteria sourced and versioned. Do not invent universal triangle/texel/LOD limits; distinguish hard source requirements from BLADE project budgets.
8. **Automation** — add machine-readable QC reports and a headless CI path. GUI-only checks remain explicitly classified rather than silently omitted.

## Non-negotiable engineering rules

- No destructive overwrite of production `.blend` files.
- No generated artifact is considered real until it is either committed or explicitly recorded as an intentional local-only artifact.
- Long operations run through the detached/headless path; direct MCP calls stay below the measured 60 s bridge ceiling.
- Controls read the produced artifact; theoretical values alone never establish QC.
- External addons are capabilities, not architectural dependencies, unless explicitly promoted and tested.
- Every architecture decision is written to the repository, not left only in chat.

## Definition of done for the reboot foundation

- Infrastructure is versioned.
- Current bench score is measured on Blender 5.2.
- Headless long-job path is proven.
- Generator contract is exercised by both an analytical and a Geometry Nodes generator.
- Canonical representation and V1 families are documented.
- QC output is machine-readable.
