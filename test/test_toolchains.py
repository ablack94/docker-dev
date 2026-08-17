"""Every toolchain is reachable and coherent for the runtime user."""

import pytest

BASELINE_TOOLS = [
    "bash", "cc", "curl", "g++", "git", "jq", "less",
    "make", "rg", "ssh", "tar", "unzip", "zip",
]

TOOLCHAIN_TOOLS = [
    "cargo", "claude", "go", "node", "npm", "python", "python3",
    "python3.13", "rustc", "rustup", "uv", "uvx",
]

VERSION_PROBES = [
    ("cargo", "--version"),
    ("claude", "--version"),
    ("go", "version"),
    ("node", "--version"),
    ("npm", "--version"),
    ("python3", "--version"),
    ("rustc", "--version"),
    ("rustup", "--version"),
    ("uv", "--version"),
]


@pytest.mark.parametrize("tool", BASELINE_TOOLS + TOOLCHAIN_TOOLS)
def test_tool_is_on_path(container, tool):
    assert container.which(tool), f"{tool} is not on PATH: {container.env['PATH']}"


@pytest.mark.parametrize("argv", VERSION_PROBES, ids=lambda a: a[0])
def test_tool_reports_a_version(container, argv):
    assert container.exec(*argv).out


def test_python_aliases_are_the_same_interpreter(container):
    """The aliases are separate symlinks (uv also drops one in ~/.local/bin);
    what matters is that they all land on the same uv-managed interpreter."""
    probe = "import os, sys; print(os.path.realpath(sys.executable), sys.version_info[:2])"
    seen = {name: container.exec(name, "-c", probe).out for name in ("python", "python3", "python3.13")}
    assert len(set(seen.values())) == 1, f"aliases resolve to different interpreters: {seen}"
    assert "(3, 13)" in seen["python3"]
    assert seen["python3"].startswith(container.env["UV_PYTHON_INSTALL_DIR"] + "/")


def test_rust_components_are_installed(container):
    assert container.exec("cargo", "clippy", "--version").out
    assert container.exec("cargo", "fmt", "--version").out
    sysroot = container.exec("rustc", "--print", "sysroot").out
    src = f"{sysroot}/lib/rustlib/src/rust"
    assert container.exec("test", "-d", src, check=False).ok, f"rust-src missing at {src}"


def test_login_shell_keeps_toolchains_on_path(container):
    """/etc/profile is a classic PATH clobberer; make sure it isn't one here."""
    result = container.sh("command -v cargo go node npm python3 uv", login=True, check=False)
    assert result.ok, f"login shell lost part of PATH:\n{result}"
    assert len(result.out.splitlines()) == 6


def test_interactive_shell_exposes_nvm(container):
    result = container.sh("type nvm", interactive=True, check=False)
    assert "nvm is a function" in result.stdout, f"nvm is not sourced in interactive shells:\n{result}"


def test_nvm_default_matches_the_node_on_path(container):
    on_path = container.exec("node", "--version").out
    nvm_default = container.sh(
        '. "$NVM_DIR/nvm.sh" >/dev/null 2>&1; nvm version default'
    ).out.splitlines()[-1]
    assert nvm_default != "N/A", "nvm has no default alias"
    assert nvm_default == on_path, f"nvm default {nvm_default} != node on PATH {on_path}"


def test_nvm_ls_lists_only_real_versions(container):
    """`$NVM_DIR/versions/node/default` is a symlink nvm also scans as a version."""
    listing = container.sh('. "$NVM_DIR/nvm.sh" >/dev/null 2>&1; nvm ls --no-colors').stdout
    entries = [line.strip(" ->*") for line in listing.splitlines() if line.strip()]
    bogus = [e for e in entries if e.startswith("default") and "->" not in e]
    assert not bogus, f"nvm ls reports a non-version entry:\n{listing}"


def test_utf8_round_trips(container):
    assert container.exec("python3", "-c", 'print("héllo ✓")').out == "héllo ✓"
    assert container.exec("node", "-e", 'console.log("héllo ✓")').out == "héllo ✓"
