import re
from pathlib import Path, PurePath

import pytest

from arbor import ArborError, Grove
from arbor.backend import LocalBackend


@pytest.fixture
def backend(tmp_path) -> LocalBackend:
    root = tmp_path / "grove"
    return LocalBackend(root)


@pytest.fixture
def grove(backend) -> Grove:
    return Grove(backend).setup()


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


def test_backend_string(backend):
    assert re.match(r'LocalBackend\(".+"\)', repr(backend))


def test_new_grove_is_unconnected(backend):
    assert not Grove(backend).connected


def test_unconnected_cant_do_things(backend):
    grove = Grove(backend)
    with pytest.raises(ArborError, match="not connected"):
        grove.list_assets()


def test_connected_cant_reconnect(backend):
    grove = Grove(backend).connect()
    with pytest.raises(ArborError, match="already connected"):
        grove.connect()


def test_local_connection(grove):
    assert grove.connected


def test_second_connection(backend):
    grove1 = Grove(backend)
    grove2 = Grove(backend)
    grove1.connect()
    grove2.connect()


def test_local_scan(dir_source):
    backend = LocalBackend(dir_source)
    assert backend.scan(PurePath(".")) == (["books"], ["readme.json"])
    assert backend.scan(PurePath("books")) == ([], ["moby.txt"])

    grove = Grove(backend)
    assert grove._scan_recursive(PurePath(".")) == (
        [PurePath("books")],
        [PurePath("readme.json"), PurePath("books/moby.txt")],
    )


def test_lifecycle_file(grove, tmp_path):
    # can make an asset
    asset = grove.create_asset("myasset")
    assert grove.list_assets() == ["myasset"]

    # make a source file
    src = Path(tmp_path / "moby.txt")
    src.write_text("Call me Ishmael")

    # can upload
    version = asset.upload(src)
    assert asset.list_data() == [PurePath("moby.txt")]

    # this should be a file asset
    assert asset.mode() == "file"

    # can download
    destination = tmp_path / "moby_cache.txt"
    assert asset.download(destination) == destination.resolve()
    assert destination.read_text() == "Call me Ishmael"
    with pytest.raises(ArborError, match="already exists"):
        asset.download(destination)

    # if we upload again, new asset should be a different version
    src2 = src.rename(tmp_path / "moby2.txt")
    second_version = asset.upload(src2)
    assert second_version != version


def test_upload_metadata(grove, file_source):
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


def test_rename_asset(grove, tmp_path):
    src = tmp_path / "moby.txt"
    src.write_text("Call me Ishmael")

    asset = grove.create_asset("old-name")
    asset.upload(src)
    grove.rename_asset("old-name", "new-name")
    dst = grove.download("new-name", tmp_path / "download_moby.txt")
    assert dst.read_text() == "Call me Ishmael"


def test_invalid_ids(grove, tmp_path):
    for value in ("", ".hidden", "has space"):
        with pytest.raises(ArborError):
            grove.create_asset(value)


def test_grove_validation(grove):
    root = grove.backend.path
    assert isinstance(root, Path)
    (root / "manifest.json").write_text('{"schema_version":9}\n')
    with pytest.raises(ArborError, match="schema"):
        grove.validate()


def test_manifest_validation_is_recursive(grove, file_source):
    asset = grove.create_asset("myasset")
    asset.upload(file_source)
    root = grove.backend.path
    assert isinstance(root, Path)
    (root / "assets" / "myasset" / "manifest.json").write_text(
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
    config.write_text('[backend]\ntype = "local"\npath = "my-grove"\n')

    grove = Grove.from_config(config)

    assert isinstance(grove, Grove)
    backend = grove.backend
    assert isinstance(backend, LocalBackend)
    assert backend.path == (tmp_path / "my-grove").resolve()


def test_metadata_query(grove, tmp_path):
    asset = grove.create_asset("myasset")
    src = tmp_path / "moby.txt"
    src.write_text("Call me Ishmael")

    v1 = asset.upload(src, metadata={"name": "first upload"})
    v2 = asset.upload(src, metadata={"name": "second upload"})
    assert v2 != v1

    assert asset.find_versions_by_metadata({"name": "first upload"}) == [v1]
