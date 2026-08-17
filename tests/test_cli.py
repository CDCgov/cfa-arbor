import re

from arbor.cli import run


def test_simple(tmp_path, capsys):
    """Basic lifecycle works when specifying the config explicitly"""
    grove_path = tmp_path / "grove"

    config = (tmp_path / "arbor.toml").resolve()
    config.write_text(f'[backend]\ntype = "local"\npath = "{grove_path!s}"\n')

    def my_run(argv):
        """Run with this config"""
        return run(["--config", str(config)] + argv)

    assert my_run(["status"]) == 0
    re.match(r'LocalBackend\(".+"\)', capsys.readouterr().out)
    assert my_run(["setup"]) == 0
    assert my_run(["list-assets"]) == 0
    assert my_run(["create-asset", "my-asset"]) == 0
    assert my_run(["list-assets"]) == 0
    assert capsys.readouterr().out == "my-asset\n"


def test_find_config(tmp_path, monkeypatch, capsys):
    """Can find a config locally"""
    grove_dir = tmp_path / "grove"

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    config_path = work_dir / "arbor.toml"
    config_path.write_text(
        "\n".join(["[backend]", 'type = "local"', f'path = "{grove_dir!s}"'])
    )

    monkeypatch.chdir(work_dir)

    assert run(["status"]) == 0
    assert capsys.readouterr().out == f'LocalBackend("{grove_dir!s}")\n'


def test_use_env_var(tmp_path, monkeypatch, capsys):
    grove_dir = tmp_path / "grove"
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "arbor.toml"
    config_path.write_text(
        "\n".join(["[backend]", 'type = "local"', f'path = "{grove_dir!s}"'])
    )

    monkeypatch.chdir(work_dir)

    # can't find config if it's not in the local tree
    assert run(["status"]) == 2
    assert "could not find arbor.toml" in capsys.readouterr().err

    # can find it if we set an env var
    monkeypatch.setenv("ARBOR_CONFIG", str(config_path))

    assert run(["status"]) == 0
    assert capsys.readouterr().out == f'LocalBackend("{grove_dir!s}")\n'


def test_config_up(tmp_path, monkeypatch, capsys):
    """Search upwards for the arbor.toml"""
    grove_dir = tmp_path / "grove"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "arbor.toml").write_text(
        "\n".join(["[backend]", 'type = "local"', f'path = "{grove_dir!s}"'])
    )
    work_dir = config_dir / "below_config" / "yet_deeper"
    work_dir.mkdir(parents=True)
    monkeypatch.chdir(work_dir)

    assert run(["status"]) == 0
    assert capsys.readouterr().out == f'LocalBackend("{grove_dir!s}")\n'
