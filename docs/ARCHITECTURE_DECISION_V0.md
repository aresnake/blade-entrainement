# BLADE — Architecture Decision V0

Date: 2026-08-31
Status: DECIDED

## Decision

**Recipe-first is the canonical parametric representation. Geometry Nodes is an execution/runtime representation, not the source of truth.**

A generated asset is reproducible from:

```text
{ generator_id, generator_version, parameters, seed }
```

When a generator uses Geometry Nodes, the GN tree is an implementation artifact derived from the recipe. It may be retained in the `.blend` for interactive editing and inspection, but the recipe remains the authoritative description of intent.

## Why

### Reproducibility
A recipe is compact, serializable, diffable and independent of Blender's internal node-tree representation. This is required for headless generation, regression tests and future Blender-version migration.

### Post-generation editing
Interactive edits to a GN tree are useful, but they can diverge from the declared parameters. Therefore an edited GN tree must not silently redefine the canonical recipe. If an edited asset is to become reproducible, its changes must be promoted explicitly into generator parameters or recorded as a distinct non-canonical variant.

### QC
QC must be able to compare requested parameters with measured artifact properties. A recipe gives the expected intent; controls still read the produced artifact. This preserves the project's inverse-check discipline.

### Headless execution
Pure-Python generators can run without a GUI. Blender/GN generators can run in background mode. Both can consume the same recipe envelope without forcing the orchestrator to understand Blender internals.

## Consequences

- A generator registry will be recipe-oriented.
- `build(params)` produces an artifact; it does not become the canonical database of parameters.
- GN node groups may be regenerated from recipes.
- Interactive GN edits require an explicit synchronization/import operation if they are to become a recipe.
- `.blend` files are deliverables/cache/runtime containers, not the canonical parametric database.
- Generator version is part of the recipe and therefore changes to geometry semantics require a version bump.

## Rejected alternative

**Geometry-Nodes-first** was rejected as the canonical representation because node trees are Blender-specific, more cumbersome to diff/review, and insufficient as a common representation for generators that do not use Geometry Nodes.

## Scope

This decision does not select the three V1 generator families or establish final Fab triangle/texel/LOD budgets. Those remain separate decisions.
