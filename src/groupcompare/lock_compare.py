"""Read poetry.lock and uv.lock and compare the resolved version graph.

Step 5 of the article generates both lock files from the same pyproject.toml
and asks the reader: do they pin the same packages to the same versions?
The helpers below parse each lock file into a flat ``{name: {versions}}``
mapping and expose three small queries on top: packages present in both,
packages only in one, and packages whose pinned version disagrees.

The root project itself (an editable install in uv.lock) is filtered out
so the comparison is apples-to-apples — we only care about resolved
*dependencies*, not the package under development.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

if sys.version_info >= (3, 11):
    import tomllib as _toml
else:
    import tomli as _toml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
POETRY_LOCK_PATH = PROJECT_ROOT / "poetry.lock"
UV_LOCK_PATH = PROJECT_ROOT / "uv.lock"
ROOT_PROJECT_NAME = "groupcompare"


def _load(path: Path) -> Mapping[str, Any]:
    with path.open("rb") as handle:
        return _toml.load(handle)


def _packages(data: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    return list(data.get("package", []))


def _is_editable(pkg: Mapping[str, Any]) -> bool:
    source = pkg.get("source")
    return isinstance(source, dict) and "editable" in source


def _collect_versions(
    packages: List[Mapping[str, Any]], skip_editable: bool
) -> Dict[str, Set[str]]:
    versions: Dict[str, Set[str]] = {}
    for pkg in packages:
        if skip_editable and _is_editable(pkg):
            continue
        name = pkg["name"]
        versions.setdefault(name, set()).add(pkg["version"])
    return versions


def poetry_lock_versions(
    path: Optional[Path] = None,
) -> Dict[str, Set[str]]:
    data = _load(path or POETRY_LOCK_PATH)
    return _collect_versions(_packages(data), skip_editable=False)


def uv_lock_versions(
    path: Optional[Path] = None,
) -> Dict[str, Set[str]]:
    data = _load(path or UV_LOCK_PATH)
    return _collect_versions(_packages(data), skip_editable=True)


def poetry_lock_packages(path: Optional[Path] = None) -> List[str]:
    return sorted(poetry_lock_versions(path).keys())


def uv_lock_packages(path: Optional[Path] = None) -> List[str]:
    return sorted(uv_lock_versions(path).keys())


def packages_in_both(
    poetry_path: Optional[Path] = None,
    uv_path: Optional[Path] = None,
) -> List[str]:
    poetry = set(poetry_lock_versions(poetry_path).keys())
    uv = set(uv_lock_versions(uv_path).keys())
    return sorted(poetry & uv)


def packages_only_in_poetry(
    poetry_path: Optional[Path] = None,
    uv_path: Optional[Path] = None,
) -> List[str]:
    poetry = set(poetry_lock_versions(poetry_path).keys())
    uv = set(uv_lock_versions(uv_path).keys())
    return sorted(poetry - uv)


def packages_only_in_uv(
    poetry_path: Optional[Path] = None,
    uv_path: Optional[Path] = None,
) -> List[str]:
    poetry = set(poetry_lock_versions(poetry_path).keys())
    uv = set(uv_lock_versions(uv_path).keys())
    return sorted(uv - poetry)


def version_disagreements(
    poetry_path: Optional[Path] = None,
    uv_path: Optional[Path] = None,
) -> Dict[str, Tuple[Set[str], Set[str]]]:
    poetry = poetry_lock_versions(poetry_path)
    uv = uv_lock_versions(uv_path)
    differences: Dict[str, Tuple[Set[str], Set[str]]] = {}
    for name in set(poetry) & set(uv):
        if poetry[name] != uv[name]:
            differences[name] = (poetry[name], uv[name])
    return differences


def _has_hash_entries(pkg: Mapping[str, Any]) -> bool:
    files = pkg.get("files")
    if isinstance(files, list) and any("hash" in f for f in files):
        return True
    wheels = pkg.get("wheels")
    if isinstance(wheels, list) and any("hash" in w for w in wheels):
        return True
    sdist = pkg.get("sdist")
    return isinstance(sdist, dict) and "hash" in sdist


def poetry_lock_is_hashed(path: Optional[Path] = None) -> bool:
    data = _load(path or POETRY_LOCK_PATH)
    packages = _packages(data)
    return bool(packages) and all(_has_hash_entries(pkg) for pkg in packages)


def uv_lock_is_hashed(path: Optional[Path] = None) -> bool:
    data = _load(path or UV_LOCK_PATH)
    packages = [pkg for pkg in _packages(data) if not _is_editable(pkg)]
    return bool(packages) and all(_has_hash_entries(pkg) for pkg in packages)


def poetry_lock_pins_are_exact(path: Optional[Path] = None) -> bool:
    versions = poetry_lock_versions(path)
    return all(len(v) == 1 for v in versions.values())
