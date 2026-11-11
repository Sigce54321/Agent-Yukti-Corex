FROM node:24-bookworm-slim AS tooling

RUN npm install --prefix /opt/yuktic-browser --no-audit --no-fund @playwright/test@1.64.1

FROM mcr.microsoft.com/playwright:v1.64.1-noble

COPY --from=tooling /opt/yuktic-browser /opt/yuktic-browser

ENV NODE_PATH=/opt/yuktic-browser/node_modules
ENV PATH="/opt/yuktic-browser/node_modules/.bin:${PATH}"

WORKDIR /workspace