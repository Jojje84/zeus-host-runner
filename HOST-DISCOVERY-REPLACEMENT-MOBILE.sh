#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
printf 'DISCOVERY=HOST-RUNNER-REPLACEMENT-V1\n'
printf 'NO_MUTATION=TRUE\nNO_SECRET_READ=TRUE\nNO_DOCKER_OPERATION=TRUE\n'
printf 'TOOL_METADATA_BEGIN\n'
for x in umbreld systemctl docker stat getent id find; do command -v "$x" 2>/dev/null | sed "s#^#tool=$x path=#" || printf 'tool=%s absent\n' "$x"; done
printf 'TOOL_METADATA_END\n'
printf 'IDENTITY_METADATA_BEGIN\n'
id umbrel 2>/dev/null || printf 'identity=umbrel unavailable\n'
getent group docker 2>/dev/null || printf 'group=docker unavailable\n'
printf 'IDENTITY_METADATA_END\n'
printf 'PATH_METADATA_BEGIN\n'
for p in /home/umbrel/umbrel /home/umbrel/umbrel/app-data /home/umbrel/umbrel/app-data/openclaw /home/umbrel/umbrel/app-data/openclaw/data /run/zeus-host-runner.sock /run/zeus-host-runner /var/lib/zeus-host-runner /etc/zeus-host-runner /var/run/docker.sock; do if test -e "$p" || test -L "$p"; then stat --printf='path=%n type=%F owner=%U:%G mode=%a\n' -- "$p"; else printf 'path=%s absent\n' "$p"; fi; done
printf 'PATH_METADATA_END\n'
printf 'SUPERVISOR_METADATA_BEGIN\n'
if command -v systemctl >/dev/null 2>&1; then
  systemctl --version 2>/dev/null | sed -n '1p'
  systemctl list-unit-files 'umbrel*' 'docker.service' 'containerd.service' --no-legend 2>/dev/null | sed -n '1,40p'
else
  printf 'systemctl=absent\n'
fi
printf 'SUPERVISOR_METADATA_END\n'
