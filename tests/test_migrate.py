from pathlib import Path

import pytest

from groupcompare import (
    caret_to_pep440,
    checklist_passes,
    checklist_report,
    migrate_group,
    migrate_groups,
    poetry_to_pep508,
    render_dependency_groups,
    tilde_to_pep440,
    verification_checklist,
)


# -- version constraint conversion -------------------------------------------


def test_caret_constraint_with_nonzero_major_bumps_major():
    assert caret_to_pep440("^8.0") == ">=8.0,<9.0"
    assert caret_to_pep440("^1.10") == ">=1.10,<2.0"
    assert caret_to_pep440("^1.6") == ">=1.6,<2.0"
    assert caret_to_pep440("^2.0") == ">=2.0,<3.0"


def test_caret_constraint_with_zero_major_bumps_minor():
    assert caret_to_pep440("^0.6") == ">=0.6,<0.7"


def test_caret_constraint_with_zero_major_and_minor_bumps_patch():
    assert caret_to_pep440("^0.0.3") == ">=0.0.3,<0.0.4"


def test_caret_constraint_rejects_non_caret_input():
    with pytest.raises(ValueError, match="not a caret constraint"):
        caret_to_pep440(">=1.0")


def test_tilde_constraint_bumps_minor_when_minor_given():
    assert tilde_to_pep440("~1.6") == ">=1.6,<1.7"
    assert tilde_to_pep440("~1.6.4") == ">=1.6.4,<1.7"


def test_tilde_constraint_bumps_major_when_only_major_given():
    assert tilde_to_pep440("~1") == ">=1.0,<2.0"


def test_tilde_constraint_rejects_non_tilde_input():
    with pytest.raises(ValueError, match="not a tilde constraint"):
        tilde_to_pep440("^1.0")


# -- spec assembly -----------------------------------------------------------


def test_poetry_to_pep508_handles_caret_string():
    assert poetry_to_pep508("pytest", "^8.0") == "pytest>=8.0,<9.0"


def test_poetry_to_pep508_handles_passthrough_pep440_range():
    assert poetry_to_pep508("rich", ">=13,<14") == "rich>=13,<14"


def test_poetry_to_pep508_drops_wildcard_constraint():
    assert poetry_to_pep508("anything", "*") == "anything"


def test_poetry_to_pep508_emits_python_marker_from_table():
    spec = poetry_to_pep508(
        "tomli", {"version": "^2.0", "python": "<3.11"}
    )
    assert spec == "tomli>=2.0,<3.0; python_version < '3.11'"


def test_poetry_to_pep508_table_without_marker_omits_semicolon():
    spec = poetry_to_pep508("anyio", {"version": "^4.0"})
    assert spec == "anyio>=4.0,<5.0"


def test_poetry_to_pep508_rejects_unknown_shape():
    with pytest.raises(ValueError, match="unsupported Poetry constraint"):
        poetry_to_pep508("foo", 42)


# -- group + groups migration -----------------------------------------------


def test_migrate_group_converts_each_member_and_sorts():
    result = migrate_group({"ruff": "^0.6", "mypy": "^1.10"})
    assert result == ["mypy>=1.10,<2.0", "ruff>=0.6,<0.7"]


def test_migrate_groups_skips_existing_dev_group_and_rebuilds_it():
    groups = migrate_groups()
    assert "dev" in groups
    assert groups["dev"] == [
        {"include-group": "docs"},
        {"include-group": "lint"},
        {"include-group": "test"},
    ]


def test_migrate_groups_produces_each_leaf_group_with_specs():
    groups = migrate_groups()
    assert groups["test"] == ["pytest>=8.0,<9.0"]
    assert groups["docs"] == ["mkdocs>=1.6,<2.0"]
    assert groups["lint"] == ["mypy>=1.10,<2.0", "ruff>=0.6,<0.7"]


# -- rendering ---------------------------------------------------------------


def test_render_dependency_groups_emits_toml_section_header():
    rendered = render_dependency_groups({"test": ["pytest>=8.0,<9.0"]})
    assert rendered.startswith("[dependency-groups]\n")
    assert 'test = [' in rendered
    assert '    "pytest>=8.0,<9.0",' in rendered


def test_render_dependency_groups_renders_include_group_inline_table():
    rendered = render_dependency_groups(
        {"dev": [{"include-group": "test"}]}
    )
    assert '{ include-group = "test" }' in rendered


def test_render_dependency_groups_rejects_unknown_entry():
    with pytest.raises(ValueError, match="cannot render"):
        render_dependency_groups({"weird": [42]})


def test_rendered_block_is_parseable_back_into_the_same_groups(tmp_path):
    rendered = render_dependency_groups(migrate_groups())
    target = tmp_path / "pyproject.toml"
    target.write_text(rendered, encoding="utf-8")

    import sys

    if sys.version_info >= (3, 11):
        import tomllib as _toml
    else:
        import tomli as _toml
    with target.open("rb") as handle:
        parsed = _toml.load(handle)["dependency-groups"]
    assert parsed["test"] == ["pytest>=8.0,<9.0"]
    assert parsed["lint"] == ["mypy>=1.10,<2.0", "ruff>=0.6,<0.7"]
    assert parsed["dev"] == [
        {"include-group": "docs"},
        {"include-group": "lint"},
        {"include-group": "test"},
    ]


# -- verification checklist --------------------------------------------------


def test_checklist_on_current_pyproject_passes():
    assert checklist_passes() is True


def test_checklist_lists_one_item_per_leaf_group_plus_three_global_checks():
    items = verification_checklist()
    leaf_membership_items = [
        i for i in items if i.name.startswith("group ")
    ]
    assert len(leaf_membership_items) == 3
    assert len(items) == 3 + 3


def test_checklist_report_marks_every_line_pass_when_pyproject_is_clean():
    report = checklist_report()
    assert "[PASS]" in report
    assert "[FAIL]" not in report


def _write_pyproject(tmp_path: Path, body: str) -> Path:
    target = tmp_path / "pyproject.toml"
    target.write_text(body, encoding="utf-8")
    return target


def test_checklist_fails_when_leaf_group_name_differs(tmp_path):
    pyproject = _write_pyproject(
        tmp_path,
        """
[tool.poetry.group.test.dependencies]
pytest = "^8.0"

[dependency-groups]
testing = ["pytest>=8.0,<9.0"]
dev = [{ include-group = "testing" }]
""",
    )
    assert checklist_passes(pyproject) is False
    fail_lines = [
        item for item in verification_checklist(pyproject) if not item.passed
    ]
    assert any(
        "leaf group names match" in item.name for item in fail_lines
    )


def test_checklist_fails_when_dev_group_has_inline_strings_instead_of_includes(
    tmp_path,
):
    pyproject = _write_pyproject(
        tmp_path,
        """
[tool.poetry.group.test.dependencies]
pytest = "^8.0"

[dependency-groups]
test = ["pytest>=8.0,<9.0"]
dev = ["pytest>=8.0,<9.0"]
""",
    )
    fail_names = [
        item.name
        for item in verification_checklist(pyproject)
        if not item.passed
    ]
    assert "dev group composes via include-group only" in fail_names


def test_checklist_fails_when_group_members_drift(tmp_path):
    pyproject = _write_pyproject(
        tmp_path,
        """
[tool.poetry.group.lint.dependencies]
ruff = "^0.6"
mypy = "^1.10"

[dependency-groups]
lint = ["ruff>=0.6,<0.7"]
dev = [{ include-group = "lint" }]
""",
    )
    items = verification_checklist(pyproject)
    drift = next(item for item in items if "group 'lint'" in item.name)
    assert drift.passed is False
    assert "mypy" in drift.detail
