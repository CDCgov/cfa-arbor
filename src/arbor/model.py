from __future__ import annotations

import datetime as dt
import json
import os
import re
import uuid
from abc import ABC
from pathlib import Path, PurePath
from typing import Any, Self

from .backend import Backend, from_config
from .types import ArborError, AssetID, AssetMode, VersionID


class Grove(ABC):
    schema_version = 1

    def __init__(self, backend: Backend):
        self.backend = backend
        self.connected = False

    @classmethod
    def from_config(cls, path: str | Path | None = None) -> Self:
        return cls(from_config(path))

    def connect(self) -> Self:
        if self.connected:
            raise ArborError("already connected")

        self.backend.connect()
        self.connected = True
        return self

    def setup(self) -> Self:
        if self.connected:
            raise ArborError("already connected")

        path = PurePath(".")
        if self.backend.exists(path):
            raise ArborError("backend destination exists")

        try:
            self.backend.mkdir(path)
            manifest = {"schema_version": self.schema_version}
            self.backend.write_text(json.dumps(manifest) + "\n", path / "manifest.json")
            self.backend.mkdir(path / "assets")
            self.backend.touch(path / "log.jsonl")
            self._log_event({"event": "create_grove"})
            return self.connect()
        except BaseException:
            self.backend.rm(path)
            raise

    def _require_connected(self):
        if not self.connected:
            raise ArborError("grove not connected; call .connect()")

    def validate(self) -> None:
        """Recursively validate the grove"""
        self._require_connected()
        # read the grove-level manifest
        path = PurePath("manifest.json")
        manifest = json.loads(self.backend.read_text(path))
        if not manifest["schema_version"] == self.schema_version:
            raise ArborError("Grove schemas do not match")

        # validate each asset
        for asset_id in self.list_assets():
            self.validate_asset(asset_id)

    def read_log(self) -> list[dict[str, Any]]:
        self._require_connected()
        path = PurePath("log.jsonl")
        return _parse_jsonl(self.backend.read_text(path))

    def list_assets(self) -> list[AssetID]:
        self._require_connected()
        dirs, _ = self.backend.scan(PurePath("assets"))
        return dirs

    def create_asset(self, asset_id: AssetID) -> Asset:
        self._require_connected()
        self._validate_id(asset_id)
        asset_path = PurePath("assets", asset_id)
        if self.backend.exists(asset_path):
            raise ArborError(f"asset {asset_id} already exists")

        self.backend.mkdir(asset_path)

        manifest = dict()
        manifest_path = asset_path / "manifest.json"
        self.backend.write_text(json.dumps(manifest) + "\n", manifest_path)
        self.backend.mkdir(asset_path / "versions")
        self._log_event({"event": "create_asset", "asset_id": asset_id})

        return Asset(grove=self, asset_id=asset_id)

    @staticmethod
    def _validate_id(x: str) -> None:
        if not re.match(r"^[\w-]+$", x):
            raise ArborError(f"Invalid ID {x}")

    def rename_asset(self, asset_id: AssetID, new_id: AssetID) -> Asset:
        self._require_asset(asset_id)
        self._validate_id(new_id)

        old_path = PurePath("assets", asset_id)
        new_path = PurePath("assets", new_id)
        if self.backend.exists(new_path):
            raise ArborError(f"asset {new_id} already exists")

        self.backend.move(old_path, new_path)
        self._log_event(
            {"event": "rename_asset", "asset_id": asset_id, "new_id": new_id}
        )

        return self.asset(new_id)

    def _require_asset(self, asset_id: AssetID) -> None:
        self._require_connected()
        if not self.backend.exists(PurePath("assets", asset_id)):
            raise ArborError(f"asset {asset_id} does not exist")

    def _require_version(self, asset_id: AssetID, version: VersionID) -> None:
        self._require_connected()
        path = PurePath("assets", asset_id, "versions", version)
        if not self.backend.exists(path):
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
        version_path = PurePath("assets", asset_id, "versions", version)
        manifest = json.loads(self.backend.read_text(version_path / "manifest.json"))
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

    def _resolve_version(
        self, asset_id: AssetID, version: VersionID | None
    ) -> VersionID:
        if version is None:
            version = self._latest_version_required(asset_id)

        self._require_version(asset_id, version)
        return version

    def list_data(self, asset_id: AssetID, version: VersionID | None) -> list[PurePath]:
        version = self._resolve_version(asset_id, version)
        dirs, files = self._scan_recursive(
            PurePath("assets", asset_id, "versions", version, "data")
        )
        return dirs + files

    def _scan_recursive(
        self, path: PurePath, root: PurePath | None = None
    ) -> tuple[list[PurePath], list[PurePath]]:
        if root is None:
            root = path

        dirs, files = self.backend.scan(path)
        dirs = [path / dir for dir in dirs]
        files = [path / file for file in files]

        for dir in dirs:
            subdirs, subfiles = self._scan_recursive(path / dir, root=root)
            dirs += subdirs
            files += subfiles

        return (
            [dir.relative_to(root) for dir in dirs],
            [file.relative_to(root) for file in files],
        )

    def list_versions(self, asset_id: AssetID) -> list[VersionID]:
        self._require_asset(asset_id)
        dirs, _ = self.backend.scan(PurePath("assets", asset_id, "versions"))
        return dirs

    def latest_version(self, asset_id: AssetID) -> VersionID | None:
        self._require_asset(asset_id)
        manifest_path = PurePath("assets", asset_id, "manifest.json")
        manifest = json.loads(self.backend.read_text(manifest_path))
        return manifest["latest_version"]

    def _latest_version_required(self, asset_id: AssetID) -> VersionID:
        v = self.latest_version(asset_id)
        if v is not None:
            return v
        else:
            raise ArborError(f"{asset_id} has no latest version")

    def upload(self, asset_id: AssetID, source: os.PathLike[str]) -> VersionID:
        self._require_asset(asset_id)
        source = Path(source)

        # determine new version
        version = str(uuid.uuid4())[:6]

        # determine new mode
        if source.exists() and source.is_file():
            mode = "file"
        elif source.exists() and source.is_dir():
            mode = "dir"
        else:
            raise ArborError(f"cannot upload {source}")

        # set up paths
        asset_path = PurePath("assets", asset_id)
        asset_manifest_path = asset_path / "manifest.json"
        version_path = asset_path / "versions" / version
        version_manifest_path = version_path / "manifest.json"
        data_path = version_path / "data"

        # set up manifest contents
        asset_manifest = {"latest_version": version}
        version_manifest = {"mode": mode}

        try:
            self.backend.mkdir(version_path)
            self.backend.mkdir(data_path)

            if mode == "file":
                self.backend.upload_file(source, data_path / source.name)
            elif mode == "dir":
                raise NotImplementedError("Directory uploads not yet supported")
            else:
                raise RuntimeError(f"invalid mode {mode}")

            self.backend.write_text(
                json.dumps(asset_manifest) + "\n", asset_manifest_path
            )
            self.backend.write_text(
                json.dumps(version_manifest) + "\n", version_manifest_path
            )

            self._log_event({"event": "upload", "asset": asset_id, "version": version})
        except BaseException:
            self.backend.rm(version_path)
            raise

        return version

    def _log_event(self, event: dict[str, Any]):
        time = (
            dt.datetime.now(dt.timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        event |= {"time": time}
        line = json.dumps(event) + "\n"
        self.backend.append(line, PurePath("log.jsonl"))

    def asset_mode(
        self,
        asset_id: AssetID,
        version: VersionID | None = None,
    ) -> AssetMode:
        self._require_asset(asset_id)
        version = self._resolve_version(asset_id, version)

        manifest_path = PurePath(
            "assets", asset_id, "versions", version, "manifest.json"
        )
        manifest = json.loads(self.backend.read_text(manifest_path))
        return manifest["mode"]

    def download(
        self,
        asset_id: AssetID,
        dest: os.PathLike[str],
        version: VersionID | None = None,
    ) -> Path:
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

            source = PurePath("assets", asset_id, "versions", version, "data", data[0])

            if not dest.exists():
                # download a file to the specified file destination
                self.backend.download_file(source, dest)
                return dest
            elif dest.exists() and dest.is_dir():
                dest_fp = dest / data[0]
                self.backend.download_file(source, dest_fp)
                return dest_fp
            elif dest.exists() and not dest.is_dir():
                raise ArborError(f"destination {dest} already exists")
            else:
                raise RuntimeError()
        elif mode == "dir":
            raise NotImplementedError("Directory downloads not yet supported")
        else:
            raise RuntimeError(f"invalid mode {mode}")


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

    def list_data(self, version: VersionID | None = None) -> list[PurePath]:
        return self.grove.list_data(self.asset_id, version)

    def latest_version(self) -> VersionID | None:
        return self.grove.latest_version(asset_id=self.asset_id)

    def upload(self, source: os.PathLike[str]) -> VersionID:
        return self.grove.upload(asset_id=self.asset_id, source=source)

    def mode(self, version: VersionID | None = None) -> Any:
        return self.grove.asset_mode(asset_id=self.asset_id, version=version)

    def download(
        self, dest: os.PathLike[str], version: VersionID | None = None
    ) -> Path:
        return self.grove.download(asset_id=self.asset_id, dest=dest, version=version)


def _parse_jsonl(x: str) -> list[Any]:
    return [json.loads(line) for line in x.splitlines()]
