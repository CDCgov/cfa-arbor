import os
import tomllib
from os import PathLike
from pathlib import Path

import fsspec

from arbor.types import ArborError


def from_config(path: PathLike | None = None) -> tuple[str, fsspec.AbstractFileSystem]:
    """
    Args:
        path: path to config. If `None`, then search for the config using
            environmental variable and then by looking for an `arbor.toml`.

    Returns:
        grove root path and file system
    """
    config_path = _resolve_config_path(path)
    config = _load_config(config_path)

    return config["grove"], fsspec.filesystem(**config["filesystem"])


def _load_config(path: Path) -> dict:
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ArborError(f"invalid configuration: {path}") from error

    if "grove" not in config:
        raise ArborError(f"configuration {path} does not specify `grove` (root path)")

    if not ("filesystem" in config and isinstance(config["filesystem"], dict)):
        raise ArborError(f"configuration {path} does not contain [filesystem] table")

    return config


def _resolve_config_path(path: PathLike | None) -> Path:
    """
    Search for arbor.toml

    Args:
        path: user-supplied path

    Return: resolved path
    """
    if path is not None:
        resolved_path = Path(path).expanduser().resolve()
        if not resolved_path.is_file():
            raise ArborError(f"configuration file not found: {path}")
        return resolved_path

    if env_path := os.environ.get("ARBOR_CONFIG"):
        resolved_path = Path(env_path).expanduser().resolve()
        if not resolved_path.is_file():
            raise ArborError(f"ARBOR_CONFIG file not found: {path}")
        return resolved_path

    start = Path.cwd().resolve()
    searched = []
    for directory in (start, *start.parents):
        candidate = directory / "arbor.toml"
        searched.append(str(candidate))
        if candidate.is_file():
            return candidate
    raise ArborError(
        "could not find arbor.toml; searched: "
        + ", ".join(searched)
        + "; use --config or ARBOR_CONFIG"
    )
