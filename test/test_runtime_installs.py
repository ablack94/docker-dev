"""Runtime package installs — the things that break when /opt is root-owned.

These need outbound network: `pytest -m "not network"` to skip them.
"""

import shlex

import pytest

from conftest import RUNTIME_UID

pytestmark = pytest.mark.network


@pytest.fixture
def workdir(container):
    path = container.workdir()
    yield path
    container.sh(f"rm -rf {shlex.quote(path)}", check=False)


def test_cargo_fetches_a_crate_into_cargo_home(container, workdir):
    container.sh(
        f"cd {workdir} && cargo new --quiet --bin netdemo --vcs none && cd netdemo && "
        "cargo add --quiet anyhow && cargo build --quiet"
    )
    registry = f"{container.env['CARGO_HOME']}/registry"
    assert container.exec("test", "-d", registry, check=False).ok
    assert container.uid_of(registry) == RUNTIME_UID


def test_rustup_can_add_a_component(container):
    container.exec("rustup", "component", "add", "rust-analyzer")
    assert "rust-analyzer" in container.exec("rustup", "component", "list", "--installed").stdout


def test_npm_install_global_works_without_sudo(container):
    try:
        container.exec("npm", "install", "-g", "--silent", "--no-fund", "--no-audit", "json")
        assert container.which("json"), "globally installed binary is not on PATH"
        assert container.sh('echo \'{"a":1}\' | json a').out == "1"
    finally:
        container.exec("npm", "uninstall", "-g", "--silent", "json", check=False)


def test_uv_pip_install_into_a_venv(container, workdir):
    result = container.sh(
        f"cd {workdir} && uv venv --quiet venv && "
        "uv pip install --quiet --python venv/bin/python packaging && "
        './venv/bin/python -c "import packaging; print(packaging.__version__)"'
    )
    assert result.out


def test_uv_python_install_writes_to_the_managed_dir(container):
    container.exec("uv", "python", "install", "3.12")
    interpreter = container.exec("uv", "python", "find", "3.12").out
    install_dir = container.env["UV_PYTHON_INSTALL_DIR"]
    assert interpreter.startswith(install_dir + "/"), (
        f"3.12 landed outside {install_dir}: {interpreter}"
    )
    assert container.uid_of(interpreter) == RUNTIME_UID


def test_go_install_drops_a_binary_on_path(container):
    container.exec("go", "install", "golang.org/x/example/hello@latest")
    assert container.which("hello"), "go-installed binary is not on PATH"
    assert container.exec("hello").ok


@pytest.mark.slow
def test_nvm_installs_another_node_version(container):
    container.sh('. "$NVM_DIR/nvm.sh" && nvm install 22 >/dev/null && nvm ls --no-colors')
    assert container.sh(f'ls -d {container.env["NVM_DIR"]}/versions/node/v22*', check=False).ok
