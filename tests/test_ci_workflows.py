from pathlib import Path

import pytest

from groupcompare import (
    dev_group_sync_command,
    isolated_install_uses_no_default_groups,
    matrix_groups,
    pep735_groups,
    per_group_sync_command,
    tool_command_for_group,
    workflow_exists,
    workflow_text,
)
from groupcompare.ci_workflows import WORKFLOW_PATH


def test_ci_workflow_file_is_committed_at_the_canonical_path():
    assert WORKFLOW_PATH.name == "ci.yml"
    assert WORKFLOW_PATH.parent.name == "workflows"
    assert WORKFLOW_PATH.parent.parent.name == ".github"
    assert workflow_exists()


def test_workflow_text_is_not_empty():
    assert workflow_text().strip() != ""


def test_workflow_runs_on_push_and_pull_request_to_main():
    text = workflow_text()
    assert "on:" in text
    assert "push:" in text
    assert "pull_request:" in text
    assert '"main"' in text


def test_matrix_iterates_exactly_the_pep735_leaf_groups():
    # The whole point of step 6 is "install one group at a time". The
    # matrix must therefore list only the leaf groups (test/lint/docs),
    # not the composed `dev` group — `dev` gets its own job.
    assert matrix_groups() == ["test", "lint", "docs"]


def test_matrix_groups_are_a_subset_of_declared_pep735_groups():
    declared = set(pep735_groups())
    for group in matrix_groups():
        assert group in declared


def test_matrix_does_not_install_dev_group_via_matrix():
    assert "dev" not in matrix_groups()


def test_isolated_install_step_uses_matrix_group_variable():
    cmd = per_group_sync_command()
    assert cmd is not None
    assert "${{ matrix.group }}" in cmd
    assert "--no-default-groups" in cmd


def test_dev_group_job_installs_composed_group_in_isolation():
    cmd = dev_group_sync_command()
    assert cmd is not None
    assert "--group dev" in cmd
    assert "--no-default-groups" in cmd


def test_every_uv_sync_invocation_opts_out_of_default_groups():
    # If any `uv sync` line forgot --no-default-groups, the job would
    # silently install the project's default groups too and the CI
    # signal — "this group works alone" — would be meaningless.
    assert isolated_install_uses_no_default_groups() is True


def test_test_group_runs_pytest_in_its_case_branch():
    cmd = tool_command_for_group("test")
    assert cmd is not None
    assert "pytest" in cmd
    assert cmd.startswith("uv run")


def test_lint_group_runs_ruff_in_its_case_branch():
    cmd = tool_command_for_group("lint")
    assert cmd is not None
    assert "ruff" in cmd
    assert cmd.startswith("uv run")


def test_docs_group_runs_mkdocs_in_its_case_branch():
    cmd = tool_command_for_group("docs")
    assert cmd is not None
    assert "mkdocs" in cmd
    assert cmd.startswith("uv run")


def test_unknown_group_has_no_case_branch():
    assert tool_command_for_group("ghost") is None


def test_per_group_run_uses_no_sync_to_avoid_re_resolving():
    # `uv run --no-sync` makes the run step reuse the env from the
    # preceding `uv sync` — without it, uv would silently re-resolve
    # using the default groups and defeat the isolation contract.
    for group in matrix_groups():
        cmd = tool_command_for_group(group)
        assert cmd is not None
        assert "--no-sync" in cmd


def test_workflow_uses_official_uv_setup_action():
    text = workflow_text()
    assert "astral-sh/setup-uv" in text


def test_workflow_uses_checkout_action():
    assert "actions/checkout@v4" in workflow_text()


# -- synthetic fixtures lock down the parser shape ----------------------------


def _write(tmp_path: Path, body: str) -> Path:
    target = tmp_path / "ci.yml"
    target.write_text(body, encoding="utf-8")
    return target


_FAKE_WORKFLOW = """\
name: fake
on: [push]
jobs:
  iso:
    strategy:
      matrix:
        group: [alpha, beta]
    steps:
      - run: uv sync --group ${{ matrix.group }} --no-default-groups
      - run: |
          case "${{ matrix.group }}" in
            alpha)
              uv run --no-sync ruff check .
              ;;
            beta)
              uv run --no-sync mypy src
              ;;
          esac
  dev:
    steps:
      - run: uv sync --group dev --no-default-groups
"""


def test_parser_recovers_matrix_groups_from_fixture(tmp_path):
    target = _write(tmp_path, _FAKE_WORKFLOW)
    assert matrix_groups(target) == ["alpha", "beta"]


def test_parser_recovers_per_group_sync_command_from_fixture(tmp_path):
    target = _write(tmp_path, _FAKE_WORKFLOW)
    cmd = per_group_sync_command(target)
    assert cmd is not None
    assert "${{ matrix.group }}" in cmd


def test_parser_recovers_dev_sync_command_from_fixture(tmp_path):
    target = _write(tmp_path, _FAKE_WORKFLOW)
    cmd = dev_group_sync_command(target)
    assert cmd == "uv sync --group dev --no-default-groups"


def test_parser_recovers_case_branch_bodies_from_fixture(tmp_path):
    target = _write(tmp_path, _FAKE_WORKFLOW)
    assert tool_command_for_group("alpha", target) == "uv run --no-sync ruff check ."
    assert tool_command_for_group("beta", target) == "uv run --no-sync mypy src"
    assert tool_command_for_group("missing", target) is None


def test_parser_flags_missing_no_default_groups(tmp_path):
    body = """\
jobs:
  bad:
    steps:
      - run: uv sync --group test
"""
    target = _write(tmp_path, body)
    assert isolated_install_uses_no_default_groups(target) is False


def test_parser_returns_empty_matrix_when_absent(tmp_path):
    body = """\
jobs:
  plain:
    steps:
      - run: echo hi
"""
    target = _write(tmp_path, body)
    assert matrix_groups(target) == []


def test_workflow_exists_reports_false_for_missing_file(tmp_path):
    assert workflow_exists(tmp_path / "nope.yml") is False


def test_workflow_text_raises_when_path_does_not_exist(tmp_path):
    with pytest.raises(FileNotFoundError):
        workflow_text(tmp_path / "nope.yml")
