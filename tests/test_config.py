import textwrap
from pathlib import Path

from fsspec.implementations.local import LocalFileSystem

from arbor import Grove
from arbor.cli import run


def test_from_config(tmp_path):
    config = tmp_path / "arbor.toml"
    config.write_text(
        textwrap.dedent("""
    grove = "/path/to/my-grove"
    [filesystem]
    protocol = "local"
    """)
    )

    grove = Grove.from_config(config)
    assert isinstance(grove.fs, LocalFileSystem)
    assert grove.root == "/path/to/my-grove"


def test_find_config_local(config: Path, monkeypatch):
    """Can find a config in the current directory."""
    monkeypatch.chdir(config.parent)
    assert run(["status"]) == 0


def test_find_config_up(config: Path, monkeypatch, capsys):
    """Can find arbor.toml by searching upwards."""
    work_dir = config.parent / "subdir" / "subsubdir"
    work_dir.mkdir(parents=True)
    monkeypatch.chdir(work_dir)

    assert run(["status"]) == 0
    assert "LocalFileSystem" in capsys.readouterr().out


def test_find_config_env_var(tmp_path: Path, config: Path, monkeypatch, capsys):
    work_dir = tmp_path / "find-config-dir"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)

    assert run(["status"]) == 2
    assert "could not find arbor.toml" in capsys.readouterr().err

    monkeypatch.setenv("ARBOR_CONFIG", str(config))

    assert run(["status"]) == 0
    assert "LocalFileSystem" in capsys.readouterr().out
