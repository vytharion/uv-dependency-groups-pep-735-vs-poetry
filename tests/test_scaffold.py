import pytest

import groupcompare
from groupcompare import describe_layout


def test_package_exposes_version():
    assert groupcompare.__version__ == "0.1.0"


def test_describe_layout_returns_poetry_table_path():
    assert describe_layout("poetry") == "[tool.poetry.group.<name>.dependencies]"


def test_describe_layout_returns_pep735_table_path():
    assert describe_layout("pep735") == "[dependency-groups]"


def test_describe_layout_is_case_insensitive():
    assert describe_layout("  Poetry  ") == "[tool.poetry.group.<name>.dependencies]"


def test_describe_layout_rejects_unknown_tool():
    with pytest.raises(ValueError, match="unknown layout"):
        describe_layout("pipenv")
