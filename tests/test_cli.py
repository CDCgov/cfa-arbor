import json
from pathlib import Path

from arbor.cli import run


def test_lifecycle(config: Path, capsys):
    """Basic lifecycle works when specifying the config explicitly"""

    def my_run(argv):
        """Run with this config"""
        return run(["--config", str(config)] + argv)

    assert my_run(["status"]) == 0

    # status should be two lines, one with the grove root, one with the file system spec
    status = json.loads(capsys.readouterr().out)
    assert set(status.keys()) == {"grove", "filesystem"}
    fs = status["filesystem"]
    assert isinstance(fs, dict)
    assert set(fs.keys()) == {"cls", "protocol", "args"}
    assert fs["protocol"] == "file"
    assert "LocalFileSystem" in fs["cls"]

    assert my_run(["setup"]) == 0
    # now the grove should exist
    assert Path(status["grove"]).is_dir()

    assert my_run(["list-assets"]) == 0
    assert my_run(["create", "my-asset"]) == 0
    assert my_run(["list-assets"]) == 0
    assert capsys.readouterr().out == "my-asset\n"


def test_asset_commands(tmp_path: Path, config: Path, capsys):
    """Asset commands select the latest version unless one is specified."""

    def my_run(argv):
        return run(["--config", str(config)] + argv)

    assert my_run(["setup"]) == 0
    assert my_run(["create", "my-asset"]) == 0

    source = tmp_path / "data.csv"
    source.write_text("x\n1\n")
    metadata = {"source": "cli", "rows": 1}
    assert (
        my_run(
            [
                "asset",
                "my-asset",
                "upload",
                str(source),
                "--metadata",
                json.dumps(metadata),
            ]
        )
        == 0
    )
    version = capsys.readouterr().out.strip()
    assert version

    assert my_run(["asset", "my-asset", "list-versions"]) == 0
    assert capsys.readouterr().out == f"{version}\n"

    assert my_run(["asset", "my-asset", "latest-version"]) == 0
    assert capsys.readouterr().out == f"{version}\n"

    assert my_run(["asset", "my-asset", "list-data"]) == 0
    assert capsys.readouterr().out == "data.csv\n"
    assert my_run(["asset", "my-asset", "list-data", "--version", version]) == 0
    assert capsys.readouterr().out == "data.csv\n"

    assert my_run(["asset", "my-asset", "mode"]) == 0
    assert capsys.readouterr().out == "file\n"
    assert my_run(["asset", "my-asset", "mode", "--version", version]) == 0
    assert capsys.readouterr().out == "file\n"

    assert my_run(["asset", "my-asset", "metadata"]) == 0
    assert json.loads(capsys.readouterr().out) == metadata
    assert my_run(["asset", "my-asset", "metadata", "--version", version]) == 0
    assert json.loads(capsys.readouterr().out) == metadata

    assert my_run(["asset", "my-asset", "validate"]) == 0
    assert my_run(["asset", "my-asset", "validate", "--version", version]) == 0
    assert my_run(["validate"]) == 0

    latest_dest = tmp_path / "latest.csv"
    assert my_run(["asset", "my-asset", "download", str(latest_dest)]) == 0
    assert latest_dest.read_text() == source.read_text()

    version_dest = tmp_path / "version.csv"
    assert (
        my_run(
            [
                "asset",
                "my-asset",
                "download",
                str(version_dest),
                "--version",
                version,
            ]
        )
        == 0
    )
    assert version_dest.read_text() == source.read_text()

    assert my_run(["asset", "my-asset", "rename", "renamed-asset"]) == 0
    assert my_run(["list-assets"]) == 0
    assert capsys.readouterr().out == "renamed-asset\n"

    assert my_run(["log"]) == 0
    assert '"event": "upload"' in capsys.readouterr().out
