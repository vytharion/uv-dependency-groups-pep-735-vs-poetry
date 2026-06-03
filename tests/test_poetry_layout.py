from groupcompare import (
    declared_groups,
    dev_dependencies,
    python_constraint,
    runtime_dependencies,
)


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


def test_declared_groups_contains_only_dev_for_now():
    assert declared_groups() == ["dev"]


def test_tomli_constraint_is_environment_marked():
    deps = runtime_dependencies()
    tomli_spec = deps["tomli"]
    assert isinstance(tomli_spec, dict)
    assert tomli_spec["python"] == "<3.11"
    assert tomli_spec["version"] == "^2.0"
