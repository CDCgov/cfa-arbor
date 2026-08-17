from typing import Literal

type AssetID = str
type VersionID = str
type AssetMode = Literal["auto", "dir", "file"]


class ArborError(Exception):
    pass
