# Minimal Host Runner adapter design

Preferred shape: one host-supervised, root-owned broker process with a private Unix socket. Zeus receives no shell, sudo, Docker socket or root. The broker accepts only `runner-schema.json`, checks candidate prefix/hash, nonce/expiry, idempotency and lease state, and maps each enum to one fixed implementation. It returns structured results and never forwards arbitrary strings. The candidate prefix is exactly `/home/umbrel/umbrel/app-data/openclaw/data/zeus-v31-umbrel-candidates-20260902`.

The broker must not use Docker CLI shell. If Docker is required, it uses a fixed Docker API client internally and exposes only the five allowlisted operations. The Docker socket is not mounted into Production; it is reachable only by the broker. Host discovery observed the socket as `root:docker` mode `660`, systemd/containerd/docker presence, and the candidate app-data ownership. The broker service identity, private transport ownership/mode, supervisor unit and any permission to use Docker remain design/approval questions; the prior `umbreld client … --help` attempt is a known CLI incompatibility.

Recommended first deployment is read-only `candidate_preflight` and `inspect_image`. Build/run/cleanup remain disabled until confinement, fixed API map, resource limits, audit destination and LKG/rollback behavior are verified. No new credential is needed for a Unix socket, but any container group/mount or host service permission is a host mutation.

Rollback: stop/disable the new broker, remove only its own socket/state/service files, verify Production mounts and permissions are unchanged, and retain audit. Ambiguous state becomes `recovery_required`; never blind-retry or promote.
