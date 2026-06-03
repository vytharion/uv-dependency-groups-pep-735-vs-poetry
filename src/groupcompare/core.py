"""Tiny façade returned by the scaffold step.

Later steps in the article grow this module: Poetry's dependency groups
land first, then PEP 735 [dependency-groups] replaces them under uv. Step
1 just needs *something* importable so pytest has a real target.
"""

from __future__ import annotations

from typing import Mapping

_KNOWN_LAYOUTS: Mapping[str, str] = {
    "poetry": "[tool.poetry.group.<name>.dependencies]",
    "pep735": "[dependency-groups]",
}


def describe_layout(tool: str) -> str:
    key = tool.strip().lower()
    if key not in _KNOWN_LAYOUTS:
        raise ValueError(f"unknown layout: {tool!r}")
    return _KNOWN_LAYOUTS[key]
