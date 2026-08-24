from pathlib import Path

import pytest

from arbor import Grove


def pytest_addoption(parser):
    parser.addoption(
        "--run-azure-e2e",
        action="store_true",
        default=False,
        help="run tests against the configured Azure Blob account",
    )


@pytest.fixture
def config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "arbor-toml-dir"
    config_dir.mkdir()
    config_path = config_dir / "arbor.toml"

    grove_path = tmp_path / "grove"
    config_path.write_text(
        f'grove="{grove_path!s}"\n[filesystem]\nprotocol = "local"\n'
    )

    return config_path.resolve()


@pytest.fixture
def filesystem_lifecycle():
    """Return an assertion covering the filesystem operations Arbor requires."""

    def assert_complete(grove: Grove, tmp_path: Path) -> None:
        source = tmp_path / "moby.txt"
        source.write_text("Call me Ishmael")

        asset = grove.create_asset("myasset")
        first_version = asset.upload(source, metadata={"author": "Melville"})

        assert grove.list_assets() == ["myasset"]
        assert asset.list_data() == ["moby.txt"]
        assert asset.mode() == "file"
        assert asset.metadata() == {"author": "Melville"}

        destination = tmp_path / "downloaded.txt"
        asset.download(destination)
        assert destination.read_text() == "Call me Ishmael"

        second_version = asset.upload(source)
        assert second_version != first_version
        assert set(asset.list_versions()) == {first_version, second_version}

        events = [entry["event"] for entry in grove.read_log()]
        assert events == ["create_grove", "create_asset", "upload", "upload"]

        grove.validate()

    return assert_complete
