"""Fixtures for the docker-dev image tests.

The suite starts one long-lived container from the image under test and runs
every check inside it with `docker exec`, as the image's runtime user. Tests
that need pristine container state (default user, workdir, mounts) use the
`docker_run` fixture instead.
"""

from __future__ import annotations

import dataclasses
import shlex
import subprocess
import textwrap
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The image is expected to run as this uid/gid regardless of the account name.
RUNTIME_UID = 1000
RUNTIME_GID = 1000


def pytest_addoption(parser):
    group = parser.getgroup("docker-dev")
    group.addoption(
        "--image",
        default="docker-dev:test",
        help="Image to test (default: docker-dev:test)",
    )
    group.addoption(
        "--build",
        action="store_true",
        help="Build the image from the repo Dockerfile before testing",
    )
    group.addoption(
        "--build-arg",
        action="append",
        default=[],
        dest="build_args",
        metavar="KEY=VALUE",
        help="Extra --build-arg for --build (repeatable)",
    )
    group.addoption(
        "--keep-container",
        action="store_true",
        help="Leave the test container running afterwards for poking at",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "network: needs outbound network access")
    config.addinivalue_line("markers", "slow: takes minutes (deselected by default)")


# --------------------------------------------------------------------- shell --


@dataclasses.dataclass
class Result:
    """Outcome of one command inside the container."""

    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def out(self) -> str:
        """stdout, stripped — the common case for assertions."""
        return self.stdout.strip()

    def __str__(self) -> str:
        body = "\n".join(
            [
                f"$ {shlex.join(self.argv)}",
                f"exit {self.returncode}",
                *(["--- stdout ---", self.stdout.rstrip()] if self.stdout.strip() else []),
                *(["--- stderr ---", self.stderr.rstrip()] if self.stderr.strip() else []),
            ]
        )
        return textwrap.indent(body, "  ")


def _run(argv: list[str], timeout: int = 900) -> Result:
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return Result(argv, proc.returncode, proc.stdout, proc.stderr)


class Container:
    """A running container, with helpers for the checks the tests keep repeating."""

    def __init__(self, cid: str, image: str):
        self.id = cid
        self.image = image
        self._env: dict[str, str] | None = None

    # -- running things --

    def exec(self, *argv: str, check: bool = True, timeout: int = 900) -> Result:
        result = _run(["docker", "exec", self.id, *argv], timeout=timeout)
        if check and not result.ok:
            pytest.fail(f"command failed in container:\n{result}", pytrace=False)
        return result

    def sh(
        self,
        script: str,
        *,
        check: bool = True,
        login: bool = False,
        interactive: bool = False,
        timeout: int = 900,
    ) -> Result:
        """Run a bash snippet. `login`/`interactive` pick up profile/bashrc."""
        flags = "-" + ("l" if login else "") + ("i" if interactive else "") + "c"
        return self.exec("bash", flags, script, check=check, timeout=timeout)

    # -- inspecting things --

    @property
    def env(self) -> dict[str, str]:
        if self._env is None:
            raw = self.exec("env").stdout
            self._env = dict(
                line.split("=", 1) for line in raw.splitlines() if "=" in line
            )
        return self._env

    def uid_of(self, path: str) -> int:
        return int(self.exec("stat", "-c", "%u", path).out)

    def writable(self, path: str) -> bool:
        """Actually write a file — `test -w` lies about read-only mounts."""
        probe = f"{path}/.pytest-probe-{uuid.uuid4().hex[:8]}"
        result = self.sh(f"touch {shlex.quote(probe)} && rm -f {shlex.quote(probe)}", check=False)
        return result.ok

    def which(self, program: str) -> str | None:
        result = self.exec("bash", "-c", f"command -v {shlex.quote(program)}", check=False)
        return result.out if result.ok else None

    def workdir(self) -> str:
        """A scratch directory, fresh per call, owned by the runtime user."""
        return self.exec("mktemp", "-d", "-p", self.env["HOME"]).out


# ------------------------------------------------------------------ fixtures --


@pytest.fixture(scope="session")
def image(pytestconfig) -> str:
    tag = pytestconfig.getoption("image")
    if pytestconfig.getoption("build"):
        argv = ["docker", "build", "-t", tag]
        for arg in pytestconfig.getoption("build_args"):
            argv += ["--build-arg", arg]
        argv.append(str(REPO_ROOT))
        print(f"\nbuilding {tag} ...")
        build = _run(argv, timeout=3600)
        if not build.ok:
            pytest.fail(f"docker build failed:\n{build}", pytrace=False)

    exists = _run(["docker", "image", "inspect", tag])
    if not exists.ok:
        pytest.fail(
            f"image {tag!r} not found locally; build it or pass --build / --image",
            pytrace=False,
        )
    return tag


@pytest.fixture(scope="session")
def container(image, pytestconfig):
    """One container shared by the whole session, started the way users start it."""
    started = _run(
        ["docker", "run", "-d", "--name", f"docker-dev-test-{uuid.uuid4().hex[:8]}", image,
         "sleep", "infinity"]
    )
    if not started.ok:
        pytest.fail(f"could not start container:\n{started}", pytrace=False)
    cid = started.out

    try:
        yield Container(cid, image)
    finally:
        if pytestconfig.getoption("keep_container"):
            print(f"\ncontainer left running: {cid}")
        else:
            _run(["docker", "rm", "-f", cid])


@pytest.fixture
def docker_run(image):
    """Run a throwaway container: `docker_run("id -u", args=["--user", "1000:1000"])`."""

    def run(command: str, *, args: list[str] | None = None, check: bool = True) -> Result:
        argv = ["docker", "run", "--rm", *(args or []), image, "bash", "-c", command]
        result = _run(argv)
        if check and not result.ok:
            pytest.fail(f"container run failed:\n{result}", pytrace=False)
        return result

    return run
