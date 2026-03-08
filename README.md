# docker-dev

Multi-language development container based on Ubuntu 24.04. Designed for use with Claude Code agents and interactive development.

## What's included

| Tool | Source | Location |
|------|--------|----------|
| Rust/Cargo | rustup | `/opt/rustup`, `/opt/cargo` |
| Python 3.13 | uv | `/opt/python` |
| Node.js LTS | nvm | `/opt/nvm` |
| Go | golang.org | `/opt/go` |
| uv/uvx | astral-sh | `/bin/uv` |
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

## CI

Pushes to `main` build and publish to GHCR as `stable`. Git tags (`v*`) produce semver tags. Manual dispatch allows building with a specific Claude version and custom image tag.
