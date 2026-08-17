"""Offline smoke builds — each toolchain compiles and runs something."""

import shlex

import pytest


@pytest.fixture
def workdir(container):
    """A fresh scratch dir under $HOME, so builds exercise user-owned storage."""
    path = container.workdir()
    yield path
    container.sh(f"rm -rf {shlex.quote(path)}", check=False)


def test_cc_compiles_and_links(container, workdir):
    container.sh(
        f"cd {workdir} && printf '%s\\n' '#include <stdio.h>' "
        "'int main(void){puts(\"hello-cc\");return 0;}' > t.c && cc t.c -o t-cc"
    )
    assert container.sh(f"{workdir}/t-cc").out == "hello-cc"


def test_rustc_compiles_and_runs(container, workdir):
    container.sh(
        f"cd {workdir} && echo 'fn main(){{println!(\"hello-rust\");}}' > t.rs && rustc -O t.rs -o t-rust"
    )
    assert container.sh(f"{workdir}/t-rust").out == "hello-rust"


def test_cargo_builds_a_new_crate_offline(container, workdir):
    result = container.sh(
        f"cd {workdir} && cargo new --quiet --bin demo --vcs none && cd demo "
        "&& cargo build --quiet --offline && ./target/debug/demo"
    )
    assert result.out == "Hello, world!"


def test_go_builds_a_module(container, workdir):
    result = container.sh(
        f"cd {workdir} && go mod init example.com/demo >/dev/null && "
        "printf '%s\\n' 'package main' 'import \"fmt\"' "
        "'func main(){fmt.Println(\"hello-go\")}' > main.go && go build -o t-go . && ./t-go"
    )
    assert result.out == "hello-go"


def test_uv_creates_a_venv_from_the_managed_python(container, workdir):
    result = container.sh(
        f"cd {workdir} && uv venv --quiet venv && "
        './venv/bin/python -c "import sys; print(sys.version_info[:2])"'
    )
    assert result.out == "(3, 13)"


def test_node_runs_a_script(container, workdir):
    container.sh(f"cd {workdir} && echo 'console.log(2 + 2)' > t.js")
    assert container.sh(f"node {workdir}/t.js").out == "4"


def test_git_can_init_and_commit(container, workdir):
    result = container.sh(
        f"cd {workdir} && git init --quiet -b main . && echo hi > f && git add f && "
        "git -c user.name=Harness -c user.email=harness@example.com commit --quiet -m test && "
        "git log --oneline"
    )
    assert "test" in result.out


def test_claude_binary_runs(container):
    assert container.exec("claude", "--version").out
    assert container.exec("claude", "--help").ok
