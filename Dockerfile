#
# Args
#
ARG CLAUDE_VERSION=stable
ARG RUST_VERSION=stable 
ARG UV_VERSION=latest
ARG NVM_VERSION=v0.40.1
ARG GO_VERSION=1.23.6
# Workarounds for templated dependencies
FROM ghcr.io/ablack94/docker-claude:${CLAUDE_VERSION} AS claude
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

#
# Image
#
FROM ubuntu:24.04

# Re-declare ARGs needed in this stage (ARGs before FROM are out of scope)
ARG RUST_VERSION
ARG NVM_VERSION
ARG GO_VERSION

#
# Metadata
#
LABEL org.opencontainers.image.source="https://github.com/ablack94/docker-dev"
LABEL org.opencontainers.image.description="Docker image for development work."
LABEL org.opencontainers.image.licenses="MIT"

#
# Baseline DPKGs
#
RUN apt-get update -y \
 && apt-get install -y --no-install-recommends \
      curl \
      ca-certificates \
      build-essential \
      git \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

#
# Claude
#
COPY --from=claude /usr/local/bin/claude /usr/local/bin/claude

#
# Rust
#
ENV RUSTUP_HOME=/opt/rustup \
    CARGO_HOME=/opt/cargo \
    PATH=/opt/cargo/bin:$PATH
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path --default-toolchain ${RUST_VERSION}

#
# Python
#
COPY --from=uv /uv /uvx /bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/python
RUN uv python install 3.13 \
 && ln -sf $(uv python find 3.13) /usr/local/bin/python3.13

#
# Install nvm and setup node/npm LTS
#
ENV NVM_DIR=/opt/nvm
RUN mkdir -p $NVM_DIR \
 && curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh | bash \
 && . "$NVM_DIR/nvm.sh" \
 && nvm install --lts \
 && nvm alias default lts/* \
 && nvm use default
ENV PATH=$NVM_DIR/versions/node/default:$PATH
# Symlink the active node version so it's on PATH without sourcing nvm.sh
RUN . "$NVM_DIR/nvm.sh" && ln -sf "$(dirname "$(which node)")" "$NVM_DIR/versions/node/default"

#
# Install golang
#
RUN curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-$(dpkg --print-architecture).tar.gz" \
    | tar -C /opt -xz
ENV GOROOT=/opt/go \
    PATH=/opt/go/bin:$PATH

#
# CLAUDE.md - generated at build time with actual versions
#
RUN cat <<EOF > /CLAUDE.md
# Base Image: Ubuntu 24.04
## Installed Tools
- **Rust $(rustc --version | awk '{print $2}')**: Installed via rustup. RUSTUP_HOME=/opt/rustup, CARGO_HOME=/opt/cargo. Binaries on PATH via /opt/cargo/bin.
- **Python $(python3.13 --version | awk '{print $2}')**: Installed via uv to /opt/python. Available as \`python3.13\`. Use \`uv\` for package management and virtual environments.
- **Node.js $(node --version)**: Installed via nvm. NVM_DIR=/opt/nvm. Default LTS version symlinked to \$NVM_DIR/versions/node/default.
- **Go $(go version | awk '{print $3}' | sed 's/go//')**: Installed to /opt/go (GOROOT). User GOPATH is /home/claude/go. \`go install\` binaries go to /home/claude/go/bin.
- **uv $(uv --version | awk '{print $2}')**: Python package manager, available at /bin/uv. UV_PYTHON_INSTALL_DIR=/opt/python.
- **Claude Code**: Installed at /usr/local/bin/claude.
EOF

#
# User setup
#
RUN userdel -r ubuntu 2>/dev/null; groupdel ubuntu 2>/dev/null; \
    groupadd --gid 1000 claude \
 && useradd --uid 1000 --gid claude --create-home --shell /bin/bash claude
USER claude
ENV GOPATH=/home/claude/go \
    PATH=/home/claude/go/bin:/home/claude/.local/bin:$PATH

WORKDIR /workarea
