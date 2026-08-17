from __future__ import annotations

import argparse
import json
import sys

from .model import Grove
from .types import ArborError


def run(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="arbor")
    p.add_argument("--config", help="path to arbor.toml")
    c = p.add_subparsers(dest="command", required=True)

    c.add_parser("status", help="show backend status")
    c.add_parser("setup", help="set up the configured backend")

    c.add_parser("log")

    c.add_parser("validate-grove", help="validate all assets")
    c.add_parser("list-assets")

    cc = c.add_parser("create-asset")
    cc.add_argument("asset")

    cc = c.add_parser("rename-asset")
    cc.add_argument("asset")
    cc.add_argument("new_id")

    cc = c.add_parser("upload")
    cc.add_argument("asset")
    cc.add_argument("source")

    cc = c.add_parser("list-versions")
    cc.add_argument("asset")

    cc = c.add_parser("list-data")
    cc.add_argument("grove")
    cc.add_argument("asset")
    cc.add_argument("--version")

    cc = c.add_parser("download")
    cc.add_argument("asset")
    cc.add_argument("dest")
    cc.add_argument("--version")

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
    grove = Grove.from_config(args.config)

    if args.command == "status":
        print(repr(grove.backend))
    elif args.command == "setup":
        grove.setup()
    else:
        grove.connect()
        if args.command == "validate-grove":
            grove.validate()
        elif args.command == "log":
            for entry in grove.read_log():
                print(json.dumps(entry))
        elif args.command == "list-assets":
            _print_lines(grove.list_assets())
        elif args.command == "create-asset":
            grove.create_asset(args.asset)
        elif args.command == "rename-asset":
            grove.rename_asset(args.asset, args.new_id)
        else:
            asset = grove.asset(args.asset)
            if args.command == "list-versions":
                _print_lines(asset.list_versions())
            elif args.command == "list-data":
                print(asset.list_data(version=args.version))
            if args.command == "upload":
                print(asset.upload(args.source))
            elif args.command == "download":
                asset.download(args.dest, version=args.version)
            else:
                raise RuntimeError(f"uncaught command {args.command}")


def _print_lines(lines: list[str]) -> None:
    for line in lines:
        print(line)
