from pathlib import Path

import pytest

from arbor import ArborError, Grove


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
        assert grove.list_assets() == []
        grove.validate()

        file_source = tmp_path / "moby.txt"
        file_source.write_text("Call me Ishmael")

        dir_source = tmp_path / "dir-source"
        dir_source.mkdir()
        (dir_source / "readme.txt").write_text("Melville wrote this")
        (dir_source / "books").mkdir()
        (dir_source / "books" / "moby.txt").write_text("Call me Ishmael")

        asset = grove.create_asset("myasset")
        assert asset.list_versions() == []
        assert asset.latest_version() is None
        asset.validate()
        with pytest.raises(ArborError, match="has no versions"):
            asset.list_data()
        with pytest.raises(ArborError, match="has no versions"):
            asset.mode()
        with pytest.raises(ArborError, match="has no versions"):
            asset.metadata()

        first_version = asset.upload_file(file_source, metadata={"author": "Melville"})

        assert grove.list_assets() == ["myasset"]
        assert asset.list_data() == ["moby.txt"]
        assert asset.mode() == "file"
        assert asset.metadata() == {"author": "Melville"}

        destination = tmp_path / "downloaded.txt"
        asset.download_file(destination)
        assert destination.read_text() == "Call me Ishmael"
        with pytest.raises(ArborError, match="exists"):
            asset.download_file(destination)
        with pytest.raises(ArborError, match="does not exist"):
            asset.download_file(tmp_path / "missing" / "downloaded.txt")

        file_dest = tmp_path / "moby-download.txt"
        asset.download_file(file_dest)
        assert file_dest.read_text() == "Call me Ishmael"

        second_version = asset.upload_dir(dir_source)
        assert second_version != first_version
        assert set(asset.list_versions()) == {first_version, second_version}
        assert asset.mode() == "dir"
        assert asset.list_data() == ["books/moby.txt", "readme.txt"]

        dest_dir = tmp_path / "moby-download-dir"
        dest_dir.mkdir()
        asset.download_dir(dest_dir)
        assert (dest_dir / "readme.txt").exists()
        assert (dest_dir / "books" / "moby.txt").read_text() == "Call me Ishmael"

        events = [entry["event"] for entry in grove.read_log()]
        assert events == ["create_grove", "create_asset", "upload", "upload"]

        grove.validate()

    return assert_complete
