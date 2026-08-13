from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Self

ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")

type GroveID = str
type AssetID = str
type RevisionID = int


class ArborError(Exception):
    """Base class for expected Arbor failures."""


class Invalid(ArborError):
    pass


class NotFound(ArborError):
    pass


class Conflict(ArborError):
    pass


class Arbor(ABC):
    schema_version = 1

    @classmethod
    def from_config(cls, path: str | Path | None = None) -> Arbor:
        from .config import from_config

        return from_config(path)

    @property
    @abstractmethod
    def connected(self) -> bool:
        """Is this Arbor connected to its backend?"""
        ...

    @abstractmethod
    def init(self) -> Self:
        """Instantiate a new backend"""
        ...

    @abstractmethod
    def connect(self) -> Self:
        """Connect to the backend"""
        ...

    @abstractmethod
    def validate(self) -> None:
        """Recursively validate the entire Arbor"""
        ...

    @abstractmethod
    def log(self) -> list[dict[str, Any]]:
        """Arbor-level log of actions on groves"""
        ...

    @abstractmethod
    def list_grove_ids(self) -> list[GroveID]: ...

    def grove(self, grove_id: GroveID) -> Grove:
        return Grove(arbor=self, grove_id=grove_id)

    @abstractmethod
    def create_grove(self, grove_id: GroveID) -> Grove: ...

    @abstractmethod
    def rename_grove(self, grove_id: GroveID, new_id: GroveID) -> None: ...

    @abstractmethod
    def grove_log(self, grove_id: GroveID) -> list[dict[str, Any]]:
        """Grove-level log of actions on assets"""
        ...

    @abstractmethod
    def validate_grove(self, grove_id: GroveID) -> None:
        """Recursively validate all the assets in this grove"""
        ...

    @abstractmethod
    def list_asset_ids(self, grove_id: GroveID) -> list[AssetID]: ...

    @abstractmethod
    def asset_log(self, grove_id: GroveID, asset_id: AssetID) -> list[dict[str, Any]]:
        """Asset-level log of actions on revisions"""
        ...

    @abstractmethod
    def create_asset(self, grove_id: GroveID, asset_id: AssetID) -> Asset: ...

    @abstractmethod
    def rename_asset(
        self, grove_id: GroveID, asset_id: AssetID, new_id: AssetID
    ) -> None: ...

    @abstractmethod
    def validate_asset(self, grove_id: GroveID, asset_id: AssetID) -> None: ...

    @abstractmethod
    def list_rev_ids(
        self, grove_id: GroveID, asset_id: AssetID
    ) -> list[RevisionID]: ...

    @abstractmethod
    def latest_rev_id(self, grove_id: GroveID, asset_id: AssetID) -> RevisionID: ...

    @abstractmethod
    def next_rev_id(self, grove_id: GroveID, asset_id: AssetID) -> RevisionID:
        """Get next revision ID, accounting for burned revisions"""
        ...

    @abstractmethod
    def upload(
        self, grove_id: GroveID, asset_id: AssetID, source: os.PathLike[str]
    ) -> RevisionID: ...

    @abstractmethod
    def paths(
        self,
        grove_id: GroveID,
        asset_id: AssetID,
        rev_id: RevisionID | None = None,
    ) -> list[str]: ...

    @abstractmethod
    def save(
        self,
        grove_id: GroveID,
        asset_id: AssetID,
        destination: os.PathLike[str],
        rev_id: RevisionID | None = None,
    ) -> Path: ...

    @abstractmethod
    def amend(
        self,
        grove_id: GroveID,
        asset_id: AssetID,
        source: os.PathLike[str],
        rev_id: RevisionID | None = None,
    ) -> RevisionID: ...

    @abstractmethod
    def burn(
        self, grove_id: GroveID, asset_id: AssetID, rev_id: RevisionID
    ) -> None: ...


class Grove:
    schema_version = 1

    def __init__(self, arbor: Arbor, grove_id: GroveID):
        self.arbor = arbor
        self.grove_id = _validated_id(grove_id)

    def rename(self, new_id: GroveID) -> None:
        self.arbor.rename_grove(grove_id=self.grove_id, new_id=new_id)

    def log(self) -> list[dict[str, Any]]:
        return self.arbor.grove_log(grove_id=self.grove_id)

    def validate(self) -> None:
        self.arbor.validate_grove(grove_id=self.grove_id)

    def list_asset_ids(self) -> list[AssetID]:
        return self.arbor.list_asset_ids(grove_id=self.grove_id)

    def create_asset(self, asset_id: AssetID) -> Asset:
        return self.arbor.create_asset(self.grove_id, asset_id)

    def asset(self, asset_id: AssetID) -> Asset:
        return Asset(arbor=self.arbor, grove_id=self.grove_id, asset_id=asset_id)


class Asset:
    schema_version = 1

    def __init__(self, arbor: Arbor, grove_id: GroveID, asset_id: AssetID):
        self.arbor = arbor
        self.grove_id = grove_id
        self.asset_id = _validated_id(asset_id)

    def log(self) -> list[dict[str, Any]]:
        return self.arbor.asset_log(grove_id=self.grove_id, asset_id=self.asset_id)

    def rename(self, new_id: AssetID) -> None:
        self.arbor.rename_asset(
            grove_id=self.grove_id, asset_id=self.asset_id, new_id=new_id
        )

    def validate(self) -> None:
        self.arbor.validate_asset(grove_id=self.grove_id, asset_id=self.asset_id)

    def list_rev_ids(self) -> list[RevisionID]:
        return self.arbor.list_rev_ids(grove_id=self.grove_id, asset_id=self.asset_id)

    def latest_rev_id(self) -> RevisionID:
        return self.arbor.latest_rev_id(grove_id=self.grove_id, asset_id=self.asset_id)

    def next_rev_id(self) -> RevisionID:
        return self.arbor.next_rev_id(grove_id=self.grove_id, asset_id=self.asset_id)

    def upload(self, source: os.PathLike[str]) -> RevisionID:
        return self.arbor.upload(
            grove_id=self.grove_id, asset_id=self.asset_id, source=source
        )

    def paths(self, rev_id: RevisionID | None = None) -> list[str]:
        return self.arbor.paths(
            grove_id=self.grove_id, asset_id=self.asset_id, rev_id=rev_id
        )

    def save(
        self, destination: os.PathLike[str], rev_id: RevisionID | None = None
    ) -> Path:
        return self.arbor.save(
            grove_id=self.grove_id,
            asset_id=self.asset_id,
            destination=destination,
            rev_id=rev_id,
        )

    def amend(
        self, source: os.PathLike[str], rev_id: RevisionID | None = None
    ) -> RevisionID:
        return self.arbor.amend(
            grove_id=self.grove_id, asset_id=self.asset_id, source=source, rev_id=rev_id
        )

    def burn(self, rev_id: RevisionID) -> None:
        self.arbor.burn(grove_id=self.grove_id, asset_id=self.asset_id, rev_id=rev_id)


def _validated_id(value: str) -> str:
    """Validation for grove and asset IDs"""
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise Invalid(f"invalid ID: {value!r}")

    return value


def _as_rev_id(value: str) -> RevisionID:
    return int(value)
