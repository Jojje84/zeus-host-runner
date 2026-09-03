# Zeus Host Runner candidate

Trust boundary: Production submits typed JSON; Runner validates schema, path, hash, expiry and idempotency; a future host adapter executes fixed operations only. Builder cannot modify policy, audit, LKG or evaluator state. Candidate source prefix is exactly `/home/umbrel/umbrel/app-data/openclaw/data/zeus-v31-umbrel-candidates-20260902`.

Denied by design: arbitrary shell, arbitrary Docker API, docker exec, Production install/promote/restart, credentials, registry push, network egress and socket access from Production.

Authentication: current candidate has no secret and is not installable as an authority. Preferred narrow mechanism is a host-supervised Unix socket/request queue with ownership and mode enforced by the operator. Any new cross-container credential or socket/group permission is a separate `JORGE_DECISION_REQUIRED` gate.

Residual risk: a Docker socket would be high authority even behind a broker; it is absent from this candidate. A future adapter must use a fixed argv/API operation map, separate UID, no shell, bounded resources and an audit-only result channel.
