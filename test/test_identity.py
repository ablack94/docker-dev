"""Who the container runs as, and what that account can reach."""

from conftest import RUNTIME_GID, RUNTIME_UID


def test_runs_as_uid_1000(container):
    assert int(container.exec("id", "-u").out) == RUNTIME_UID
    assert int(container.exec("id", "-g").out) == RUNTIME_GID


def test_uid_has_a_passwd_entry(container):
    """Without one, whoami, git and ssh all misbehave."""
    entry = container.exec("getent", "passwd", str(RUNTIME_UID)).out
    assert entry, f"no /etc/passwd entry for uid {RUNTIME_UID}"
    assert container.exec("whoami").out


def test_home_is_set_and_owned_by_the_runtime_user(container):
    home = container.env.get("HOME")
    assert home, "HOME is not set in the image environment"
    assert container.exec("test", "-d", home, check=False).ok, f"HOME does not exist: {home}"
    assert container.uid_of(home) == RUNTIME_UID
    assert container.writable(home)


def test_home_matches_the_passwd_entry(container):
    passwd_home = container.exec("getent", "passwd", str(RUNTIME_UID)).out.split(":")[5]
    assert container.env["HOME"] == passwd_home


def test_not_root_and_system_prefixes_stay_read_only(container):
    assert int(container.exec("id", "-u").out) != 0
    assert not container.writable("/usr/local/bin"), (
        "/usr/local/bin is writable by the runtime user — the image is too permissive"
    )


def test_default_user_is_uid_1000(docker_run):
    """The image must not need an explicit --user to be unprivileged."""
    assert docker_run("id -u").out == str(RUNTIME_UID)


def test_explicit_numeric_user_still_gets_a_working_environment(docker_run):
    """`docker run --user 1000:1000` is common in CI; HOME/PATH must survive it."""
    result = docker_run(
        "echo $HOME; command -v cargo go node python3 uv",
        args=["--user", f"{RUNTIME_UID}:{RUNTIME_GID}"],
    )
    lines = result.out.splitlines()
    assert lines[0].startswith("/home/"), f"unexpected HOME: {lines[0]!r}"
    assert len(lines) == 6, f"toolchains missing from PATH:\n{result}"


def test_default_workdir_is_workarea(docker_run):
    assert docker_run("pwd").out == "/workarea"


def test_workarea_is_owned_by_the_runtime_user_and_writable(container):
    assert container.uid_of("/workarea") == RUNTIME_UID
    assert container.writable("/workarea")


def test_fresh_volume_on_workarea_is_writable(docker_run):
    """Anonymous/named volumes inherit the image dir's ownership — check they do."""
    result = docker_run("touch /workarea/probe && echo ok", args=["-v", "/workarea"])
    assert result.out == "ok"


def test_claude_md_is_present_and_readable(container):
    assert container.exec("test", "-s", "/CLAUDE.md", check=False).ok
    assert "Ubuntu" in container.exec("cat", "/CLAUDE.md").stdout
