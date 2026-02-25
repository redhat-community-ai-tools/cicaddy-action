FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install git for local git operations
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY entrypoint.sh ./

RUN uv pip install --system --no-cache . && \
    chmod +x /app/entrypoint.sh && \
    chgrp -R 0 /app && \
    chmod -R g=u /app && \
    useradd -u 1001 -m -d /home/gha-user gha-user && \
    mkdir -p /home/gha-user/.cache && \
    chown -R 1001:0 /home/gha-user && \
    chmod -R g=u /home/gha-user

USER 1001

ENTRYPOINT ["/app/entrypoint.sh"]
