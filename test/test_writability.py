"""The image's core promise: /opt toolchain dirs are writable without sudo."""

import pytest

from conftest import RUNTIME_UID

TOOLCHAIN_HOMES = ["RUSTUP_HOME", "CARGO_HOME", "UV_PYTHON_INSTALL_DIR", "NVM_DIR"]


@pytest.mark.parametrize("var", TOOLCHAIN_HOMES)
def test_toolchain_home_is_owned_by_the_runtime_user(container, var):
    path = container.env[var]
    assert container.uid_of(path) == RUNTIME_UID, f"{var}={path} is not owned by uid {RUNTIME_UID}"
    assert container.writable(path), f"{var}={path} is not writable"


def test_cargo_bin_is_writable(container):
    """`cargo install` drops binaries here."""
    assert container.writable(f"{container.env['CARGO_HOME']}/bin")


def test_cargo_registry_cache_is_writable(container):
    cargo_home = container.env["CARGO_HOME"]
    container.sh(f"mkdir -p {cargo_home}/registry {cargo_home}/git")
    assert container.writable(f"{cargo_home}/registry")
    assert container.writable(f"{cargo_home}/git")


def test_npm_global_prefix_is_writable(container):
    prefix = container.exec("npm", "config", "get", "prefix").out
    assert container.writable(f"{prefix}/lib"), f"npm install -g would need sudo ({prefix})"
    assert container.writable(f"{prefix}/bin")


def test_nvm_can_install_more_node_versions(container):
    assert container.writable(f"{container.env['NVM_DIR']}/versions/node")


def test_gopath_is_under_home_and_on_path(container):
    gopath = container.exec("go", "env", "GOPATH").out
    home = container.env["HOME"]
    assert gopath.startswith(home + "/"), f"GOPATH {gopath} is not under HOME {home}"
    assert f"{gopath}/bin" in container.env["PATH"].split(":"), (
        f"{gopath}/bin is not on PATH: {container.env['PATH']}"
    )
    container.sh(f"mkdir -p {gopath}/bin")
    assert container.writable(f"{gopath}/bin")


@pytest.mark.parametrize("var", ["GOCACHE", "GOMODCACHE"])
def test_go_caches_are_writable(container, var):
    path = container.exec("go", "env", var).out
    container.sh(f"mkdir -p {path}")
    assert container.writable(path)


def test_local_bin_is_writable(container):
    """PATH advertises ~/.local/bin, so pip/uv --user installs must land somewhere real."""
    local_bin = f"{container.env['HOME']}/.local/bin"
    assert local_bin in container.env["PATH"].split(":")
    container.sh(f"mkdir -p {local_bin}")
    assert container.writable(local_bin)
