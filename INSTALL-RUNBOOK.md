# Host Runner candidate runbook

No installation is authorized by this candidate. The verified replacement discovery has already supplied bounded host facts; the separate UID/app-management discovery has also completed. No install command is embedded because the supported Umbrel install/activation surface remains `UNVERIFIED`; `app`/`store` help signals are not treated as an executable path. Before any install, the operator must verify the bundle hash, manifest schema, image digest, socket/auth design and backup/LKG. Install, socket/group permission and service activation require host facts and a later Jorge gate.

The current safe test is local:

```bash
node test-runner.js
```

The inactive named-session/work-queue bridge is validated locally with `node test-work-queue-bridge.js`; it is not enabled and has no scheduler, socket or host authority.

Host adapter requirements: fixed typed operation map; no shell strings; candidate prefix exactly `/home/umbrel/umbrel/app-data/openclaw/data/zeus-v31-umbrel-candidates-20260902`; no symlink/traversal; expected hash and immutable image binding; timeout/cleanup only for runner-owned resources; result with exact exit code, redacted stdout/stderr, hashes, image ID, timestamps and `UNVERIFIED` when host evidence is absent.

Every mutating host request must hold the v3.1 `CHANGE_LOCK` with lease, timeout and heartbeat. Stale or ambiguous lock state becomes `recovery_required`; resume requires verified baseline/LKG and rollback target. PRE-RESTART is a single batch; `SINGLE_RESTART_REQUIRED` is not implied by any candidate operation.
