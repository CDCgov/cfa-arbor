import datetime as dt
import json
import os
import shutil
from pathlib import Path
from typing import Any, Self

from .core import (
    Arbor,
    Asset,
    AssetID,
    Conflict,
    Grove,
    GroveID,
    Invalid,
    NotFound,
    RevisionID,
    _as_rev_id,
    _validated_id,
)


def _time() -> str:
    """Canonical string representation of 'now'"""
    return (
        dt.datetime.now(dt.timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> Any:
    with open(path) as f:
        values = [json.loads(line) for line in f]

    return values


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _check_manifest(path: Path, schema_version: int) -> None:
    """Ensure the manifest is what we expect"""
    try:
        value = _read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Invalid(f"invalid manifest: {path}") from error

    if not ("schema_version" in value and value["schema_version"] == schema_version):
        raise Invalid(f"unsupported or malformed manifest: {path}")


def _append_jsonl(path: Path, value: Any) -> None:
    """Append a line to a JSON Lines file, recovering if possible"""
    old_size = path.stat().st_size
    try:
        with path.open("ab") as stream:
            stream.write(json.dumps(value).encode() + b"\n")
            stream.flush()
    except BaseException:
        with path.open("r+b") as stream:
            stream.truncate(old_size)
        raise


class LocalArbor(Arbor):
    def __init__(self, path: os.PathLike[str]):
        self.path = Path(os.path.abspath(path))
        self._connected = False
        self._manifest_path = self.path / "manifest.json"
        self._log_path = self.path / "log.jsonl"

    def __repr__(self) -> str:
        return f'LocalArbor("{self.path!s}")'

    @property
    def connected(self) -> bool:
        return self._connected

    def _require_connected(self) -> None:
        if not self.connected:
            raise Conflict("arbor is not connected; call init() or connect()")

    def connect(self) -> Self:
        if self.connected:
            return self
        elif not self.path.is_dir():
            raise Invalid(f"local arbor path is not a directory: {self.path}")
        else:
            _check_manifest(self._manifest_path, self.schema_version)
            self._connected = True
            return self

    def init(self) -> Self:
        if self.connected:
            raise Conflict("arbor is already connected")

        if self.path.exists() and (not self.path.is_dir() or any(self.path.iterdir())):
            raise Conflict(f"local arbor directory is not empty: {self.path}")

        # try to set up; if we fail, delete everything we did
        self.path.mkdir(parents=True, exist_ok=True)
        try:
            self._write_manifest(self._manifest_path)
            self._log_path.touch()
        except BaseException:
            for path in (self._log_path, self._manifest_path):
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
            raise

        self._connected = True
        return self

    def _write_manifest(self, path: Path):
        _write_json(path, {"schema_version": self.schema_version})

    def list_grove_ids(self) -> list[GroveID]:
        self._require_connected()
        dirs = [x for x in self.path.iterdir() if x.is_dir()]
        return [_validated_id(x.name) for x in dirs]

    def create_grove(self, grove_id: GroveID) -> Grove:
        self._require_connected()
        grove_id = _validated_id(grove_id)

        if self._grove_path(grove_id).exists():
            raise Conflict(f"grove already exists: {grove_id}")

        grove_path = self._grove_path(grove_id)
        try:
            # create grove, grove manifest, grove log
            grove_path.mkdir()
            self._write_manifest(self._grove_manifest_path(grove_id))
            self._grove_log_path(grove_id).touch()
            # log grove creation in arbor's log
            _append_jsonl(
                self._log_path,
                {"event": "created", "grove_id": grove_id, "created_at": _time()},
            )
        except BaseException:
            shutil.rmtree(grove_path, ignore_errors=True)
            raise

        return Grove(self, _validated_id(grove_id))

    def _grove_path(self, grove_id: GroveID) -> Path:
        return self.path / grove_id

    def _grove_log_path(self, grove_id: GroveID) -> Path:
        return self._grove_path(grove_id) / "log.jsonl"

    def rename_grove(self, grove_id: GroveID, new_id: GroveID) -> None:
        self._require_grove(grove_id)
        new_id = _validated_id(new_id)

        old_grove_path = self._grove_path(grove_id)
        new_grove_path = self._grove_path(new_id)

        if new_grove_path.exists():
            raise Conflict(f"grove already exists: {new_id}")

        old_grove_path.rename(new_grove_path)
        _append_jsonl(
            self._log_path,
            {
                "event": "renamed",
                "old_grove_id": grove_id,
                "grove_id": new_id,
                "renamed_at": _time(),
            },
        )

    def _require_grove(self, grove_id: GroveID) -> None:
        self._require_connected()
        grove_path = self._grove_path(grove_id)
        if not grove_path.is_dir():
            raise NotFound(f"grove not found: {grove_id}")
        _check_manifest(self._grove_manifest_path(grove_id), self.schema_version)

    def _grove_manifest_path(self, grove_id: GroveID) -> Path:
        return self.path / grove_id / "manifest.json"

    def list_asset_ids(self, grove_id: GroveID) -> list[AssetID]:
        self._require_grove(grove_id)
        dirs = [x for x in self._grove_path(grove_id).iterdir() if x.is_dir()]
        return sorted([_validated_id(x.name) for x in dirs])

    def grove_log(self, grove_id: GroveID) -> list[dict[str, Any]]:
        self._require_grove(grove_id)
        path = self._grove_log_path(grove_id)
        return _read_jsonl(path)

    def asset_log(self, grove_id: GroveID, asset_id: AssetID) -> list[dict[str, Any]]:
        self._require_asset(grove_id, asset_id)
        path = self._asset_log_path(grove_id, asset_id)
        return _read_jsonl(path)

    def validate_grove(self, grove_id: GroveID) -> None:
        self._require_grove(grove_id)
        self.grove_log(grove_id)
        for asset_id in self.list_asset_ids(grove_id):
            self.validate_asset(grove_id, asset_id)

    def _asset_path(self, grove_id: GroveID, asset_id: AssetID) -> Path:
        return self._grove_path(grove_id) / asset_id

    def _asset_log_path(self, grove_id: GroveID, asset_id: AssetID) -> Path:
        return self._asset_path(grove_id, asset_id) / "log.jsonl"

    def _require_asset(self, grove_id: GroveID, asset_id: AssetID) -> None:
        self._require_grove(grove_id)
        path = self._asset_path(grove_id, asset_id)
        if not path.is_dir():
            raise NotFound(f"asset not found: {grove_id}/{asset_id}")
        _check_manifest(
            self._asset_manifest_path(grove_id, asset_id), self.schema_version
        )

    def list_rev_ids(self, grove_id: GroveID, asset_id: AssetID) -> list[RevisionID]:
        self._require_asset(grove_id, asset_id)
        dirs = [x for x in self._asset_path(grove_id, asset_id).iterdir() if x.is_dir()]
        return sorted([_as_rev_id(x.name) for x in dirs])

    def latest_rev_id(self, grove_id: GroveID, asset_id: AssetID) -> RevisionID:
        existing = self.list_rev_ids(grove_id, asset_id)
        if not existing:
            raise NotFound(f"asset has no revisions: {grove_id}/{asset_id}")
        return existing[-1]

    def next_rev_id(self, grove_id: GroveID, asset_id: AssetID) -> RevisionID:
        """Get next revision ID, accounting for burned revisions"""
        revs = self.list_rev_ids(grove_id, asset_id)
        log_path = self._asset_log_path(grove_id, asset_id)
        log = _read_jsonl(log_path)

        revs.extend(
            event["revision"] for event in log if event.get("event") == "uploaded"
        )

        if not revs:
            rev_id = 0
        else:
            rev_id = max(revs) + 1

        if self._rev_path(grove_id, asset_id, rev_id).exists():
            raise RuntimeError(
                f"revision {grove_id}/{asset_id}/{rev_id} already exists"
            )

        return rev_id

    def _rev_path(
        self, grove_id: GroveID, asset_id: AssetID, rev_id: RevisionID
    ) -> Path:
        return self._asset_path(grove_id, asset_id) / str(rev_id)

    def _asset_manifest_path(self, grove_id: GroveID, asset_id: AssetID) -> Path:
        return self._asset_path(grove_id, asset_id) / "manifest.json"

    def create_asset(self, grove_id: GroveID, asset_id: AssetID) -> Asset:
        self._require_grove(grove_id)
        asset_id = _validated_id(asset_id)
        asset_path = self._asset_path(grove_id, asset_id)

        if asset_path.exists():
            raise Conflict(f"asset already exists: {asset_id}")

        try:
            asset_path.mkdir()
            self._write_manifest(self._asset_manifest_path(grove_id, asset_id))
            self._asset_log_path(grove_id, asset_id).touch()

            _append_jsonl(
                self._grove_log_path(grove_id),
                {"event": "created", "asset_id": asset_id, "created_at": _time()},
            )
        except BaseException:
            shutil.rmtree(asset_path, ignore_errors=True)
            raise

        return Asset(arbor=self, grove_id=grove_id, asset_id=asset_id)

    def upload(
        self, grove_id: GroveID, asset_id: AssetID, source: os.PathLike[str]
    ) -> RevisionID:
        source = Path(source)
        self._require_asset(grove_id, asset_id)
        rev_id = self.next_rev_id(grove_id, asset_id)

        try:
            target = self._rev_path(grove_id, asset_id, rev_id)
            shutil.copytree(source, target)
            _append_jsonl(
                self._asset_log_path(grove_id, asset_id),
                {"event": "uploaded", "revision": rev_id, "uploaded_at": _time()},
            )

        except BaseException:
            shutil.rmtree(target, ignore_errors=True)
            raise

        return rev_id

    def _require_rev(
        self, grove_id: GroveID, asset_id: AssetID, rev_id: RevisionID
    ) -> None:
        self._require_asset(grove_id, asset_id)
        path = self._rev_path(grove_id, asset_id, rev_id)
        if not path.exists():
            raise NotFound(f"revision not found: {grove_id}/{asset_id}/{rev_id}")

    def paths(
        self, grove_id: GroveID, asset_id: AssetID, rev_id: RevisionID | None = None
    ) -> list[str]:
        self._require_asset(grove_id, asset_id)
        if rev_id is None:
            rev_id = self.latest_rev_id(grove_id, asset_id)

        self._require_rev(grove_id, asset_id, rev_id)

        root = self._rev_path(grove_id, asset_id, rev_id)
        paths = []
        for current, dirs, files in os.walk(root):
            base = Path(current)
            for name in dirs + files:
                path = base / name
                if path.is_symlink():
                    raise Invalid(f"symbolic link in stored revision: {path}")
            for name in files:
                path = base / name
                if not path.is_file():
                    raise Invalid(f"special file in stored revision: {path}")
                paths.append(path.relative_to(root).as_posix())
        if not paths:
            raise Invalid(f"empty stored revision: {root}")
        return sorted(paths)

    def save(
        self,
        grove_id: GroveID,
        asset_id: AssetID,
        destination: os.PathLike[str],
        rev_id: RevisionID | None = None,
    ) -> Path:
        self._require_asset(grove_id, asset_id)
        if rev_id is None:
            rev_id = self.latest_rev_id(grove_id, asset_id)

        source = self._rev_path(grove_id, asset_id, rev_id)

        destination = Path(destination).resolve()
        if os.path.lexists(destination):
            raise Conflict(f"download destination exists: {destination}")

        try:
            shutil.copytree(source, destination)
        except BaseException:
            shutil.rmtree(destination, ignore_errors=True)
            raise

        return destination

    def amend(
        self,
        grove_id: GroveID,
        asset_id: AssetID,
        source: os.PathLike[str],
        rev_id: RevisionID | None = None,
    ) -> int:
        if rev_id is None:
            rev_id = self.latest_rev_id(grove_id, asset_id)

        self._require_rev(grove_id, asset_id, rev_id)
        source = Path(source)
        target = self._rev_path(grove_id, asset_id, rev_id)

        temp_dir = target.parent / f".{rev_id}-backup"
        try:
            # rename old revision as temp directory
            target.rename(temp_dir)
            # copy in the new data
            shutil.copytree(source, target)
            # remove the temporary data
            shutil.rmtree(temp_dir)

            _append_jsonl(
                self._asset_log_path(grove_id, asset_id),
                {"event": "amended", "revision": rev_id, "amended_at": _time()},
            )

            shutil.rmtree(temp_dir, ignore_errors=True)
        except BaseException:
            if target.exists():
                shutil.rmtree(target)
            if temp_dir.exists():
                temp_dir.rename(target)
            raise

        return rev_id

    def burn(self, grove_id: GroveID, asset_id: AssetID, rev_id: RevisionID) -> None:

        self._require_rev(grove_id, asset_id, rev_id)
        target = self._rev_path(grove_id, asset_id, rev_id)
        shutil.rmtree(target)
        _append_jsonl(
            self._asset_log_path(grove_id, asset_id),
            {"event": "destroyed", "revision": rev_id, "destroyed_at": _time()},
        )

    def rename_asset(
        self, grove_id: GroveID, asset_id: AssetID, new_id: AssetID
    ) -> None:
        self._require_asset(grove_id, asset_id)
        new_id = _validated_id(new_id)
        old_path = self._asset_path(grove_id, asset_id)
        new_path = self._asset_path(grove_id, new_id)

        if new_path.exists():
            raise Conflict(f"asset already exists: {new_id}")

        try:
            old_path.rename(new_path)
            _append_jsonl(
                self._grove_log_path(grove_id),
                {
                    "event": "renamed",
                    "old_asset_id": asset_id,
                    "asset_id": new_id,
                    "renamed_at": _time(),
                },
            )
        except BaseException:
            if new_path.exists() and not old_path.exists():
                new_path.rename(old_path)
            raise

    def validate_asset(self, grove_id: GroveID, asset_id: AssetID) -> None:
        self._require_asset(grove_id, asset_id)
        self.asset_log(grove_id, asset_id)

    def log(self) -> list[dict[str, Any]]:
        self._require_connected()
        return _read_jsonl(self._log_path)

    def validate(self) -> None:
        self._require_connected()
        _check_manifest(self._manifest_path, self.schema_version)
        self.log()
        for grove_id in self.list_grove_ids():
            self.validate_grove(grove_id)
