from pathlib import Path

import pytest

from groupcompare import (
    packages_in_both,
    packages_only_in_poetry,
    packages_only_in_uv,
    poetry_lock_is_hashed,
    poetry_lock_packages,
    poetry_lock_pins_are_exact,
    poetry_lock_versions,
    uv_lock_is_hashed,
    uv_lock_packages,
    uv_lock_versions,
    version_disagreements,
)
from groupcompare.lock_compare import (
    POETRY_LOCK_PATH,
    ROOT_PROJECT_NAME,
    UV_LOCK_PATH,
)


def test_both_lock_files_exist():
    assert POETRY_LOCK_PATH.is_file()
    assert UV_LOCK_PATH.is_file()


def test_poetry_lock_lists_at_least_the_core_tools():
    names = poetry_lock_packages()
    for required in ("pytest", "ruff", "mypy", "mkdocs"):
        assert required in names


def test_uv_lock_lists_at_least_the_core_tools():
    names = uv_lock_packages()
    for required in ("pytest", "ruff", "mypy", "mkdocs"):
        assert required in names


def test_uv_lock_skips_the_editable_root_project():
    # uv tracks the workspace root as `{ source = { editable = "." } }`.
    # We filter that out so the diff only covers resolved dependencies.
    assert ROOT_PROJECT_NAME not in uv_lock_packages()


def test_poetry_lock_does_not_list_the_root_project():
    assert ROOT_PROJECT_NAME not in poetry_lock_packages()


def test_lock_parsing_is_deterministic_across_calls():
    assert poetry_lock_versions() == poetry_lock_versions()
    assert uv_lock_versions() == uv_lock_versions()


def test_poetry_lock_pins_each_package_to_one_exact_version():
    assert poetry_lock_pins_are_exact() is True
    versions = poetry_lock_versions()
    assert versions, "poetry.lock parsed empty"
    for name, vs in versions.items():
        assert len(vs) == 1, f"{name} has {len(vs)} versions in poetry.lock"


def test_poetry_lock_records_artifact_hashes():
    assert poetry_lock_is_hashed() is True


def test_uv_lock_records_artifact_hashes():
    assert uv_lock_is_hashed() is True


def test_packages_in_both_includes_the_shared_tooling():
    shared = set(packages_in_both())
    for tool in ("pytest", "ruff", "mypy", "mkdocs"):
        assert tool in shared


def test_overlap_set_is_symmetric_with_unique_sets():
    poetry_names = set(poetry_lock_packages())
    uv_names = set(uv_lock_packages())
    both = set(packages_in_both())
    only_poetry = set(packages_only_in_poetry())
    only_uv = set(packages_only_in_uv())
    assert both | only_poetry == poetry_names
    assert both | only_uv == uv_names
    assert both & only_poetry == set()
    assert both & only_uv == set()


def test_version_disagreements_returns_only_diverging_pins():
    diffs = version_disagreements()
    poetry = poetry_lock_versions()
    uv = uv_lock_versions()
    for name, (poetry_vs, uv_vs) in diffs.items():
        assert poetry_vs == poetry[name]
        assert uv_vs == uv[name]
        assert poetry_vs != uv_vs


def test_uv_may_pin_multiple_versions_when_resolver_branches_on_python():
    # uv supports `resolution-markers`, so the same dependency can resolve
    # to two versions under different Python ranges. Poetry collapses to
    # one. We don't assert it always happens, but if it does, the version
    # set has length > 1 — which is the determinism contract uv documents.
    uv = uv_lock_versions()
    multi = {name: vs for name, vs in uv.items() if len(vs) > 1}
    for name, vs in multi.items():
        assert all(isinstance(v, str) and v for v in vs)


# -- synthetic fixtures lock down the parser shape ----------------------------


def _write(tmp_path: Path, name: str, body: str) -> Path:
    target = tmp_path / name
    target.write_text(body, encoding="utf-8")
    return target


_POETRY_FIXTURE = """\
[[package]]
name = "alpha"
version = "1.0.0"
groups = ["dev"]
files = [
    {file = "alpha-1.0.0.tar.gz", hash = "sha256:aaaa"},
]

[[package]]
name = "beta"
version = "2.0.0"
groups = ["dev"]
files = [
    {file = "beta-2.0.0.tar.gz", hash = "sha256:bbbb"},
]
"""

_UV_FIXTURE = """\
version = 1

[[package]]
name = "alpha"
version = "1.0.0"
sdist = { url = "x", hash = "sha256:aaaa" }

[[package]]
name = "gamma"
version = "9.9.9"
sdist = { url = "x", hash = "sha256:gggg" }

[[package]]
name = "groupcompare"
version = "0.1.0"
source = { editable = "." }
"""


def test_parser_against_fixture_lock_files(tmp_path):
    poetry = _write(tmp_path, "poetry.lock", _POETRY_FIXTURE)
    uv = _write(tmp_path, "uv.lock", _UV_FIXTURE)

    assert poetry_lock_packages(poetry) == ["alpha", "beta"]
    assert uv_lock_packages(uv) == ["alpha", "gamma"]
    assert packages_in_both(poetry, uv) == ["alpha"]
    assert packages_only_in_poetry(poetry, uv) == ["beta"]
    assert packages_only_in_uv(poetry, uv) == ["gamma"]
    assert version_disagreements(poetry, uv) == {}


_POETRY_DISAGREE = """\
[[package]]
name = "alpha"
version = "1.0.0"
groups = ["dev"]
files = [
    {file = "alpha-1.0.0.tar.gz", hash = "sha256:aaaa"},
]
"""

_UV_DISAGREE = """\
version = 1

[[package]]
name = "alpha"
version = "1.2.0"
sdist = { url = "x", hash = "sha256:aaaa" }
"""


def test_parser_flags_version_drift_between_resolvers(tmp_path):
    poetry = _write(tmp_path, "poetry.lock", _POETRY_DISAGREE)
    uv = _write(tmp_path, "uv.lock", _UV_DISAGREE)

    diffs = version_disagreements(poetry, uv)
    assert set(diffs) == {"alpha"}
    poetry_vs, uv_vs = diffs["alpha"]
    assert poetry_vs == {"1.0.0"}
    assert uv_vs == {"1.2.0"}


def test_hash_check_rejects_lock_with_missing_artifacts(tmp_path):
    body = """\
[[package]]
name = "alpha"
version = "1.0.0"
groups = ["dev"]
files = []
"""
    target = _write(tmp_path, "poetry.lock", body)
    assert poetry_lock_is_hashed(target) is False


def test_exact_pin_check_rejects_lock_with_duplicate_versions(tmp_path):
    body = """\
[[package]]
name = "alpha"
version = "1.0.0"
groups = ["dev"]
files = [
    {file = "alpha-1.0.0.tar.gz", hash = "sha256:aaaa"},
]

[[package]]
name = "alpha"
version = "1.1.0"
groups = ["dev"]
files = [
    {file = "alpha-1.1.0.tar.gz", hash = "sha256:bbbb"},
]
"""
    target = _write(tmp_path, "poetry.lock", body)
    assert poetry_lock_pins_are_exact(target) is False


def test_uv_hash_check_skips_editable_root(tmp_path):
    # editable root has no files/wheels/sdist — that's fine, we ignore it.
    body = """\
version = 1

[[package]]
name = "alpha"
version = "1.0.0"
sdist = { url = "x", hash = "sha256:aaaa" }

[[package]]
name = "groupcompare"
version = "0.1.0"
source = { editable = "." }
"""
    target = _write(tmp_path, "uv.lock", body)
    assert uv_lock_is_hashed(target) is True
