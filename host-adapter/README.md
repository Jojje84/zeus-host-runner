# Zeus Host Adapter — integration candidate

Purpose: provide the Host Runner a narrow host-authority boundary without giving Zeus Production or the Runner container a Docker socket, root shell, sudo, arbitrary exec, or general host access.

## Trust boundary

- Runs as a root-owned host service.
- Exposes only one Unix socket: `/run/zeus-host-adapter/adapter.sock`.
- Socket mode is `0660`, owner `root`, group is the verified Runner GID.
- Every connection is independently checked with Linux `SO_PEERCRED`; only the verified Runner UID is accepted.
- Request schema is the same exact 9-field typed request used by Host Runner.
- Unknown fields/operations, expired jobs, wrong requester, wrong candidate root/hash, duplicates and unsafe paths fail closed.
- No shell execution is used. Docker is invoked only with fixed argv for the five allowlisted operations.
- Persistent idempotency, per-change run limit, lease, crash detection and `recovery_required` are host-side as defense in depth.
- A failed mutating operation enters `recovery_required`; it is never auto-cleared by Zeus.

## Allowlisted operations

1. `candidate_preflight`
2. `build_rescue`
3. `inspect_image`
4. `run_rescue_test`
5. `cleanup_own_temp`

The adapter does not contain Production install/promote/restart, arbitrary command, `docker exec`, socket passthrough, credential reads, or secret distribution.

## Required verified bootstrap values

The service intentionally has no guessed UID/GID defaults. Bootstrap must provide root-owned `/etc/zeus-host-adapter.conf` containing verified values for:

- `ZEUS_RUNNER_UID`
- `ZEUS_RUNNER_GID`
- `ZEUS_RESCUE_UID`
- `ZEUS_RESCUE_GID`

The allowed candidate root defaults only to the already-defined V3.1 candidate root and may be overridden by the root-owned service configuration if the final locked path differs.

## Runner integration

`../integration-candidate/` contains:

- `host-backend-client.js` — bounded Unix-socket client.
- `live-adapter.js` — preserves backend status and never converts an unavailable/error backend into PASS.
- `daemon-live.js` — replacement live daemon that routes validated requests to the host adapter instead of `executeMock()`.
- `test-live-bridge.js` — real Unix-socket roundtrip test.

These files are deliberately not part of the currently locked 11-file root build context. The existing locked source remains preserved. They must first be copied into the local full candidate, tested with the existing runner/daemon/lease/readiness suites, then included in a single new manifest/re-lock because the current root daemon is a mock and cannot provide live Host Runner functionality.

## Current evidence

Local construction tests performed before publication:

- Python compile: PASS
- Host Adapter fail-closed unit tests: 8/8 PASS
- Node syntax for bridge files: PASS
- Unix-socket client roundtrip: PASS

Live host execution, real Docker operations, `SO_PEERCRED` across the final container UID mapping, systemd hardening enforcement, and Umbrel runtime remain `UNVERIFIED` until the approved host bootstrap executes them.
