from __future__ import annotations

import datetime as dt
import json
import os
import re
import uuid
from abc import ABC
from os import PathLike
from pathlib import Path
from typing import Any, Self

import fsspec
from fsspec.implementations.dirfs import DirFileSystem
from fsspec.implementations.local import LocalFileSystem

import arbor.config
from arbor.types import ArborError, AssetID, AssetMode, VersionID


class Grove(ABC):
    schema_version = 1

    def __init__(self, root: str, fs: fsspec.AbstractFileSystem):
        self.root = root
        self.fs = fs
        self.dfs = DirFileSystem(path=root, fs=fs)

    def _join(self, parts: list[str]) -> str:
        return self.dfs.sep.join(parts)

    @classmethod
    def from_config(cls, path: PathLike | None = None) -> Self:
        root, fs = arbor.config.from_config(path)
        return cls(root=root, fs=fs)

    def setup(self) -> Self:
        if self.dfs.exists(""):
            raise ArborError("grove root exists")

        try:
            self.dfs.mkdir("")
            manifest = {"schema_version": self.schema_version}
            self._write_json(path="manifest.json", value=manifest)
            self.dfs.mkdir("assets")
            self.dfs.touch("log.jsonl")
            self._log_event({"event": "create_grove"})
            return self
        except BaseException:
            self.dfs.rm("", recursive=True)
            raise

    def _read_json(self, path: str) -> Any:
        return json.loads(self.dfs.read_text(path, encoding="utf-8"))

    def _write_json(self, path: str, value):
        self.dfs.write_text(path=path, value=json.dumps(value) + "\n", encoding="utf-8")

    def validate(self) -> None:
        """Recursively validate the grove"""
        # read the grove-level manifest
        manifest = self._read_json("manifest.json")
        if not manifest["schema_version"] == self.schema_version:
            raise ArborError("Grove schemas do not match")

        # validate each asset
        for asset_id in self.list_assets():
            self.validate_asset(asset_id)

    def read_log(self) -> list[dict[str, Any]]:
        return _parse_jsonl(self.dfs.read_text("log.jsonl"))

    def list_assets(self) -> list[AssetID]:
        _, dirs, _ = next(self.dfs.walk("assets"))
        return dirs

    def create_asset(self, asset_id: AssetID) -> Asset:
        self._validate_id(asset_id)
        asset_path = self._join(["assets", asset_id])
        if self.dfs.exists(asset_path):
            raise ArborError(f"asset {asset_id} already exists")

        self.dfs.mkdir(asset_path)

        manifest = dict()
        self._write_json(path=self._join([asset_path, "manifest.json"]), value=manifest)
        self.dfs.mkdir(self._join([asset_path, "versions"]))
        self._log_event({"event": "create_asset", "asset_id": asset_id})

        return Asset(grove=self, asset_id=asset_id)

    @staticmethod
    def _validate_id(x: str) -> None:
        if not re.match(r"^[\w-]+$", x):
            raise ArborError(f"Invalid ID {x}")

    def rename_asset(self, asset_id: AssetID, new_id: AssetID) -> Asset:
        if not isinstance(self.fs, LocalFileSystem):
            raise NotImplementedError(
                "asset renaming only supported for local filesystem"
            )

        self._require_asset(asset_id)
        self._validate_id(new_id)

        old_path = self._join(["assets", asset_id])
        new_path = self._join(["assets", new_id])
        if self.dfs.exists(new_path):
            raise ArborError(f"asset {new_id} already exists")

        self.dfs.mv(old_path, new_path)
        self._log_event(
            {"event": "rename_asset", "asset_id": asset_id, "new_id": new_id}
        )

        return self.asset(new_id)

    def _require_asset(self, asset_id: AssetID) -> None:
        if not self.dfs.exists(self._join(["assets", asset_id])):
            raise ArborError(f"asset {asset_id} does not exist")

    def _require_version(self, asset_id: AssetID, version: VersionID) -> None:
        path = self._join(["assets", asset_id, "versions", version])
        if not self.dfs.exists(path):
            raise ArborError(f"version {asset_id}/{version} does not exist")

    def asset(self, asset_id: AssetID) -> Asset:
        return Asset(grove=self, asset_id=asset_id)

    def validate_asset(self, asset_id: AssetID) -> None:
        self._require_asset(asset_id)
        versions = self.list_versions(asset_id)
        latest_version = self.latest_version(asset_id)

        if latest_version is not None:
            self._require_version(asset_id, latest_version)

        for version in versions:
            self.validate_version(asset_id, version)

    def validate_version(self, asset_id: AssetID, version: VersionID) -> None:
        self._require_version(asset_id, version)
        manifest = self._read_manifest(asset_id, version)
        mode = manifest["mode"]

        if mode == "file":
            data = self.list_data(asset_id, version)

            if len(data) != 1:
                # there is only one file
                raise ArborError(
                    f"{asset_id}/{version} is mode {mode} but has {len(data)} != 1 files/dirs"
                )
        elif mode == "dir":
            # a directory if always fine
            pass
        else:
            raise RuntimeError(f"bad mode {mode}")

    def _read_manifest(self, asset_id: AssetID, version: VersionID) -> dict[str, Any]:
        self._require_version(asset_id, version)
        manifest_path = self._join(
            ["assets", asset_id, "versions", version, "manifest.json"]
        )
        manifest = json.loads(self.dfs.read_text(manifest_path))

        keys = set(manifest.keys())
        if not keys == {"mode", "metadata"}:
            raise ArborError(
                f"Malformed manifest {asset_id}/{version} with keys {keys}"
            )

        return manifest

    def _resolve_version(
        self, asset_id: AssetID, version: VersionID | None
    ) -> VersionID:
        if version is None:
            version = self._latest_version_required(asset_id)

        self._require_version(asset_id, version)
        return version

    def list_data(self, asset_id: AssetID, version: VersionID | None) -> list[str]:
        version = self._resolve_version(asset_id, version)
        data_path = self._join(["assets", asset_id, "versions", version, "data"])
        paths = [fn for _, _, fns in self.dfs.walk(data_path) for fn in fns]

        if not len(paths) == 1:
            raise NotImplementedError("only single-file assets are supported")

        return paths

    def list_versions(self, asset_id: AssetID) -> list[VersionID]:
        self._require_asset(asset_id)
        _, dir_names, _ = next(
            self.dfs.walk(self._join(["assets", asset_id, "versions"]))
        )
        return dir_names

    def latest_version(self, asset_id: AssetID) -> VersionID | None:
        self._require_asset(asset_id)
        manifest_path = self._join(["assets", asset_id, "manifest.json"])
        manifest = self._read_json(manifest_path)
        return manifest["latest_version"]

    def _latest_version_required(self, asset_id: AssetID) -> VersionID:
        v = self.latest_version(asset_id)
        if v is not None:
            return v
        else:
            raise ArborError(f"{asset_id} has no latest version")

    def upload(
        self,
        asset_id: AssetID,
        source: PathLike,
        metadata: dict[str, Any] | None = None,
    ) -> VersionID:
        self._require_asset(asset_id)
        source = Path(source)

        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise ArborError("metadata must be a dictionary")

        # determine new version
        version = str(uuid.uuid4())[:6]

        # determine new mode
        if source.exists() and source.is_file():
            mode = "file"
            recursive = False
        elif source.exists() and source.is_dir():
            mode = "dir"
            raise NotImplementedError("directory upload not implemented")
        else:
            raise ArborError(f"cannot upload {source}")

        # set up paths
        asset_path = self._join(["assets", asset_id])
        asset_manifest_path = self._join([asset_path, "manifest.json"])
        version_path = self._join([asset_path, "versions", version])
        version_manifest_path = self._join([version_path, "manifest.json"])
        data_path = self._join([version_path, "data"])

        # set up manifest contents
        asset_manifest = {"latest_version": version}
        version_manifest = {"mode": mode, "metadata": metadata}

        try:
            self.dfs.mkdir(version_path)
            self.dfs.mkdir(data_path)
            self.dfs.put(source, data_path, recursive=recursive)

            self._write_json(path=asset_manifest_path, value=asset_manifest)
            self._write_json(path=version_manifest_path, value=version_manifest)
            self._log_event({"event": "upload", "asset": asset_id, "version": version})
        except BaseException:
            self.dfs.rm(version_path, recursive=True)
            raise

        return version

    def asset_metadata(
        self, asset_id: AssetID, version: VersionID | None = None
    ) -> dict[str, Any]:
        """Return metadata stored on a version manifest."""
        version = self._resolve_version(asset_id, version)
        manifest = self._read_manifest(asset_id, version)
        return manifest["metadata"]

    def _log_event(self, event: dict[str, Any]):
        time = (
            dt.datetime.now(dt.timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        event |= {"time": time}
        line = json.dumps(event) + "\n"

        path = "log.jsonl"
        log = self.dfs.read_text(path) + line
        self.dfs.write_text(path=path, value=log)

    def asset_mode(
        self,
        asset_id: AssetID,
        version: VersionID | None = None,
    ) -> AssetMode:
        self._require_asset(asset_id)
        version = self._resolve_version(asset_id, version)

        manifest_path = self._join(
            ["assets", asset_id, "versions", version, "manifest.json"]
        )

        manifest = json.loads(self.dfs.read_text(manifest_path))
        return manifest["mode"]

    def download(
        self,
        asset_id: AssetID,
        dest: os.PathLike[str],
        version: VersionID | None = None,
    ) -> None:
        mode = self.asset_mode(asset_id, version)
        dest = Path(dest)

        if version is None:
            version = self._latest_version_required(asset_id)

        if mode == "file":
            data = self.list_data(asset_id, version)
            if not len(data) == 1:
                raise ArborError(
                    f"Asset {asset_id}/{version} is file mode but has more than 1 file"
                )

            source = self._join(
                ["assets", asset_id, "versions", version, "data", data[0]]
            )
            recursive = False
        elif mode == "dir":
            source = self._join(["assets", asset_id, "versions", version, "data"])
            recursive = True
            raise NotImplementedError("directory downloads not implemented")
        else:
            raise ValueError(f"Invalid mode {mode}")

        self.dfs.get(source, str(dest), recursive=recursive)


class Asset:
    schema_version = 1

    def __init__(self, grove: Grove, asset_id: AssetID):
        self.grove = grove
        self.asset_id = asset_id

    def rename(self, new_id: AssetID) -> None:
        self.grove.rename_asset(asset_id=self.asset_id, new_id=new_id)

    def validate(self) -> None:
        self.grove.validate_asset(asset_id=self.asset_id)

    def list_versions(self) -> list[VersionID]:
        return self.grove.list_versions(asset_id=self.asset_id)

    def list_data(self, version: VersionID | None = None) -> list[str]:
        return self.grove.list_data(self.asset_id, version)

    def latest_version(self) -> VersionID | None:
        return self.grove.latest_version(asset_id=self.asset_id)

    def upload(
        self, source: os.PathLike[str], metadata: dict[str, Any] | None = None
    ) -> VersionID:
        return self.grove.upload(
            asset_id=self.asset_id, source=source, metadata=metadata
        )

    def metadata(self, version: VersionID | None = None) -> dict[str, Any]:
        return self.grove.asset_metadata(asset_id=self.asset_id, version=version)

    def mode(self, version: VersionID | None = None) -> Any:
        return self.grove.asset_mode(asset_id=self.asset_id, version=version)

    def download(
        self, dest: os.PathLike[str], version: VersionID | None = None
    ) -> None:
        self.grove.download(asset_id=self.asset_id, dest=dest, version=version)


def _parse_jsonl(x: str) -> list[Any]:
    return [json.loads(line) for line in x.splitlines()]
