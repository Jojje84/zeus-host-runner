#!/usr/bin/env bash
# Read-only, bounded Umbrel host discovery; the known broken tRPC help route is excluded.
set -Eeuo pipefail
trap 'rc=$?; printf "HOST_DISCOVERY_EXIT=%s\n" "$rc"; exit "$rc"' ERR

required_tools=(getent id stat timeout awk grep sort head sed)
for tool in "${required_tools[@]}"; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf 'TOOL=%s STATUS=ABSENT\n' "$tool"
    printf 'HOST_DISCOVERY_EXIT=21\n'
    exit 21
  fi
done

printf '%s\n' 'HOST_DISCOVERY=UID-APP-MGMT-READONLY-V2'
printf '%s\n' 'SCOPE=read-only;numeric-id-facts;filtered-local-binary-help-filesystem-systemd-metadata;no-docker;no-secrets;no-mutation'
printf '%s\n' 'UNSUPPORTED_TRPC_HELP_ROUTE=NOT_INVOKED'
for tool in "${required_tools[@]}"; do
  printf 'TOOL=%s PATH=%s\n' "$tool" "$(command -v "$tool")"
done

printf '%s\n' 'ID_FACTS_BEGIN'
if passwd_record=$(getent passwd 1003 2>/dev/null); then
  passwd_uid=$(printf '%s\n' "$passwd_record" | awk -F: 'NF >= 3 && $3 == "1003" { print $3; exit }')
  if [ "$passwd_uid" = 1003 ]; then
    printf '%s\n' 'TARGET_UID_1003=FOUND UID=1003'
  else
    printf '%s\n' 'TARGET_UID_1003=UNVERIFIED'
  fi
else
  rc=$?
  if [ "$rc" -eq 2 ]; then
    printf '%s\n' 'TARGET_UID_1003=NOT_FOUND'
  else
    printf 'TARGET_UID_1003=UNVERIFIED LOOKUP_EXIT=%s\n' "$rc"
  fi
fi
if group_record=$(getent group 1003 2>/dev/null); then
  group_gid=$(printf '%s\n' "$group_record" | awk -F: 'NF >= 3 && $3 == "1003" { print $3; exit }')
  if [ "$group_gid" = 1003 ]; then
    printf '%s\n' 'TARGET_GID_1003=FOUND GID=1003'
  else
    printf '%s\n' 'TARGET_GID_1003=UNVERIFIED'
  fi
else
  rc=$?
  if [ "$rc" -eq 2 ]; then
    printf '%s\n' 'TARGET_GID_1003=NOT_FOUND'
  else
    printf 'TARGET_GID_1003=UNVERIFIED LOOKUP_EXIT=%s\n' "$rc"
  fi
fi
if id umbrel >/dev/null 2>&1; then
  id -u umbrel | awk '/^[0-9]+$/ { print "UMBREL_UID=" $0 }'
  id -g umbrel | awk '/^[0-9]+$/ { print "UMBREL_GID=" $0 }'
else
  printf '%s\n' 'UMBREL_IDENTITY=ABSENT'
fi
printf '%s\n' 'ID_FACTS_NOTE=NOT_FOUND_DOES_NOT_AUTHORIZE_OR_RESERVE_1003'
printf '%s\n' 'ID_FACTS_END'

printf '%s\n' 'UMBREL_ENTRYPOINTS_BEGIN'
for p in /usr/local/bin/umbreld /usr/bin/umbreld /usr/local/bin/umbrel /usr/bin/umbrel; do
  if [ -e "$p" ] || [ -L "$p" ]; then
    stat -Lc 'PATH=%n TYPE=%F OWNER=%U:%G MODE=%a' "$p"
    if [ -x "$p" ]; then
      if version_raw=$(timeout 5s "$p" --version 2>/dev/null); then
        version_token=$(printf '%s\n' "$version_raw" | grep -Eo 'v?[0-9]+(\.[0-9]+){1,3}([-+][0-9A-Za-z.-]+)?' | head -1 || true)
        if printf '%s\n' "$version_token" | grep -Eq '^v?[0-9]+(\.[0-9]+){1,3}([-+][0-9A-Za-z.-]+)?$'; then
          printf 'UMBREL_VERSION=%s PATH=%s\n' "$version_token" "$p"
        else
          printf 'UMBREL_VERSION=UNVERIFIED PATH=%s\n' "$p"
        fi
      else
        rc=$?
        printf 'UMBREL_VERSION=UNVERIFIED PATH=%s EXIT=%s\n' "$p" "$rc"
      fi

      if help_raw=$(timeout 5s "$p" --help 2>/dev/null); then
        capabilities=$(printf '%s\n' "$help_raw" | awk '
          {
            for (i = 1; i <= NF; i++) {
              token = tolower($i)
              gsub(/^[^a-z]+|[^a-z]+$/, "", token)
              if (token ~ /^(app|apps|install|start|restart|stop|client|store)$/) seen[token] = 1
            }
          }
          END {
            for (token in seen) print token
          }
        ' | sort -u)
        printf 'HELP_STATUS=AVAILABLE PATH=%s\n' "$p"
        if [ -n "$capabilities" ]; then
          while IFS= read -r capability; do
            [ -n "$capability" ] && printf 'HELP_CAPABILITY=%s PATH=%s\n' "$capability" "$p"
          done <<< "$capabilities"
        else
          printf 'APP_MGMT_ENTRYPOINT=UNVERIFIED PATH=%s\n' "$p"
        fi
      else
        rc=$?
        printf 'HELP_STATUS=UNVERIFIED PATH=%s EXIT=%s\n' "$p" "$rc"
        printf 'APP_MGMT_ENTRYPOINT=UNVERIFIED PATH=%s\n' "$p"
      fi
    fi
  else
    printf 'PATH=%s STATUS=ABSENT\n' "$p"
  fi
done
printf '%s\n' 'APP_MGMT_ENTRYPOINT=UNVERIFIED REASON=FILTERED_HELP_ONLY'
printf '%s\n' 'UMBREL_ENTRYPOINTS_END'

printf '%s\n' 'UMBREL_FILESYSTEM_BEGIN'
for p in /home/umbrel/umbrel /home/umbrel/umbrel/app-data /home/umbrel/umbrel/app-data/openclaw /home/umbrel/umbrel/app-data/openclaw/data; do
  if [ -e "$p" ] || [ -L "$p" ]; then
    stat -Lc 'PATH=%n TYPE=%F OWNER=%U:%G MODE=%a' "$p"
  else
    printf 'PATH=%s STATUS=ABSENT\n' "$p"
  fi
done
printf '%s\n' 'UMBREL_FILESYSTEM_END'

printf '%s\n' 'SYSTEMD_BEGIN'
if command -v systemctl >/dev/null 2>&1; then
  printf 'SYSTEMCTL_PATH=%s\n' "$(command -v systemctl)"
  systemctl --version 2>/dev/null | head -1 | sed 's/[[:cntrl:]]//g' || printf '%s\n' 'SYSTEMD_VERSION=UNVERIFIED'
  systemctl list-unit-files --type=service --no-legend --no-pager 2>/dev/null \
    | awk '$1 ~ /^(umbrel|umbreld|docker|containerd)/ { print "UNIT=" $1 " STATE=" $2 }' \
    | head -80 || printf '%s\n' 'SYSTEMD_UNITS=UNVERIFIED'
else
  printf '%s\n' 'SYSTEMCTL_STATUS=ABSENT'
fi
printf '%s\n' 'SYSTEMD_END'
printf '%s\n' 'HOST_DISCOVERY_EXIT=0'
