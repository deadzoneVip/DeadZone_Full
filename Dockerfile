FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# ── Base tools ────────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    git-lfs \
    curl \
    sudo \
    zip \
    unzip \
    p7zip-full \
    zstd \
    brotli \
    lz4 \
    jq \
    file \
    ca-certificates \
    tar \
    xz-utils \
    aria2 \
    python3 \
    python3-pip \
    python3-venv \
    e2fsprogs \
    erofs-utils \
    android-sdk-libsparse-utils \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# ── GitHub CLI ────────────────────────────────────────────────────────────────
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
      https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y gh && \
    rm -rf /var/lib/apt/lists/*

# ── Python deps for dzfactory ─────────────────────────────────────────────────
RUN pip3 install --no-cache-dir --break-system-packages \
    pyyaml \
    requests \
    jsonschema

# ── Copy repo + build script ──────────────────────────────────────────────────
WORKDIR /deadzone
COPY . /deadzone/

# Make all scripts executable
RUN chmod +x main.sh core/*.sh bin/* 2>/dev/null || true && \
    chmod +x /deadzone/dz_build_script.sh 2>/dev/null || true

ENTRYPOINT ["/deadzone/dz_build_script.sh"]
