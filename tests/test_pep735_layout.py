from pathlib import Path

import pytest

from groupcompare import (
    dev_dependencies,
    pep735_dev_dependencies,
    pep735_dev_dependency_names,
    pep735_group_items,
    pep735_groups,
    pep735_resolve_group,
    pep735_resolved_group_names,
    project_name,
)


def test_pep735_dev_group_is_declared():
    assert "dev" in pep735_groups()


def test_pep735_groups_now_include_test_lint_docs():
    assert pep735_groups() == ["dev", "docs", "lint", "test"]


def test_pep735_dev_group_resolves_to_four_tools():
    assert len(pep735_dev_dependencies()) == 4


def test_pep735_dev_group_specs_are_strings():
    specs = pep735_dev_dependencies()
    assert all(isinstance(spec, str) for spec in specs)


def test_pep735_dev_group_pins_pytest_with_pep508_bounds():
    specs = pep735_dev_dependencies()
    pytest_spec = next(spec for spec in specs if spec.startswith("pytest"))
    assert pytest_spec == "pytest>=8.0,<9.0"


def test_pep735_dev_dependency_names_match_poetry_group():
    poetry_names = sorted(dev_dependencies().keys())
    assert pep735_dev_dependency_names() == poetry_names


def test_project_name_extracts_distribution_from_spec():
    assert project_name("pytest>=8.0,<9.0") == "pytest"
    assert project_name("ruff>=0.6,<0.7") == "ruff"
    assert project_name("mypy>=1.10,<2.0") == "mypy"
    assert project_name("mkdocs>=1.6,<2.0") == "mkdocs"


def test_project_name_rejects_empty_requirement():
    with pytest.raises(ValueError, match="unrecognised PEP 508 requirement"):
        project_name("")


# -- include-group composition ------------------------------------------------


def test_pep735_test_group_holds_pytest_only():
    assert pep735_resolve_group("test") == ["pytest>=8.0,<9.0"]


def test_pep735_lint_group_holds_ruff_and_mypy():
    assert pep735_resolve_group("lint") == [
        "ruff>=0.6,<0.7",
        "mypy>=1.10,<2.0",
    ]


def test_pep735_docs_group_holds_mkdocs():
    assert pep735_resolve_group("docs") == ["mkdocs>=1.6,<2.0"]


def test_pep735_dev_group_items_are_pure_include_directives():
    # The raw `dev` entries are not strings — they are
    # `{include-group = "..."}` tables. That is the whole point of
    # step 4: dev composes its members instead of restating them.
    raw = pep735_group_items("dev")
    assert raw == [
        {"include-group": "test"},
        {"include-group": "lint"},
        {"include-group": "docs"},
    ]


def test_pep735_dev_group_resolves_to_concat_of_members():
    expected = (
        pep735_resolve_group("test")
        + pep735_resolve_group("lint")
        + pep735_resolve_group("docs")
    )
    assert pep735_resolve_group("dev") == expected


def test_pep735_resolved_group_names_are_sorted_distribution_names():
    assert pep735_resolved_group_names("lint") == ["mypy", "ruff"]


def _write_pyproject(tmp_path: Path, body: str) -> Path:
    target = tmp_path / "pyproject.toml"
    target.write_text(body, encoding="utf-8")
    return target


def test_pep735_resolver_detects_include_group_cycle(tmp_path):
    pyproject = _write_pyproject(
        tmp_path,
        """
[dependency-groups]
a = [{ include-group = "b" }]
b = [{ include-group = "a" }]
""",
    )
    with pytest.raises(ValueError, match="include-group cycle"):
        pep735_resolve_group("a", pyproject)


def test_pep735_resolver_rejects_unknown_included_group(tmp_path):
    pyproject = _write_pyproject(
        tmp_path,
        """
[dependency-groups]
dev = [{ include-group = "ghost" }]
""",
    )
    with pytest.raises(KeyError, match="undefined dependency group"):
        pep735_resolve_group("dev", pyproject)


def test_pep735_resolver_rejects_malformed_entry(tmp_path):
    pyproject = _write_pyproject(
        tmp_path,
        """
[dependency-groups]
weird = [{ not_a_known_key = "x" }]
""",
    )
    with pytest.raises(ValueError, match="unrecognised dependency-groups entry"):
        pep735_resolve_group("weird", pyproject)
