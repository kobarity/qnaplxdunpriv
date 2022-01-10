"""Test configurations
"""

# pylint: disable=missing-function-docstring

import pathlib
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    # pylint: disable=missing-class-docstring,too-few-public-methods
    class FixtureRequest:
        param: list[int]
else:
    from typing import Any
    FixtureRequest = Any


@pytest.fixture(params=[[10000], [10000, 20000]])
def uids(request: FixtureRequest) -> list[int]:
    return request.param


@pytest.fixture
def target_file(tmp_path: pathlib.Path) -> str:
    test_path = tmp_path / 'test-file'
    test_path.write_text('Test')
    return str(test_path)


@pytest.fixture
def target_dir(tmp_path: pathlib.Path) -> str:
    test_path = tmp_path / 'test-dir'
    test_path.mkdir()
    return str(test_path)


@pytest.fixture
def target_symlink(tmp_path: pathlib.Path) -> str:
    test_path = tmp_path / 'test-file'
    test_path.write_text('Test')
    test_link = tmp_path / 'test-link'
    test_link.symlink_to(test_path)
    return str(test_link)


@pytest.fixture
def target_symlink_ne(tmp_path: pathlib.Path) -> str:
    test_link = tmp_path / 'test-link'
    test_link.symlink_to('not-exist')
    return str(test_link)
