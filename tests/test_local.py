import json
import re
from pathlib import Path

import pytest

import arbor
from arbor.cli import run


@pytest.fixture
def raw_arbor(tmp_path):
    root = tmp_path / "arbor"
    root.mkdir()
    return arbor.LocalArbor(root)


@pytest.fixture
def local_arbor(raw_arbor):
    return raw_arbor.init()


@pytest.fixture
def source(tmp_path):
    root = Path(tmp_path / "source")
    root.mkdir()
    (root / "metadata.json").write_text('{"author": "Melville"}')
    (root / "books").mkdir()
    (root / "books" / "moby.txt").write_text("Call me Ishmael")
    return root


def test_arbor_string(raw_arbor):
    assert re.match(r'LocalArbor\(".+"\)', repr(raw_arbor))


def test_new_arbor_is_unconnected(raw_arbor):
    assert not raw_arbor.connected


def test_unconnected_cant_do_things(raw_arbor):
    with pytest.raises(arbor.Conflict, match="not connected"):
        raw_arbor.list_grove_ids()


def test_unconnected_cant_connect(raw_arbor):
    with pytest.raises(arbor.Invalid):
        raw_arbor.connect()


def test_local_connection(raw_arbor):
    assert raw_arbor.init() is raw_arbor
    assert raw_arbor.connected


def test_cant_reconnect(local_arbor):
    with pytest.raises(arbor.Conflict, match="already connected"):
        local_arbor.init()


def test_second_connection(local_arbor):
    reopened = arbor.LocalArbor(local_arbor.path)
    assert reopened.connect() is reopened
    assert reopened.connected


def test_lifecycle_round_trip_and_revision_history(local_arbor, source, tmp_path):
    # can make a grove
    grove = local_arbor.create_grove("mygrove")
    assert local_arbor.list_grove_ids() == ["mygrove"]

    # can make an asset
    asset = local_arbor.create_asset("mygrove", "myasset")
    assert grove.list_asset_ids() == ["myasset"]

    # can upload
    assert asset.upload(source) == 0
    assert set(asset.paths()) == {"books/moby.txt", "metadata.json"}

    # can amend
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    (replacement / "books").mkdir()
    (replacement / "books" / "moby.txt").write_text("Call me Michael")
    assert asset.amend(replacement) == 0
    assert asset.list_rev_ids() == [0]
    assert asset.paths() == ["books/moby.txt"]

    # can download
    destination = tmp_path / "download"
    assert asset.save(destination) == destination.resolve()
    assert (destination / "books" / "moby.txt").read_text() == "Call me Michael"
    with pytest.raises(arbor.Conflict):
        asset.save(destination)

    # can burn
    asset.burn(0)
    assert asset.list_rev_ids() == []
    with pytest.raises(arbor.NotFound):
        asset.paths()

    # new asset should skip to the next numbers
    assert asset.upload(source) == 1


def test_rename_grove(local_arbor, source):
    grove = local_arbor.create_grove("elms")
    asset = grove.create_asset("stuff")
    asset.upload(source)
    grove.rename("ashes")

    assert (local_arbor.path / "ashes").exists()
    assert (local_arbor.path / "ashes" / "stuff" / "0").exists()


def test_rename_asset(local_arbor, source):
    local_arbor.create_grove("old")
    asset = local_arbor.create_asset("old", "first")
    asset.upload(source)
    local_arbor.rename_asset("old", "first", "second")
    local_arbor.rename_grove("old", "new")

    reopened = arbor.LocalArbor(local_arbor.path).connect()
    assert reopened.list_grove_ids() == ["new"]
    assert reopened.list_asset_ids("new") == ["second"]
    assert reopened.paths("new", "second") == ["books/moby.txt", "metadata.json"]
    with pytest.raises(arbor.NotFound):
        reopened.list_asset_ids("old")


def test_invalid_sources_and_ids(local_arbor, tmp_path):
    local_arbor.create_grove("mygrove")
    for value in ("", ".hidden", "has space", "x" * 81):
        with pytest.raises(arbor.Invalid):
            local_arbor.create_grove(value)

    asset = local_arbor.create_asset("mygrove", "myasset")
    empty = tmp_path / "empty"
    empty.mkdir()
    assert asset.upload(empty) == 0
    with pytest.raises(arbor.Invalid, match="empty"):
        asset.paths()


def test_manifest_validation_is_recursive(local_arbor, source):
    local_arbor.create_grove("g")
    asset = local_arbor.create_asset("g", "a")
    asset.upload(source)
    asset.arbor._asset_manifest_path("g", "a").write_text('{"schema_version":99}\n')
    with pytest.raises(arbor.Invalid):
        local_arbor.validate()


def test_manifest_and_event_shapes(local_arbor, source):
    grove = local_arbor.create_grove("g")
    asset = local_arbor.create_asset("g", "a")
    asset.upload(source)
    for path in (
        local_arbor.path / "manifest.json",
        grove.arbor._grove_path("g") / "manifest.json",
        asset.arbor._asset_manifest_path("g", "a"),
    ):
        assert json.loads(path.read_text()) == {"schema_version": 1}
    assert set(local_arbor.log()[0]) == {"event", "grove_id", "created_at"}
    assert set(grove.log()[0]) == {"event", "asset_id", "created_at"}
    assert set(asset.log()[0]) == {"event", "revision", "uploaded_at"}


def test_cli_lifecycle(tmp_path, capsys, monkeypatch):
    config = tmp_path / "arbor.toml"
    config.write_text('[backend]\ntype = "local"\npath = "cli-arbor"\n')
    monkeypatch.chdir(tmp_path)

    assert run(["init"]) == 0
    assert run(["create-grove", "g"]) == 0
    assert run(["list-groves"]) == 0
    assert capsys.readouterr().out == "g\n"
