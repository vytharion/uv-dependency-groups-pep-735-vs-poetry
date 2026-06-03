"""Read the PEP 735 [dependency-groups] table out of pyproject.toml.

Step 4 splits the single dev group into test / lint / docs and lets the
top-level `dev` group compose them via the PEP 735 `include-group`
directive. The helpers here parse the raw table, expose per-group
readers, and resolve `include-group` references recursively so callers
can ask "what does `dev` actually install?" without re-implementing the
spec.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Set

if sys.version_info >= (3, 11):
    import tomllib as _toml
else:
    import tomli as _toml


PYPROJECT_PATH = Path(__file__).resolve().parents[2] / "pyproject.toml"

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")


def _load(path: Optional[Path]) -> Mapping[str, Any]:
    target = path or PYPROJECT_PATH
    with target.open("rb") as handle:
        return _toml.load(handle)


def _dependency_groups_table(path: Optional[Path]) -> Mapping[str, Any]:
    return _load(path).get("dependency-groups", {})


def pep735_groups(path: Optional[Path] = None) -> List[str]:
    return sorted(_dependency_groups_table(path).keys())


def pep735_group_items(name: str, path: Optional[Path] = None) -> List[Any]:
    return list(_dependency_groups_table(path).get(name, []))


def _resolve_item(
    table: Mapping[str, Any], item: Any, seen: Set[str]
) -> List[str]:
    if isinstance(item, str):
        return [item]
    if isinstance(item, dict) and "include-group" in item:
        return _resolve(table, item["include-group"], seen)
    raise ValueError(f"unrecognised dependency-groups entry: {item!r}")


def _resolve(
    table: Mapping[str, Any], name: str, seen: Set[str]
) -> List[str]:
    if name in seen:
        raise ValueError(f"include-group cycle detected at {name!r}")
    if name not in table:
        raise KeyError(f"undefined dependency group: {name!r}")
    next_seen = seen | {name}
    resolved: List[str] = []
    for item in table[name]:
        resolved.extend(_resolve_item(table, item, next_seen))
    return resolved


def pep735_resolve_group(
    name: str, path: Optional[Path] = None
) -> List[str]:
    return _resolve(_dependency_groups_table(path), name, set())


def pep735_dev_dependencies(path: Optional[Path] = None) -> List[str]:
    return pep735_resolve_group("dev", path)


def project_name(requirement: str) -> str:
    match = _NAME_RE.match(requirement.strip())
    if match is None:
        raise ValueError(f"unrecognised PEP 508 requirement: {requirement!r}")
    return match.group(0)


def _names(specs: Iterable[str]) -> List[str]:
    return sorted(project_name(spec) for spec in specs)


def pep735_dev_dependency_names(path: Optional[Path] = None) -> List[str]:
    return _names(pep735_dev_dependencies(path))


def pep735_resolved_group_names(
    name: str, path: Optional[Path] = None
) -> List[str]:
    return _names(pep735_resolve_group(name, path))
