FROM node:22.23.1-bookworm-slim
ARG RUNNER_UID
ARG RUNNER_GID
WORKDIR /app
COPY --chown=${RUNNER_UID}:${RUNNER_GID} runner.js runner-schema.json operations.allowlist.json adapter.js fake-backend.js lease.js work-queue-bridge.js daemon.js healthcheck.js readiness.js ./
USER ${RUNNER_UID}:${RUNNER_GID}
ENTRYPOINT ["node","/app/daemon.js"]
