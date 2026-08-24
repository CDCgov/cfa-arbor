import os
import uuid

import fsspec
import pytest

from arbor import Grove

pytestmark = pytest.mark.azure_e2e


@pytest.fixture
def azure_grove(pytestconfig):
    if not pytestconfig.getoption("--run-azure-e2e"):
        pytest.skip("use --run-azure-e2e to enable Azure tests")

    account_name = os.environ["ARBOR_AZURE_ACCOUNT_NAME"]
    container = os.environ["ARBOR_AZURE_CONTAINER"]
    assert account_name is not None, "Missing azure account name"
    assert container is not None, "Missing azure container"

    test_prefix = f"arbor-e2e/{uuid.uuid4().hex}"
    root = f"{container}/{test_prefix}"

    fs = fsspec.filesystem("abfs", account_name=account_name, skip_instance_cache=True)
    grove = Grove(root=root, fs=fs)

    try:
        grove.setup()
        yield grove
    finally:
        # Never widen cleanup beyond the unique prefix created by this fixture.
        assert test_prefix.startswith("arbor-e2e/")
        if fs.exists(root):
            fs.rm(root, recursive=True)


def test_complete_filesystem_lifecycle(azure_grove, tmp_path, filesystem_lifecycle):
    filesystem_lifecycle(azure_grove, tmp_path)
