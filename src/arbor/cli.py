from __future__ import annotations

import argparse
import json
import sys

from .core import Arbor, ArborError


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
    my_arbor = Arbor.from_config(args.config)

    if args.command == "status":
        print(my_arbor)

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


def _print_lines(values: list) -> None:
    for value in values:
        print(value if isinstance(value, (str, int)) else json.dumps(value))
