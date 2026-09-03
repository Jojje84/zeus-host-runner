#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
STAGE=bootstrap
trap 'rc=$?; printf "STOP stage=%s line=%s exit=%s\n" "$STAGE" "${BASH_LINENO[0]}" "$rc" >&2; exit "$rc"' ERR
stage(){ STAGE="$1"; printf 'STAGE=%s\n' "$STAGE"; }
stage tools
command -v umbreld >/dev/null || { printf 'UNVERIFIED umbreld_missing\n'; exit 20; }
printf 'umbreld=%s\n' "$(command -v umbreld)"
stage umbrel_root
readonly ROOT=/home/umbrel/umbrel
test -d "$ROOT"
printf 'root=%s\n' "$ROOT"
stage app_store_candidates
for p in "$ROOT/app-store" "$ROOT/apps" "$ROOT/umbrel-apps" "$ROOT/app-data"; do
  if test -d "$p"; then
    stat --printf='dir=%n owner=%U:%G mode=%a\n' -- "$p"
  fi
done
stage runner_paths
for p in /run/zeus-host-runner.sock /run/zeus-host-runner /var/lib/zeus-host-runner /etc/zeus-host-runner; do
  if test -e "$p"; then stat --printf='existing=%n type=%F owner=%U:%G mode=%a\n' -- "$p"; fi
done
stage docker_metadata
if test -S /var/run/docker.sock; then stat --printf='docker_socket=%n owner=%U:%G mode=%a\n' /var/run/docker.sock; else printf 'docker_socket=absent\n'; fi
printf 'NO_MUTATION=TRUE\nNO_SECRET_READ=TRUE\nNO_DOCKER_OPERATION=TRUE\n'
