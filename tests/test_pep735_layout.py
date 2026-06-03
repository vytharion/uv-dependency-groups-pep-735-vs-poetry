import pytest

from groupcompare import (
    dev_dependencies,
    pep735_dev_dependencies,
    pep735_dev_dependency_names,
    pep735_groups,
    project_name,
)


def test_pep735_dev_group_is_declared():
    assert "dev" in pep735_groups()


def test_pep735_groups_contain_only_dev_for_now():
    assert pep735_groups() == ["dev"]


def test_pep735_dev_group_lists_three_tools():
    assert len(pep735_dev_dependencies()) == 3


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


def test_project_name_rejects_empty_requirement():
    with pytest.raises(ValueError, match="unrecognised PEP 508 requirement"):
        project_name("")
