"""Static guard for generators intended to run without Blender.

This is deliberately AST-based: CI must not import project modules, because the
repository currently contains both pure-Python and bpy-dependent generators.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("visserie.py", "engrenage.py", "roulement.py", "geo.py", "granit.py")
FORBIDDEN_ROOTS = {"bpy"}


def imports_bpy(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] in FORBIDDEN_ROOTS for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in FORBIDDEN_ROOTS:
                return True
    return False


def has_callable(path: Path, name: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
        for node in tree.body
    )


errors: list[str] = []
for filename in TARGETS:
    path = ROOT / filename
    if not path.is_file():
        errors.append(f"missing: {filename}")
        continue
    if imports_bpy(path):
        errors.append(f"bpy import found: {filename}")
    if not has_callable(path, "controle"):
        errors.append(f"controle() missing: {filename}")

if errors:
    raise SystemExit("\n".join(errors))

print(f"OK: {len(TARGETS)} headless-safe generators checked")
