"""Read the PEP 735 [dependency-groups] table out of pyproject.toml.

Step 3 mirrors the dev tooling from [tool.poetry.group.dev.dependencies]
into a top-level [dependency-groups] table. These helpers parse the
PEP 735 dialect so the test suite can prove the two views agree on
which packages belong to the dev group.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, List, Mapping, Optional

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


def pep735_dev_dependencies(path: Optional[Path] = None) -> List[str]:
    return list(_dependency_groups_table(path).get("dev", []))


def project_name(requirement: str) -> str:
    match = _NAME_RE.match(requirement.strip())
    if match is None:
        raise ValueError(f"unrecognised PEP 508 requirement: {requirement!r}")
    return match.group(0)


def pep735_dev_dependency_names(path: Optional[Path] = None) -> List[str]:
    return sorted(project_name(spec) for spec in pep735_dev_dependencies(path))
