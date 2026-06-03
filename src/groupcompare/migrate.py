"""Translate Poetry's dependency tables into a PEP 735 [dependency-groups] block.

Step 7 of the article hands the reader a script they can run on their own
project: read the `[tool.poetry.group.*]` tables, convert each Poetry
version constraint to PEP 508, and emit an equivalent `[dependency-groups]`
mapping plus an `include-group`-composed `dev` group. A verification
checklist double-checks the conversion so the reader can delete the
Poetry tables only when every line says PASS.

The conversion is intentionally narrow. It covers the constraint shapes
this article actually exercises (`^`, `~`, exact, plain PEP 440 ranges,
wildcard, and `{version = ..., python = ...}` tables). Anything else
raises so the caller has to look at it by hand instead of getting a
silently-wrong migration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from groupcompare.pep735_layout import (
    pep735_group_items,
    pep735_groups,
    pep735_resolve_group,
    project_name,
)
from groupcompare.poetry_layout import _poetry_table, declared_groups


_CARET_RE = re.compile(r"^\^(\d+)(?:\.(\d+))?(?:\.(\d+))?$")
_TILDE_RE = re.compile(r"^~(\d+)(?:\.(\d+))?(?:\.(\d+))?$")
_PYTHON_MARKER_RE = re.compile(r"^([<>!=]=?|==)\s*([0-9][\w.]*)$")


def caret_to_pep440(constraint: str) -> str:
    match = _CARET_RE.match(constraint)
    if match is None:
        raise ValueError(f"not a caret constraint: {constraint!r}")
    major = int(match.group(1))
    minor = int(match.group(2)) if match.group(2) is not None else 0
    patch_raw = match.group(3)
    floor_parts = [str(major), str(minor)]
    if patch_raw is not None:
        floor_parts.append(patch_raw)
    floor = ".".join(floor_parts)
    ceiling = _caret_ceiling(major, minor, patch_raw)
    return f">={floor},<{ceiling}"


def _caret_ceiling(major: int, minor: int, patch_raw: Optional[str]) -> str:
    if major > 0:
        return f"{major + 1}.0"
    if minor > 0:
        return f"0.{minor + 1}"
    patch = int(patch_raw) if patch_raw is not None else 0
    return f"0.0.{patch + 1}"


def tilde_to_pep440(constraint: str) -> str:
    match = _TILDE_RE.match(constraint)
    if match is None:
        raise ValueError(f"not a tilde constraint: {constraint!r}")
    major = int(match.group(1))
    minor_raw = match.group(2)
    patch_raw = match.group(3)
    if minor_raw is None:
        return f">={major}.0,<{major + 1}.0"
    minor = int(minor_raw)
    floor_parts = [str(major), str(minor)]
    if patch_raw is not None:
        floor_parts.append(patch_raw)
    return f">={'.'.join(floor_parts)},<{major}.{minor + 1}"


def _bound_constraint(text: str) -> str:
    cleaned = text.strip()
    if not cleaned or cleaned == "*":
        return ""
    if cleaned.startswith("^"):
        return caret_to_pep440(cleaned)
    if cleaned.startswith("~"):
        return tilde_to_pep440(cleaned)
    return cleaned


def _marker_from_python(constraint: str) -> str:
    match = _PYTHON_MARKER_RE.match(constraint.strip())
    if match is None:
        raise ValueError(f"unsupported python marker: {constraint!r}")
    return f"python_version {match.group(1)} '{match.group(2)}'"


def poetry_to_pep508(name: str, constraint: Any) -> str:
    if isinstance(constraint, str):
        bound = _bound_constraint(constraint)
        return f"{name}{bound}"
    if isinstance(constraint, Mapping):
        return _poetry_table_to_spec(name, constraint)
    raise ValueError(f"unsupported Poetry constraint shape: {constraint!r}")


def _poetry_table_to_spec(name: str, table: Mapping[str, Any]) -> str:
    version = str(table.get("version", "")).strip()
    bound = _bound_constraint(version) if version else ""
    spec = f"{name}{bound}"
    python = table.get("python")
    if not python:
        return spec
    return f"{spec}; {_marker_from_python(str(python))}"


def migrate_group(deps: Mapping[str, Any]) -> List[str]:
    return sorted(poetry_to_pep508(name, spec) for name, spec in deps.items())


def migrate_groups(path: Optional[Path] = None) -> Dict[str, List[Any]]:
    poetry = _poetry_table(path).get("group", {})
    leaf_groups: Dict[str, List[Any]] = {}
    for name, body in poetry.items():
        if name == "dev":
            continue
        leaf_groups[name] = migrate_group(body.get("dependencies", {}))
    members = sorted(leaf_groups.keys())
    leaf_groups["dev"] = [{"include-group": m} for m in members]
    return leaf_groups


def render_dependency_groups(groups: Mapping[str, Sequence[Any]]) -> str:
    """Render a `[dependency-groups]` TOML block from migrated groups."""
    lines: List[str] = ["[dependency-groups]"]
    for name in sorted(groups.keys()):
        lines.append(f"{name} = [")
        for entry in groups[name]:
            lines.append(f"    {_render_entry(entry)},")
        lines.append("]")
    return "\n".join(lines) + "\n"


def _render_entry(entry: Any) -> str:
    if isinstance(entry, str):
        escaped = entry.replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(entry, Mapping) and "include-group" in entry:
        return f'{{ include-group = "{entry["include-group"]}" }}'
    raise ValueError(f"cannot render dependency-groups entry: {entry!r}")


@dataclass(frozen=True)
class ChecklistItem:
    name: str
    passed: bool
    detail: str = ""


def verification_checklist(
    path: Optional[Path] = None,
) -> List[ChecklistItem]:
    poetry_leaves = sorted(g for g in declared_groups(path) if g != "dev")
    pep_leaves = sorted(g for g in pep735_groups(path) if g != "dev")
    items: List[ChecklistItem] = [
        _check_leaf_group_names(poetry_leaves, pep_leaves),
        _check_dev_uses_includes_only(path),
        _check_dev_includes_match_leaves(path, pep_leaves),
    ]
    items.extend(_check_each_leaf_membership(path, poetry_leaves, pep_leaves))
    return items


def _check_leaf_group_names(
    poetry_leaves: Sequence[str], pep_leaves: Sequence[str]
) -> ChecklistItem:
    return ChecklistItem(
        name="leaf group names match between Poetry and PEP 735",
        passed=list(poetry_leaves) == list(pep_leaves),
        detail=f"poetry={list(poetry_leaves)} pep735={list(pep_leaves)}",
    )


def _check_dev_uses_includes_only(path: Optional[Path]) -> ChecklistItem:
    raw = pep735_group_items("dev", path)
    only_includes = bool(raw) and all(
        isinstance(entry, dict) and "include-group" in entry for entry in raw
    )
    return ChecklistItem(
        name="dev group composes via include-group only",
        passed=only_includes,
        detail=f"raw={raw}",
    )


def _check_dev_includes_match_leaves(
    path: Optional[Path], pep_leaves: Sequence[str]
) -> ChecklistItem:
    raw = pep735_group_items("dev", path)
    included = sorted(
        entry["include-group"]
        for entry in raw
        if isinstance(entry, dict) and "include-group" in entry
    )
    return ChecklistItem(
        name="dev group includes every leaf group exactly once",
        passed=included == list(pep_leaves),
        detail=f"included={included} leaves={list(pep_leaves)}",
    )


def _check_each_leaf_membership(
    path: Optional[Path],
    poetry_leaves: Sequence[str],
    pep_leaves: Sequence[str],
) -> List[ChecklistItem]:
    items: List[ChecklistItem] = []
    common = sorted(set(poetry_leaves) & set(pep_leaves))
    for name in common:
        items.append(_compare_single_group_members(path, name))
    return items


def _compare_single_group_members(
    path: Optional[Path], name: str
) -> ChecklistItem:
    poetry_table = _poetry_table(path).get("group", {}).get(name, {})
    poetry_names = sorted(poetry_table.get("dependencies", {}).keys())
    pep_names = sorted(project_name(s) for s in pep735_resolve_group(name, path))
    return ChecklistItem(
        name=f"group {name!r} has the same package names",
        passed=poetry_names == pep_names,
        detail=f"poetry={poetry_names} pep735={pep_names}",
    )


def checklist_passes(path: Optional[Path] = None) -> bool:
    return all(item.passed for item in verification_checklist(path))


def checklist_report(path: Optional[Path] = None) -> str:
    lines: List[str] = []
    for item in verification_checklist(path):
        marker = "PASS" if item.passed else "FAIL"
        lines.append(f"[{marker}] {item.name}")
        if not item.passed and item.detail:
            lines.append(f"       {item.detail}")
    return "\n".join(lines) + "\n"
