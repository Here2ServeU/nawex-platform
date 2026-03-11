# ------------------------------------------------------------------------------
# NEXUS WORKLOAD CONTAINER - MULTI-STAGE BUILD
# ------------------------------------------------------------------------------
# Architect: Emmanuel Naweji
# Strategy:  Optimized for security and size. Uses multi-stage builds to
#            discard development dependencies and keep the runtime lightweight.
# ------------------------------------------------------------------------------

# --- STAGE 1: BUILDER ---
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /usr/src/app

# Install dependencies (cached if package.json hasn't changed)
COPY package*.json ./
# Install ALL dependencies (including devDeps for testing/building)
RUN npm ci

# Copy source code
COPY . .

# (Optional) Run tests during build - fails build if tests fail
# RUN npm test

# Prune dev dependencies to keep the final layer small
RUN npm prune --production

# --- STAGE 2: RUNTIME ---
FROM node:18-alpine

# Set working directory
WORKDIR /usr/src/app

# Security: Don't run as root
# Create a non-root user 'nexus'
RUN addgroup -g 1001 nexus && adduser -u 1001 -G nexus -s /bin/sh -D nexus

# Copy only production artifacts from builder stage
COPY --from=builder --chown=nexus:nexus /usr/src/app/node_modules ./node_modules
COPY --from=builder --chown=nexus:nexus /usr/src/app/src ./src
COPY --from=builder --chown=nexus:nexus /usr/src/app/package.json ./

# Set environment variables
ENV NODE_ENV=production
ENV PORT=3000

# Switch to non-root user
USER nexus

# Expose port
EXPOSE 3000

# Healthcheck for orchestration resilience
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

# Start the platform wrapper
CMD ["node", "src/index.js"]
