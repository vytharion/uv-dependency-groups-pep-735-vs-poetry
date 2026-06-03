"""Introspect the GitHub Actions workflow that installs PEP 735 groups in isolation.

Step 6 lands `.github/workflows/ci.yml` with one matrix entry per
dependency group (`test`, `lint`, `docs`). Each matrix leg runs
`uv sync --group <name> --no-default-groups` so CI proves the groups are
genuinely independent — installing one does not pull in the others. A
second job sanity-checks the composed `dev` group, mirroring the
include-group story from step 4.

The helpers here treat the workflow as text + regex. We deliberately do
not pull PyYAML in: the article is about uv dependency groups, so adding
a YAML library to the runtime install would muddy the example. The
parser only has to recognise the small shape we authored next door.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
)

_MATRIX_RE = re.compile(r"^\s*group:\s*\[([^\]]+)\]\s*$", re.MULTILINE)
_PER_GROUP_SYNC_RE = re.compile(
    r"uv sync\s+--group\s+\$\{\{\s*matrix\.group\s*\}\}\s+--no-default-groups"
)
_DEV_SYNC_RE = re.compile(r"uv sync\s+--group\s+dev\s+--no-default-groups")
_CASE_BRANCH_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9_-]+)\)\s*\n\s*(?P<body>uv run[^\n]+)",
    re.MULTILINE,
)


def workflow_text(path: Optional[Path] = None) -> str:
    target = path or WORKFLOW_PATH
    return target.read_text(encoding="utf-8")


def workflow_exists(path: Optional[Path] = None) -> bool:
    target = path or WORKFLOW_PATH
    return target.is_file()


def matrix_groups(path: Optional[Path] = None) -> List[str]:
    match = _MATRIX_RE.search(workflow_text(path))
    if match is None:
        return []
    raw = match.group(1)
    items = [chunk.strip().strip("'\"") for chunk in raw.split(",")]
    return [item for item in items if item]


def per_group_sync_command(path: Optional[Path] = None) -> Optional[str]:
    match = _PER_GROUP_SYNC_RE.search(workflow_text(path))
    return match.group(0) if match else None


def dev_group_sync_command(path: Optional[Path] = None) -> Optional[str]:
    match = _DEV_SYNC_RE.search(workflow_text(path))
    return match.group(0) if match else None


def tool_command_for_group(
    group: str, path: Optional[Path] = None
) -> Optional[str]:
    for match in _CASE_BRANCH_RE.finditer(workflow_text(path)):
        if match.group("name") == group:
            return match.group("body").strip()
    return None


def isolated_install_uses_no_default_groups(
    path: Optional[Path] = None,
) -> bool:
    text = workflow_text(path)
    sync_lines = [line for line in text.splitlines() if "uv sync" in line]
    if not sync_lines:
        return False
    return all("--no-default-groups" in line for line in sync_lines)
