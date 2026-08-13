from __future__ import annotations

import os
import tomllib
from pathlib import Path

from .core import Arbor, Invalid
from .local import LocalArbor


def from_config(path: str | Path | None = None) -> Arbor:
    config_path = _resolve_config_path(path)
    config = _load_config(config_path)
    return _configure_arbor(config, config_path)


def _configure_arbor(config: dict, path: Path) -> Arbor:
    if not ("backend" in config and isinstance(config["backend"], dict)):
        raise Invalid(f"configuration must contain a [backend] table: {path}")

    backend = config["backend"]
    if "type" not in backend:
        raise Invalid(f"missing backend.type: {path}")
    elif backend["type"] == "local":
        if not ("path" in backend and isinstance(backend["path"], str)):
            raise Invalid(f"backend.path must be a non-empty string: {path}")
        root = (path.parent / backend["path"]).resolve()
        return LocalArbor(root)
    else:
        raise Invalid(f"unsupported backend type {backend['type']!r}: {path}")


def _resolve_config_path(path: str | Path | None) -> Path:
    """
    Search for arbor.toml

    Args:
        path: user-supplied path

    Return: resolved path
    """
    if path is not None:
        resolved_path = Path(path).expanduser().resolve()
        if not resolved_path.is_file():
            raise Invalid(f"configuration file not found: {path}")
        return resolved_path

    if path := os.environ.get("ARBOR_CONFIG"):
        resolved_path = Path(path).expanduser().resolve()
        if not resolved_path.is_file():
            raise Invalid(f"ARBOR_CONFIG file not found: {path}")
        return resolved_path

    start = Path.cwd().resolve()
    searched = []
    for directory in (start, *start.parents):
        candidate = directory / "arbor.toml"
        searched.append(str(candidate))
        if candidate.is_file():
            return candidate
    raise Invalid(
        "could not find arbor.toml; searched: "
        + ", ".join(searched)
        + "; use --config or ARBOR_CONFIG"
    )


def _load_config(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise Invalid(f"invalid configuration: {path}") from error
