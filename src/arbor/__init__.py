from .model import Asset, Grove
from .types import ArborError


def main() -> None:
    from .cli import run

    raise SystemExit(run())


__all__ = [
    "ArborError",
    "Asset",
    "Grove",
]
