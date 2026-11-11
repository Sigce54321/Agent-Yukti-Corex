FROM node:24-bookworm-slim

# Install generic test tooling at image build time, never from the workspace.
# Keep tooling outside /workspace so the task bind mount cannot hide it.
RUN npm install --prefix /opt/yuktic-tooling --no-audit --no-fund jest@30.2.0 \
    && printf '%s\n' '#!/bin/sh' \
       'exec node /opt/yuktic-tooling/node_modules/jest/bin/jest.js --runInBand "$@"' \
       > /usr/local/bin/jest \
    && chmod 755 /usr/local/bin/jest \
    && npm cache clean --force

# Runtime writes go to the sandbox tmpfs. Offline npm also prevents accidental
# dependency fetches; the runner independently enforces --network=none.
ENV NODE_PATH=/opt/yuktic-tooling/node_modules \
    HOME=/tmp \
    TMPDIR=/tmp \
    CI=true \
    npm_config_cache=/tmp/npm-cache \
    npm_config_offline=true \
    npm_config_audit=false \
    npm_config_fund=false \
    npm_config_update_notifier=false

WORKDIR /workspace
