# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import
from pathlib import Path

import dask_task_models_library
import pytest

pytest_plugins = [
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.pydantic_models",
]


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(dask_task_models_library.__file__).resolve().parent
    assert pdir.exists()
    return pdir
