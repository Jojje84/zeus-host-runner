#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT=/home/umbrel/umbrel/app-data/openclaw/data/zeus-host-runner-candidate-20260902
: "${RUNNER_UID:?STOP: RUNNER_UID must come from verified bootstrap allocation}"
: "${RUNNER_GID:?STOP: RUNNER_GID must come from verified bootstrap allocation}"
printf '%s\n' "$RUNNER_UID" | grep -Eq '^[0-9]+$' || { printf 'STOP invalid_runner_uid\n' >&2; exit 25; }
printf '%s\n' "$RUNNER_GID" | grep -Eq '^[0-9]+$' || { printf 'STOP invalid_runner_gid\n' >&2; exit 25; }
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)-$$
WORK=$(mktemp -d "/tmp/zeus-host-runner-build.${RUN_ID}.XXXXXX")
CTX="$WORK/context"; IID="$WORK/image.iid"; CM="$WORK/context-manifest.sha256"; EVIDENCE="$WORK/build-evidence.txt"; mkdir -m 700 "$CTX"
printf 'BUILD_WORK=%s\n' "$WORK"
test -d "$ROOT" && test ! -L "$ROOT"
cd "$ROOT"
sha256sum -c ARTIFACT-HASHES.sha256 >/dev/null
for f in Dockerfile runner.js runner-schema.json operations.allowlist.json adapter.js fake-backend.js lease.js work-queue-bridge.js daemon.js healthcheck.js readiness.js; do test -f "$f" && test ! -L "$f" || { printf 'STOP missing_or_symlink=%s RUN_ID=%s WORK=%s\n' "$f" "$RUN_ID" "$WORK" >&2; exit 20; }; cp -- "$f" "$CTX/$f"; expected=$(awk -v p="./$f" '$2==p{print $1}' ARTIFACT-HASHES.sha256); actual=$(sha256sum "$CTX/$f" | awk '{print $1}'); test "$expected" = "$actual" || { printf 'STOP context_hash_mismatch=%s RUN_ID=%s WORK=%s\n' "$f" "$RUN_ID" "$WORK" >&2; exit 22; }; done
test "$(find "$CTX" -maxdepth 1 -type f | wc -l)" = 11
(cd "$CTX" && sha256sum Dockerfile runner.js runner-schema.json operations.allowlist.json adapter.js fake-backend.js lease.js work-queue-bridge.js daemon.js healthcheck.js readiness.js) > "$CM"
CM_SHA=$(sha256sum "$CM" | awk '{print $1}')
printf 'RUN_ID=%s\nCONTEXT_MANIFEST=%s\nCONTEXT_MANIFEST_SHA=%s\nIIDFILE=%s\n' "$RUN_ID" "$CM" "$CM_SHA" "$IID" > "$EVIDENCE"
test ! -e "$IID" && test ! -L "$IID"
BASE=$(docker image inspect node:22.23.1-bookworm-slim --format '{{.Id}} {{json .RepoDigests}}') || { printf 'STOP base_inspect_failed\n' >&2; exit 21; }
printf 'BASE_IMAGE_INSPECT=%s\n' "$BASE"
TAG="zeus-host-runner:build-${RUN_ID}"
set +e
docker build --pull=false --build-arg "RUNNER_UID=$RUNNER_UID" --build-arg "RUNNER_GID=$RUNNER_GID" --file "$CTX/Dockerfile" --iidfile "$IID" --tag "$TAG" "$CTX"
BUILD_RC=$?
set -e
if test "$BUILD_RC" -ne 0; then printf 'BUILD_RESULT=FAIL\nBUILD_EXIT=%s\n' "$BUILD_RC" >> "$EVIDENCE"; printf 'STOP build_exit=%s RUN_ID=%s CONTEXT_MANIFEST_SHA=%s IIDFILE=%s WORK=%s\n' "$BUILD_RC" "$RUN_ID" "$CM_SHA" "$IID" "$WORK" >&2; exit "$BUILD_RC"; fi
test -f "$IID" && test ! -L "$IID"
IMAGE_ID=$(tr -d '\r\n' < "$IID")
test "$IMAGE_ID" != '' && printf '%s\n' "$IMAGE_ID" | grep -Eq '^sha256:[0-9a-f]{64}$' || { printf 'STOP iid_invalid work=%s\n' "$WORK" >&2; exit 22; }
INSPECT=$(docker image inspect "$IMAGE_ID" --format '{{.Id}} {{json .RepoDigests}}') || { printf 'STOP inspect_failed image_id=%s RUN_ID=%s CONTEXT_MANIFEST_SHA=%s IIDFILE=%s WORK=%s\n' "$IMAGE_ID" "$RUN_ID" "$CM_SHA" "$IID" "$WORK" >&2; exit 23; }
INSPECT_ID=$(printf '%s\n' "$INSPECT" | awk '{print $1}')
test "$INSPECT_ID" = "$IMAGE_ID" || { printf 'STOP image_id_mismatch iid=%s inspected=%s RUN_ID=%s CONTEXT_MANIFEST_SHA=%s IIDFILE=%s WORK=%s\n' "$IMAGE_ID" "$INSPECT_ID" "$RUN_ID" "$CM_SHA" "$IID" "$WORK" >&2; exit 24; }
printf 'BUILD_RESULT=PASS\nIMAGE_ID=%s\nINSPECTED_ID=%s\nIMAGE_INSPECT=%s\n' "$IMAGE_ID" "$INSPECT_ID" "$INSPECT" >> "$EVIDENCE"
printf 'IMAGE_ID=%s\nINSPECTED_ID=%s\nIMAGE_INSPECT=%s\nBUILD_RESULT=PASS\n' "$IMAGE_ID" "$INSPECT_ID" "$INSPECT"
printf 'RETAIN_WORK=%s\n' "$WORK"
