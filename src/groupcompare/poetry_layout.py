"""Read the Poetry-dialect dependency tables out of pyproject.toml.

Step 2 of the article lands `[tool.poetry.dependencies]` plus
`[tool.poetry.group.dev.dependencies]` next to the existing PEP 621
metadata. The helpers here parse those tables so the test suite can
lock the shape down before later steps mutate it into PEP 735.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

if sys.version_info >= (3, 11):
    import tomllib as _toml
else:
    import tomli as _toml


PYPROJECT_PATH = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _load(path: Optional[Path]) -> Mapping[str, Any]:
    target = path or PYPROJECT_PATH
    with target.open("rb") as handle:
        return _toml.load(handle)


def _poetry_table(path: Optional[Path]) -> Mapping[str, Any]:
    return _load(path).get("tool", {}).get("poetry", {})


def runtime_dependencies(path: Optional[Path] = None) -> Dict[str, Any]:
    deps = dict(_poetry_table(path).get("dependencies", {}))
    deps.pop("python", None)
    return deps


def python_constraint(path: Optional[Path] = None) -> Optional[str]:
    return _poetry_table(path).get("dependencies", {}).get("python")


def dev_dependencies(path: Optional[Path] = None) -> Dict[str, Any]:
    groups = _poetry_table(path).get("group", {})
    return dict(groups.get("dev", {}).get("dependencies", {}))


def declared_groups(path: Optional[Path] = None) -> List[str]:
    return sorted(_poetry_table(path).get("group", {}).keys())
