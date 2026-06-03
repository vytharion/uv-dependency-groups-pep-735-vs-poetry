from groupcompare import (
    declared_groups,
    dev_dependencies,
    python_constraint,
    runtime_dependencies,
)
from groupcompare.poetry_layout import _poetry_table


def _group_deps(name: str) -> dict:
    groups = _poetry_table(None).get("group", {})
    return dict(groups.get(name, {}).get("dependencies", {}))


def test_runtime_dependencies_include_tomli():
    deps = runtime_dependencies()
    assert "tomli" in deps


def test_runtime_dependencies_strip_python_constraint():
    deps = runtime_dependencies()
    assert "python" not in deps


def test_python_constraint_matches_project_floor():
    assert python_constraint() == "^3.9"


def test_dev_group_pins_pytest():
    deps = dev_dependencies()
    assert "pytest" in deps
    assert deps["pytest"] == "^8.0"


def test_declared_groups_now_include_test_lint_docs():
    assert declared_groups() == ["dev", "docs", "lint", "test"]


def test_poetry_test_group_pins_pytest():
    assert _group_deps("test") == {"pytest": "^8.0"}


def test_poetry_lint_group_pins_ruff_and_mypy():
    assert _group_deps("lint") == {"ruff": "^0.6", "mypy": "^1.10"}


def test_poetry_docs_group_pins_mkdocs():
    assert _group_deps("docs") == {"mkdocs": "^1.6"}


def test_poetry_dev_group_redundantly_enumerates_every_tool():
    # Poetry has no include-group equivalent, so dev must hand-copy every
    # tool from test + lint + docs. Drift here is silent — that pain is
    # exactly what PEP 735's include-group fixes.
    dev = dev_dependencies()
    test_lint_docs = (
        set(_group_deps("test"))
        | set(_group_deps("lint"))
        | set(_group_deps("docs"))
    )
    assert set(dev) == test_lint_docs


def test_tomli_constraint_is_environment_marked():
    deps = runtime_dependencies()
    tomli_spec = deps["tomli"]
    assert isinstance(tomli_spec, dict)
    assert tomli_spec["python"] == "<3.11"
    assert tomli_spec["version"] == "^2.0"
