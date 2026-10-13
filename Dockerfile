# syntax=docker/dockerfile:1.7
# One image for every Python service:  docker run IMAGE serve <service>
# ML extras (torch) are excluded to keep the image small; build with --build-arg EXTRAS=ml for training images.

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS build
ARG EXTRAS=""
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install ".${EXTRAS:+[$EXTRAS]}"

FROM python:${PYTHON_VERSION}-slim AS runtime
LABEL org.opencontainers.image.title="golden-platform" \
      org.opencontainers.image.source="https://github.com/Here2ServeU/nawex-platform" \
      org.opencontainers.image.description="Golden Platform services (API, fintech, healthcare, GPU, migration, identity, agent-ops)"
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GOLDEN_ENV=production \
    GOLDEN_AUTONOMY_MODE=dry_run
RUN groupadd --system --gid 10001 golden \
 && useradd --system --uid 10001 --gid golden --no-create-home --shell /usr/sbin/nologin golden
COPY --from=build /opt/venv /opt/venv
# Persona access model served by identity-governance (same file Terraform reads).
COPY security/identity/access-model.yaml /etc/golden/identity/access-model.yaml
ENV GOLDEN_ACCESS_MODEL=/etc/golden/identity/access-model.yaml
USER 10001:10001
EXPOSE 8000 8090-8099
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\",\"8000\")}/health',timeout=2)"
ENTRYPOINT ["golden"]
CMD ["serve", "api"]
