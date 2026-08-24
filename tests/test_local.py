import textwrap
from pathlib import Path

import fsspec
import pytest
from fsspec.implementations.local import LocalFileSystem

from arbor import ArborError, Grove


@pytest.fixture
def grove(tmp_path) -> Grove:
    fs = fsspec.filesystem("local")
    grove = Grove(root=tmp_path / "grove", fs=fs)
    grove.setup()
    return grove


@pytest.fixture
def file_source(tmp_path) -> Path:
    root = tmp_path / "file_source"
    root.mkdir()
    src = root / "moby.txt"
    src.write_text("Call me Ishmael")
    return src


@pytest.fixture
def dir_source(tmp_path) -> Path:
    root = Path(tmp_path / "source")
    root.mkdir()
    (root / "readme.json").write_text('{"author": "Melville"}')
    (root / "books").mkdir()
    (root / "books" / "moby.txt").write_text("Call me Ishmael")
    return root


def test_local_instantiate(grove):
    grove


def test_second_connection(tmp_path):
    root = tmp_path / "grove"
    Grove(root=root, fs=fsspec.filesystem("local"))
    Grove(root=root, fs=fsspec.filesystem("local"))


def test_list_data_one_file(grove: Grove, file_source):
    asset = grove.create_asset("mybook")
    asset.upload(file_source)
    assert asset.list_data() == ["moby.txt"]


def test_list_versions(grove: Grove, file_source):
    asset = grove.create_asset("mybook")
    asset.upload(file_source)
    asset.upload(file_source)
    asset.upload(file_source)
    versions = asset.list_versions()
    assert len(versions) == 3
    assert len(versions[0]) == 6


def test_lifecycle_file(grove: Grove, tmp_path):
    # can make an asset
    asset = grove.create_asset("myasset")
    assert grove.list_assets() == ["myasset"]

    # make a source file
    src = Path(tmp_path / "moby.txt")
    src.write_text("Call me Ishmael")

    # can upload
    version = asset.upload(src)
    assert asset.list_data() == ["moby.txt"]

    # this should be a file asset
    assert asset.mode() == "file"

    # can download
    destination = tmp_path / "moby_cache.txt"
    asset.download(destination)
    assert destination.read_text() == "Call me Ishmael"

    # if we upload again, new asset should be a different version
    src2 = src.rename(tmp_path / "moby2.txt")
    second_version = asset.upload(src2)
    assert second_version != version


def test_upload_metadata(grove: Grove, file_source):
    asset = grove.create_asset("myasset")

    metadata = {
        "transform_version": "v1",
        "upstreams": {"raw": "abc123"},
        "note": "hello",
    }

    asset.upload(
        file_source,
        metadata=metadata,
    )

    assert asset.metadata() == metadata


def test_missing_version_metadata_defaults_to_empty(grove, file_source):
    asset = grove.create_asset("myasset")
    asset.upload(file_source)
    assert asset.metadata() == {}


def test_rename_asset(grove: Grove, tmp_path):
    src = tmp_path / "moby.txt"
    src.write_text("Call me Ishmael")

    asset = grove.create_asset("old-name")
    asset.upload(src)
    grove.rename_asset("old-name", "new-name")
    dst = tmp_path / "download_moby.txt"
    grove.download("new-name", dst)
    assert dst.read_text() == "Call me Ishmael"


def test_invalid_ids(grove, tmp_path):
    for value in ("", ".hidden", "has space"):
        with pytest.raises(ArborError):
            grove.create_asset(value)


def test_grove_validation(grove: Grove):
    Path(grove.root, "manifest.json").write_text('{"schema_version":9}\n')
    with pytest.raises(ArborError, match="schema"):
        grove.validate()


def test_manifest_validation_is_recursive(grove: Grove, file_source):
    asset = grove.create_asset("myasset")
    asset.upload(file_source)
    Path(grove.root, "assets", "myasset", "manifest.json").write_text(
        '{"latest_version":"bad-version"}\n'
    )
    with pytest.raises(ArborError, match="does not exist"):
        grove.validate()


def test_log_shape(grove, file_source):
    asset = grove.create_asset("my-asset")
    asset.upload(file_source)
    log = grove.read_log()
    print(log)
    assert len(log) == 3
    assert log[0]["event"] == "create_grove"
    assert "time" in log[0]
    assert log[1]["event"] == "create_asset"
    assert log[1]["asset_id"] == "my-asset"
    assert "time" in log[1]
    assert log[2]["event"] == "upload"
    assert "time" in log[2]
    assert "version" in log[2]


def test_from_config(tmp_path):
    config = tmp_path / "arbor.toml"
    config.write_text(
        textwrap.dedent("""
    grove = "/path/to/my-grove"
    [filesystem]
    protocol = "local"
    """)
    )

    grove = Grove.from_config(config)
    assert isinstance(grove.fs, LocalFileSystem)
    assert grove.root == Path("/", "path", "to", "my-grove")
