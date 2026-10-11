# syntax=docker/dockerfile:1
# golden-client-portal — production image
# Build: docker build -t ghcr.io/here2serveu/golden-client-portal:dev apps/client-portal

ARG NODE_IMAGE=node:22-alpine

# --- deps: production node_modules only --------------------------------------
FROM ${NODE_IMAGE} AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts && npm cache clean --force

# --- runtime -------------------------------------------------------------------
FROM ${NODE_IMAGE} AS runtime
ENV NODE_ENV=production \
    PORT=3001
WORKDIR /app

RUN addgroup -g 10001 -S app && adduser -u 10001 -S -G app -H -s /sbin/nologin app

COPY --from=deps --chown=10001:10001 /app/node_modules ./node_modules
COPY --chown=10001:10001 package.json ./
COPY --chown=10001:10001 src ./src
COPY --chown=10001:10001 public ./public

USER 10001:10001
EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- "http://127.0.0.1:${PORT}/health" >/dev/null || exit 1

# exec-form so node is PID 1 and receives SIGTERM directly
CMD ["node", "src/server.js"]
