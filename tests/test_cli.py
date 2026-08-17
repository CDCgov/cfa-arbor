import re

from arbor import Grove
from arbor.backend import LocalBackend
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


def test_find_config(tmp_path, monkeypatch):
    """Can find a config locally"""
    raise NotImplementedError
    config = tmp_path / "arbor.toml"
    config.write_text('[backend]\ntype = "local"\npath = "my-grove"\n')

    grove = Grove.from_config(config)

    assert isinstance(grove, Grove)
    backend = grove.backend
    assert isinstance(backend, LocalBackend)
    assert backend.path == (tmp_path / "my-grove").resolve()


def test_use_env_var():
    raise NotImplementedError
