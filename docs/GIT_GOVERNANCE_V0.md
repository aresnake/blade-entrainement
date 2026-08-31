# BLADE — Git Governance V0

Date: 2026-08-31

## Source of truth

`main` is the stable branch. Reboot work happens on a dedicated branch and enters
`main` through a pull request after verification.

## Rule: no untracked production

Any infrastructure or production asset required to reproduce a result must live
in Git. The user profile is not a backup system.

The following are explicitly migration targets from the 2026-08-31 audit:

- `atelier.py`
- `renfort.py`
- `projet.py`
- the canonical `banc.py`
- `mobilier_paris` source, recipes, scenes and exports that are actually part of
  the deliverable

Binary `.blend` files remain local when large, but their recipe/source, provenance
and verification report must be versioned.

## Branching

- `main`: stable, reproducible baseline.
- `reboot/*`: architectural recovery and migration.
- `feat/*`: isolated implementation work after the foundation is proven.
- No direct force-push to `main`.

## Commit discipline

Each commit must answer one question and leave the tree coherent. Verification
results belong in the repository, not only in chat logs.

Preferred sequence:

1. preserve/recover source;
2. add or update tests/checks;
3. run verification;
4. record the result;
5. commit;
6. merge only after the branch is reproducible.

## CI baseline

GitHub Actions compiles the Python tree and statically verifies the five currently
identified headless-safe generators:

`visserie`, `engrenage`, `roulement`, `geo`, `granit`.

CI intentionally does not claim Blender 5.2 runtime compatibility. That requires
the real Blender installation and is a separate runtime gate.
