# docker-dev

Multi-language development container based on Ubuntu 24.04. Designed for use with Claude Code agents and interactive development.

## What's included

| Tool | Source | Location |
|------|--------|----------|
| Rust/Cargo | rustup | `/opt/rustup`, `/opt/cargo` |
| Python 3.13 | uv | `/opt/python` |
| Node.js LTS | nvm | `/opt/nvm` |
| Go | golang.org | `/opt/go` |
| uv/uvx | astral-sh | `/usr/local/bin/uv` |
| Claude Code | docker-claude | `/usr/local/bin/claude` |

A `/CLAUDE.md` is generated at build time with exact installed versions, so Claude Code agents automatically know what's available.

## Usage

```bash
docker pull ghcr.io/ablack94/docker-dev:stable
```

```bash
docker run -it --rm \
  -v "$HOME/.claude:/home/claude/.claude" \
  -v "$HOME/.claude.json:/home/claude/.claude.json" \
  -v "$(pwd):/workarea" \
  -e CLAUDE_API_KEY \
  ghcr.io/ablack94/docker-dev:stable
```

The container runs as user `claude` (uid=1000) with `/workarea` as the default working directory.

The toolchain directories under `/opt` (rustup, cargo, python, nvm) are owned by the `claude` user, so `cargo build`/`cargo install`, `rustup component add`, `uv python install`, `nvm install`, and `npm install -g` all work at runtime without sudo or environment overrides. Don't bind-mount over `/opt/cargo` — it contains the rustup proxy binaries; to persist the crate cache, mount only `/opt/cargo/registry` and `/opt/cargo/git`.

## Build args

| Arg | Default | Description |
|-----|---------|-------------|
| `CLAUDE_VERSION` | `stable` | Tag for `ghcr.io/ablack94/docker-claude` |
| `RUST_VERSION` | `stable` | Rust toolchain version |
| `UV_VERSION` | `latest` | uv image tag |
| `NVM_VERSION` | `v0.40.1` | nvm install script version |
| `GO_VERSION` | `1.23.6` | Go release version |

```bash
docker build --build-arg GO_VERSION=1.24.0 --build-arg RUST_VERSION=nightly -t docker-dev .
```

## Tests

A pytest suite in `test/` verifies the image behaves for the non-root runtime user (uid 1000): every toolchain on PATH, the `/opt` dirs owned and writable, offline builds for each language, and runtime installs (`cargo add`, `npm install -g`, `go install`, `uv pip install`, `rustup component add`) working without sudo.

```bash
python3 -m venv .venv && .venv/bin/pip install -r test/requirements.txt
docker build -t docker-dev:test .
.venv/bin/pytest                       # ~20s, needs network
```

| Flag | Effect |
|------|--------|
| `--image TAG` | Test a different image (default `docker-dev:test`) |
| `--build` | `docker build` the image first (`--build-arg K=V` to pass args) |
| `--keep-container` | Leave the test container running for poking at |
| `-m "not network"` | Skip the runtime-install tests |
| `-m slow` | Run only the minutes-long tests (deselected by default) |

The suite starts one container and runs the checks with `docker exec`; tests that need pristine state (default user, workdir, volume mounts) launch their own throwaway containers.

## CI

`test.yml` builds the image and runs the suite on every pull request. `publish.yml` calls it as a gate — nothing reaches GHCR unless the tests pass on the same Claude version being published. Both share the same buildx layer cache, so the gate build is reused by the publish build.

Pushes to `main` build and publish to GHCR as `stable`. Git tags (`v*`) produce semver tags. Manual dispatch allows building with a specific Claude version and custom image tag.
