#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=${1:-"$(cd "$(dirname "$0")" && pwd)/community-store-candidate"}
STORE="$ROOT/umbrel-app-store.yml"
APP="$ROOT/zeus-host-runner"
test -f "$STORE" && test ! -L "$STORE"
test -f "$APP/umbrel-app.yml" && test ! -L "$APP/umbrel-app.yml"
test -f "$APP/docker-compose.yml" && test ! -L "$APP/docker-compose.yml"
grep -Eq '^id: zeus$' "$STORE"
grep -Eq '^id: zeus-host-runner$' "$APP/umbrel-app.yml"
grep -Eq '^  - zeus-host-runner$' "$STORE"
grep -Eq 'context: \.$' "$APP/docker-compose.yml"
grep -Eq 'RUNNER_UID:\s*\$\{RUNNER_UID:\?[^}]+\}' "$APP/docker-compose.yml"
grep -Eq 'RUNNER_GID:\s*\$\{RUNNER_GID:\?[^}]+\}' "$APP/docker-compose.yml"
! grep -Eiq 'github|https?://|docker\.sock|privileged:[[:space:]]*true|password|token|secret|ADD[[:space:]]|curl|wget' "$ROOT/umbrel-app-store.yml" "$APP/umbrel-app.yml" "$APP/docker-compose.yml" "$APP/SOURCE-BINDING.txt"
printf '%s\n' 'COMMUNITY_STORE_CANDIDATE=PASS_STATIC'
printf '%s\n' 'STORE_URL=ABSENT'
printf '%s\n' 'PUBLISH=DISABLED'
printf '%s\n' 'HOST_IMPORT=UNVERIFIED'
printf '%s\n' 'IMAGE_ID=UNVERIFIED'
printf '%s\n' 'RUNNER_UID_GID=BOOTSTRAP_REQUIRED'
