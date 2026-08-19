from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

from .model import Asset, Grove
from .types import ArborError, VersionID

Command = Callable[[argparse.Namespace], None]


def run(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    try:
        command: Command = args.command
        command(args)
    except ArborError as error:
        print(f"arbor: {error}", file=sys.stderr)
        return 2
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arbor")
    parser.add_argument("--config", type=Path, help="path to arbor.toml")
    commands = parser.add_subparsers(required=True, metavar="COMMAND")

    _command(commands, "status", _status, "show the configured backend")
    _command(commands, "setup", _setup, "set up the configured backend")
    _command(commands, "log", _log, "print the grove event log")
    _command(commands, "validate", _validate_grove, "recursively validate the grove")
    _command(commands, "list-assets", _list_assets, "list assets in the grove")

    create = _command(commands, "create", _create_asset, "create an asset")
    create.add_argument("asset", metavar="ASSET")

    asset = commands.add_parser(
        "asset", help="perform an operation on a selected asset"
    )
    asset.add_argument("asset", metavar="ASSET")
    asset_commands = asset.add_subparsers(required=True, metavar="COMMAND")

    rename = _command(asset_commands, "rename", _rename_asset, "rename the asset")
    rename.add_argument("new_id", metavar="NEW-ID")

    upload = _command(asset_commands, "upload", _upload, "upload a new asset version")
    upload.add_argument("source", type=Path, metavar="SOURCE")
    upload.add_argument(
        "--metadata",
        type=_metadata_json,
        metavar="METADATA",
        help="JSON object to store as asset version metadata",
    )

    _command(
        asset_commands,
        "list-versions",
        _list_versions,
        "list versions of the asset",
    )
    _command(
        asset_commands,
        "latest-version",
        _latest_version,
        "print the latest version ID",
    )

    list_data = _command(
        asset_commands, "list-data", _list_data, "list data paths in an asset"
    )
    _add_version_option(list_data)

    mode = _command(asset_commands, "mode", _mode, "print the asset mode")
    _add_version_option(mode)

    metadata = _command(asset_commands, "metadata", _metadata, "print asset metadata")
    _add_version_option(metadata)

    download = _command(asset_commands, "download", _download, "download an asset")
    download.add_argument("dest", type=Path, metavar="DEST")
    _add_version_option(download)

    validate = _command(
        asset_commands, "validate", _validate_asset, "validate asset data"
    )
    _add_version_option(validate)

    return parser


def _command(
    subparsers: argparse._SubParsersAction,
    name: str,
    command: Command,
    help: str,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help)
    parser.set_defaults(command=command)
    return parser


def _add_version_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--version",
        metavar="VERSION",
        help="version ID; defaults to the asset's latest version",
    )


def _metadata_json(value: str) -> dict[str, object]:
    try:
        metadata = json.loads(value)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError("metadata must be valid JSON") from error

    if not isinstance(metadata, dict):
        raise argparse.ArgumentTypeError("metadata must be a JSON object")

    return metadata


def _grove(args: argparse.Namespace, *, connect: bool = True) -> Grove:
    grove = Grove.from_config(args.config)

    if connect:
        grove.connect()

    return grove


def _asset(args: argparse.Namespace) -> Asset:
    return _grove(args).asset(args.asset)


def _selected_version(asset: Asset, version: VersionID | None) -> VersionID:
    if version is not None:
        return version
    else:
        latest = asset.latest_version()
        if latest is None:
            raise ArborError(f"{asset.asset_id} has no latest version")
        return latest


def _status(args: argparse.Namespace) -> None:
    print(repr(_grove(args, connect=False).backend))


def _setup(args: argparse.Namespace) -> None:
    _grove(args, connect=False).setup()


def _log(args: argparse.Namespace) -> None:
    for entry in _grove(args).read_log():
        print(json.dumps(entry))


def _validate_grove(args: argparse.Namespace) -> None:
    _grove(args).validate()


def _list_assets(args: argparse.Namespace) -> None:
    _print_lines(_grove(args).list_assets())


def _create_asset(args: argparse.Namespace) -> None:
    _grove(args).create_asset(args.asset)


def _rename_asset(args: argparse.Namespace) -> None:
    _asset(args).rename(args.new_id)


def _upload(args: argparse.Namespace) -> None:
    print(_asset(args).upload(args.source, metadata=args.metadata))


def _list_versions(args: argparse.Namespace) -> None:
    _print_lines(_asset(args).list_versions())


def _latest_version(args: argparse.Namespace) -> None:
    latest = _asset(args).latest_version()
    if latest is not None:
        print(latest)


def _list_data(args: argparse.Namespace) -> None:
    _print_lines(_asset(args).list_data(version=args.version))


def _mode(args: argparse.Namespace) -> None:
    print(_asset(args).mode(version=args.version))


def _metadata(args: argparse.Namespace) -> None:
    print(json.dumps(_asset(args).metadata(version=args.version)))


def _download(args: argparse.Namespace) -> None:
    _asset(args).download(args.dest, version=args.version)


def _validate_asset(args: argparse.Namespace) -> None:
    asset = _asset(args)
    version = _selected_version(asset, args.version)
    asset.grove.validate_version(asset.asset_id, version)


def _print_lines(lines: Iterable[object]) -> None:
    for line in lines:
        print(line)
