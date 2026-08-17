import os
import shutil
import tomllib
from abc import ABC, abstractmethod
from pathlib import Path, PurePath

from .types import ArborError


class Backend(ABC):
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def exists(self, path: PurePath) -> bool: ...

    @abstractmethod
    def touch(self, path: PurePath) -> None: ...

    @abstractmethod
    def read_text(self, path: PurePath) -> str: ...

    @abstractmethod
    def write_text(self, text: str, path: PurePath) -> None: ...

    @abstractmethod
    def append(self, text: str, path: PurePath) -> None: ...

    @abstractmethod
    def mkdir(self, path: PurePath) -> None: ...

    @abstractmethod
    def rm(self, path: PurePath) -> None:
        """Delete a file or a directory (recursively)"""
        ...

    @abstractmethod
    def move(self, src: PurePath, dst: PurePath) -> None: ...

    @abstractmethod
    def scan(self, path: PurePath) -> tuple[list[str], list[str]]:
        """Return a list of directories and a list of files at the path"""
        ...

    @abstractmethod
    def upload_file(self, source: Path, dest: PurePath) -> None: ...

    @abstractmethod
    def download_file(self, source: PurePath, dest: Path) -> Path: ...


class LocalBackend(Backend):
    def __init__(self, path: os.PathLike[str]):
        self.path = Path(os.path.abspath(path))

    def __repr__(self) -> str:
        return f'LocalBackend("{self.path!s}")'

    def connect(self):
        if not self.path.exists() and self.path.is_dir():
            raise ArborError(f"local path {self.path} is not a directory")

    def exists(self, path: PurePath) -> bool:
        return (self.path / path).exists()

    def touch(self, path: PurePath) -> None:
        (self.path / path).touch()

    def read_text(self, path: PurePath) -> str:
        return (self.path / path).read_text(encoding="utf-8")

    def write_text(self, text: str, path: PurePath) -> None:
        (self.path / path).write_text(text, encoding="utf-8")

    def append(self, text: str, path: PurePath) -> None:
        fp = self.path / path
        old_size = fp.stat().st_size
        try:
            with fp.open("ab") as stream:
                stream.write(text.encode())
                stream.flush()
        except BaseException:
            with fp.open("r+b") as stream:
                stream.truncate(old_size)
            raise

    def mkdir(self, path: PurePath):
        (self.path / path).mkdir()

    def rm(self, path: PurePath):
        # get the concrete path
        p = self.path / path
        if p.is_dir():
            shutil.rmtree(p)
        elif p.is_file():
            p.unlink()
        else:
            raise ArborError(f"Backend cannot delete {p}")

    def move(self, src: PurePath, dst: PurePath):
        shutil.move(self.path / src, self.path / dst)

    def scan(self, path: PurePath) -> tuple[list[str], list[str]]:
        _, dirs, files = next((self.path / path).walk())

        return dirs, files

    def upload_file(self, src: Path, dest: PurePath) -> None:
        shutil.copy(src, self.path / dest)

    def download_file(self, source: PurePath, dest: Path) -> Path:
        return Path(shutil.copy(self.path / source, dest))


def from_config(path: str | Path | None = None) -> Backend:
    config_path = _resolve_config_path(path)
    config = _load_config(config_path)
    return _configure_backend(config, config_path)


def _configure_backend(config: dict, path: Path) -> Backend:
    if not ("backend" in config and isinstance(config["backend"], dict)):
        raise ArborError(f"configuration must contain a [backend] table: {path}")

    backend = config["backend"]
    if "type" not in backend:
        raise ArborError(f"missing backend.type: {path}")
    elif backend["type"] == "local":
        if not ("path" in backend and isinstance(backend["path"], str)):
            raise ArborError(f"backend.path must be a non-empty string: {path}")
        root = (path.parent / backend["path"]).resolve()
        return LocalBackend(root)
    else:
        raise ArborError(f"unsupported backend type {backend['type']!r}: {path}")


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
            raise ArborError(f"configuration file not found: {path}")
        return resolved_path

    if path := os.environ.get("ARBOR_CONFIG"):
        resolved_path = Path(path).expanduser().resolve()
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


def _load_config(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ArborError(f"invalid configuration: {path}") from error
