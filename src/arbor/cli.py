from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

from .core import Arbor, ArborError, Invalid
from .local import LocalArbor


def run(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="arbor")
    p.add_argument("--config", help="path to arbor.toml")
    c = p.add_subparsers(dest="command", required=True)

    c.add_parser("status", help="show resolved configuration without connecting")
    c.add_parser("init", help="initialize the configured backend")

    c.add_parser("list-groves", help="list groves in the backend")
    c.add_parser("log-groves")

    c.add_parser("validate-backend", help="validate all groves")

    cc = c.add_parser("create-grove")
    cc.add_argument("grove")

    cc = c.add_parser("rename-grove")
    cc.add_argument("grove")
    cc.add_argument("new_id")

    cc = c.add_parser("list-assets")
    cc.add_argument("grove")

    cc = c.add_parser("log-assets")
    cc.add_argument("grove")

    cc = c.add_parser("rename-asset")
    cc.add_argument("grove")
    cc.add_argument("asset")
    cc.add_argument("new_id")

    cc = c.add_parser("upload")
    cc.add_argument("grove")
    cc.add_argument("asset")
    cc.add_argument("source")

    cc = c.add_parser("revs")
    cc.add_argument("grove")
    cc.add_argument("asset")

    cc = c.add_parser("log-revs")
    cc.add_argument("grove")
    cc.add_argument("asset")

    cc = c.add_parser("paths")
    cc.add_argument("grove")
    cc.add_argument("asset")
    cc.add_argument("--rev", type=int)

    cc = c.add_parser("save")
    cc.add_argument("grove")
    cc.add_argument("asset")
    cc.add_argument("dest")
    cc.add_argument("--rev", type=int)

    cc = c.add_parser("amend")
    cc.add_argument("grove")
    cc.add_argument("asset")
    cc.add_argument("source")
    cc.add_argument("--rev", type=int)

    cc = c.add_parser("burn")
    cc.add_argument("grove")
    cc.add_argument("asset")
    cc.add_argument("--rev", type=int)

    args = p.parse_args(argv)

    try:
        _dispatch(args)
    except ArborError as error:
        print(f"arbor: {error}", file=sys.stderr)
        return 2
    return 0


def _dispatch(args: argparse.Namespace) -> None:
    """Execute logic, based on the parsed args"""
    # find and load the config; get the backend set up
    config_path = _resolve_config_path(args.config)
    config = _load_config(config_path)
    my_arbor = _configure_arbor(config=config, path=config_path)

    if args.command == "status":
        print(f"config: {config_path}")
        print(config)

    elif args.command == "init":
        my_arbor.init()
    elif args.command == "validate-arbor":
        my_arbor.validate()
    else:
        my_arbor.connect()
        if args.command == "list-groves":
            _print_lines(my_arbor.list_grove_ids())
        elif args.command == "arbor-log":
            _print_lines(my_arbor.log())
        elif args.command == "create-grove":
            my_arbor.create_grove(args.grove)
        elif args.command == "rename-grove":
            my_arbor.grove(args.grove).rename(args.new_id)
        else:
            grove = my_arbor.grove(args.grove)
            if args.command == "list-assets":
                _print_lines(grove.list_asset_ids())
            elif args.command == "grove-log":
                _print_lines(grove.log())
            elif args.command == "rename-asset":
                grove.asset(args.asset).rename(args.new_id)
            else:
                asset = grove.asset(args.asset)
                if args.command == "upload":
                    print(asset.upload(args.source))
                elif args.command == "list-revs":
                    _print_lines(asset.list_rev_ids())
                elif args.command == "asset-log":
                    _print_lines(asset.log())
                elif args.command == "paths":
                    _print_lines(asset.paths(args.rev))
                elif args.command == "save":
                    asset.save(args.dest, args.rev)
                elif args.command == "amend":
                    print(asset.amend(args.source, args.rev))
                elif args.command == "burn":
                    print(asset.burn(args.rev))


def _resolve_config_path(path: str | None) -> Path:
    """
    Search for arbor.toml

    Args:
        path: user-supplied path

    Return: resolved path
    """
    # use explicitly supplied path if possible
    if path is not None:
        resolved_path = Path(path).expanduser().resolve()
        if not resolved_path.is_file():
            raise Invalid(f"configuration file not found: {path}")
        return resolved_path

    # if not, use path supplied in the env var
    if path := os.environ.get("ARBOR_CONFIG"):
        resolved_path = Path(path).expanduser().resolve()
        if not resolved_path.is_file():
            raise Invalid(f"ARBOR_CONFIG file not found: {path}")
        return resolved_path

    # if not, search through the directory structure
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


def _configure_arbor(config: dict, path: Path) -> Arbor:
    if not (isinstance(config["backend"], dict) and "backend" in config):
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


def _print_lines(values: list) -> None:
    for value in values:
        print(value if isinstance(value, (str, int)) else json.dumps(value))
