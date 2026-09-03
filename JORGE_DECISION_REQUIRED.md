# JORGE_DECISION_REQUIRED — Zeus Host Runner (prepared, inactive)

Change: `V31-ISO-20260902-002`  |  Candidate: `zeus-host-runner` 0.1.0

## Current evidence and unresolved gate

Host OBSERVED: `/usr/local/bin/umbreld`, `/usr/bin/systemctl` and `/usr/bin/docker` exist; systemd is `257.9-1~deb13u1`; `containerd.service` and `docker.service` are enabled; Umbrel services are present. Umbrel root `/home/umbrel/umbrel` is `root:root` `755`; app-data, OpenClaw and OpenClaw data are `umbrel:umbrel` `755`; Docker socket `/var/run/docker.sock` is `root:docker` `660`; no Runner paths exist. The operator identity is `umbrel` UID/GID `1000:1000`, not a member of `docker` (sudo membership is OBSERVED but is not requested for Zeus). The extended discovery then stopped at `umbreld client … --help` with a tRPC `TypeError`; no mutation occurred. Its causal impact on service metadata is now bounded to the unsupported help path; install API semantics remain `UNVERIFIED`.

The replacement script `HOST-DISCOVERY-REPLACEMENT-MOBILE.sh` passed host execution with `HOST_DISCOVERY_EXIT=0`, and its no-mutation/no-secret/no-Docker markers were observed. Host tool and supervisor presence, existing identities, candidate paths and Docker-socket metadata are therefore no longer UNVERIFIED. Supported Umbrel install schema/API, Runner runtime identity, typed transport/socket ownership, Runner state/audit ownership, and permission to grant any Docker authority remain UNVERIFIED.

The separate bounded UID/app-management discovery then completed with `HOST_DISCOVERY_EXIT=0` and `HOST_DISCOVERY_WRAPPER_EXIT=0`. It observed `TARGET_UID_1003=NOT_FOUND`, `TARGET_GID_1003=NOT_FOUND`, `UMBREL_UID=1000` and `UMBREL_GID=1000`. This is lookup evidence only: it does not reserve, authorize or approve creation of `1003:1003`. The `umbreld --version` probe returned exit `1`, so the installed Umbrel version is `UNVERIFIED`. Filtered help exposed only capability signals `app` and `store`; the supported install/activation entrypoint remains `UNVERIFIED`.

## Requested decision (only after replacement discovery)

Approve or reject one bounded host installation of the separately packaged Runner. Approval must cover all items below as one decision; no automatic activation follows.

1. Allocate one dedicated Runner UID/GID using the host's supported identity mechanism. The numeric values are runtime parameters, never hardcoded: bootstrap must check both are absent, create/reserve them atomically, re-query the resulting identity, and stop on collision, ambiguity or mismatch. Use internal network only, read-only rootfs, `cap_drop: ALL`, `no-new-privileges`, bounded CPU/memory/PIDs, and state limited to `/runner-state`.
2. Permit one local typed request/response transport from Zeus Production to Runner. Recommended: a host-supervised Unix socket with an explicit socket path, owner/mode and no network listener. No new secret is required by this candidate; if the selected transport needs a secret, stop and issue a new decision.
3. Decide whether to provide Runner a Docker API capability. Recommended initial choice: *no socket*; keep build/inspect/run operations `UNVERIFIED` until a narrower host mechanism exists. If a Docker socket is approved, it must be mounted only into Runner, with a dedicated identity/group, fixed Docker API operation map, no shell and no `docker exec`; Production Zeus must never receive it. This is a high-residual-risk exception.
4. Permit only the typed schema and operation allowlist in `runner-schema.json` and `operations.allowlist.json`. No install/promote/restart-Production operation.

## Host-live acceptance tests

The operator must verify bundle hash, app identity, UID/GID, socket ownership/mode, mounts, network, caps, rootfs, resource limits, and audit output. Then run the typed preflight, image inspect and Rescue-test operations. Every result must include exact exit code, allowlisted stdout/stderr, artifact hashes and immutable image identity. Any ambiguity is `UNVERIFIED` and stops.

Rollback: disable/uninstall only the newly installed Runner, remove only Runner-owned state/temp artifacts, verify Production state unchanged, and retain audit/LKG. No Production restart or promotion is included.

## Current boundary

The candidate has no host socket, credential, service or Docker access. Local fake-backend tests prove protocol and fail-closed behavior only; they do not prove host trust separation, runtime enforcement, restore, or supervisor health.

## Chosen bootstrap/install route

Use one Umbrel custom-app package (`umbrel-app.yml` plus `docker-compose.yml`) placed under the observed app-data tree and installed through the host's supported Umbrel app-management path. Do not create a standalone hand-written systemd unit as the primary service path. Official Umbrel app documentation confirms `manifestVersion: 1.1`, app manifests, Compose services, digest-pinned images and per-service `user:` declarations; it does not document the `umbreld client …` RPC install command used in the failed discovery. Therefore the exact host-side install API/UI action remains `UNVERIFIED` until the operator's supported app-management surface accepts the package.

The exact proposed values are:

- app id: `zeus-host-runner`
- service identity: `RUNNER_UID:RUNNER_GID`, allocated and re-verified during bootstrap; observed `1003` absence is not a reservation
- state: `/var/lib/zeus-host-runner`, owner `root:RUNNER_GID`, mode `0770`
- audit: `/var/log/zeus-host-runner`, owner `root:RUNNER_GID`, mode `0770`; files mode `0640`
- socket directory: `/run/zeus-host-runner`, owner `root:RUNNER_GID`, mode `0770`
- socket: `/run/zeus-host-runner/runner.sock`, owner `RUNNER_UID:RUNNER_GID`, mode `0660`
- no TCP listener, no published port, no Docker socket mount
- container: read-only rootfs, `cap_drop: ALL`, `no-new-privileges`, internal-only network, bounded CPU/memory/PIDs, only `/runner-state` writable

The socket path and ownership are a concrete parameterized proposal, not host evidence. Cross-container bind-mount support and Production's numeric group mapping must be verified before activation; if unsupported, the package fails closed and is not installed. The local daemon candidate now exists and has isolated bind/connect and state/audit tests; the unauthorized UID test remains `UNVERIFIED` because this container cannot perform the UID switch.

## Single approval scope

One approval must cover creation of the dedicated identity, Runner-owned host directories, one Umbrel custom-app installation, one local typed socket bind and Runner activation. It explicitly excludes Docker-socket access, arbitrary shell/root, credentials, external services, Production mounts except the typed socket, Production restart, promotion and canary.

## Official reference evidence

- `https://github.com/getumbrel/umbrel-apps/blob/master/README.md`
- `https://github.com/getumbrel/umbrel-apps/blob/master/bitcoin/umbrel-app.yml`
- `https://github.com/getumbrel/umbrel-apps/blob/master/bitcoin/docker-compose.yml`

## Candidate build and runtime artifacts

`Dockerfile`, `BUILD-METADATA.json`, `daemon.js`, `docker-compose.yml` and `umbrel-app.yml` are present. Build is local-context-only and must use `--pull=false`; the base image digest must be read from the host before build, and the resulting image ID plus RepoDigest must replace the candidate's `UNVERIFIED` binding. No floating tag is an identity.

The daemon writes only to `/runner-state` and `/runner-audit`, creates only the Runner-owned Unix socket, accepts newline-delimited JSON bounded to 64 KiB, audits every result and returns `FAIL`/`UNVERIFIED` on malformed, denied, unavailable or ambiguous work. It never invokes Docker or an arbitrary command. The Compose healthcheck invokes `/app/healthcheck.js`, performs a bounded non-mutating liveness request, validates the exact response and never opens the mutation gate; bind mounts, ownership and restart behavior remain host-runtime tests.

`BUILD-OPERATOR.sh` is the complete bounded build proposal. It verifies the candidate manifest, stages only the allowlisted context into a fresh `umask 077` `mktemp` directory, asserts a previously absent iidfile, records the locally available base-image inspection, builds with `--pull=false`, stops on any non-zero build, validates the iidfile as an image ID, and inspects exactly that ID. It retains the private work directory for evidence and has no tag fallback. The script is inactive and has not been run here.

## Single host bootstrap gate

Jorge's one approval may authorize only this ordered host sequence: (1) verify the candidate root is the exact non-symlink path and run `sha256sum -c ARTIFACT-HASHES.sha256`; (2) allocate a dedicated UID/GID through the supported host identity mechanism, with pre/post collision and identity checks; (3) create only Runner state, audit and socket directories owned by `root:RUNNER_GID` mode `0770`; (4) export the verified numeric values to the inactive `BUILD-OPERATOR.sh`, which must pass them as build args; (5) require base-image evidence, context-manifest hash, `BUILD_RESULT=PASS`, `IMAGE_ID` and exact `INSPECTED_ID`; (6) bind that immutable image ID, never its tag, into the custom-app package; (7) use only the host's supported Umbrel custom-app management surface to install the package; (8) verify the service identity, read-only rootfs, non-privileged caps, no-new-privileges, internal-only network, bounded 0.25 CPU/128 MiB/64 PIDs, and only the three declared bind mounts; (9) verify socket liveness, readiness, audit and state paths; (10) run only typed negative tests and `candidate_preflight` before any Docker-capable operation. Any allocation, identity, path, install-surface or runtime ambiguity stops without activation.

The private build `WORK` directory and `build-evidence.txt` are retained for review and correlation-ID binding. No automatic cleanup is performed. Any later cleanup is a separate, explicitly bounded destructive action restricted to that exact generated `/tmp/zeus-host-runner-build.<RUN_ID>.*` directory after evidence export; it is not part of rollback. Rollback disables/uninstalls only the new Runner and preserves audit, build evidence, iidfile and historical correlation IDs.

## Liveness versus readiness

`healthcheck.js` is liveness only: it performs a bounded Unix-socket request, requires an exact non-mutating response, and returns `0` only for `liveness=PASS` with `mutation_gate=false`. Stale socket, connect failure, timeout and malformed response return `111`, `124` and `65` respectively. It never writes state/audit and never starts recovery.

`readiness.js` is a separate pure evaluator. It returns `0` only when liveness, socket/state/audit path validity, immutable image-ID binding and policy clarity are all present. It returns `10` for liveness failure, `11` for invalid paths, `12` for `recovery_required`, `13` for an unbound image and `14` for policy ambiguity. Readiness never sets `mutation_gate=true`; a healthy process cannot authorize a mutating operation. Recovery requires a separately verified baseline/LKG and rollback target.

## Socket and client boundary

The candidate socket is `/run/zeus-host-runner/runner.sock`, with a runtime-allocated host parent `root:RUNNER_GID` mode `0770` and socket `RUNNER_UID:RUNNER_GID` mode `0660`; state and audit parents are likewise `root:RUNNER_GID` mode `0770`, with files mode `0640`. This is narrow group-based filesystem authorization, not payload authentication. The daemon does not claim `SO_PEERCRED`; actual cross-container peer credentials, numeric group mapping and Production bind-mount isolation remain `UNVERIFIED` and must fail closed if unavailable. No Production Docker-socket mount is permitted.

## Immutable build binding

The host operator must verify the allowlisted context and its manifest, stage and re-hash the copied context, inspect the locally available base image without pulling, build with `--pull=false` and a newly absent unique `--iidfile`, then inspect exactly the `sha256:<64hex>` ID read from that file. A non-zero build, missing/invalid iidfile, inspect error or ID mismatch stops before any image reference is updated. The resulting image ID and RepoDigest are recorded separately; the tag is never identity. Each run binds evidence to `RUN_ID`, the post-copy context-manifest hash and the iidfile path; its private work directory is retained. No build, pull or run is performed by this candidate turn.

## Read-only install-path investigation (2026-09-03)

FACTUAL_STATE: The OpenClaw application container reports version `2026.7.1-2` and Node `v22.23.1`. Inside this container `/home/umbrel/umbrel` and `/usr/local/bin/umbreld` are absent. No local OpenClaw/Umbrel documentation or source available in the container exposes a custom-app install RPC or activation command. The host-side discovery already observed `/usr/local/bin/umbreld`, but the `umbreld client ... --help` path failed with the recorded tRPC `TypeError` and is not reused.

EVIDENCE: The current official `getumbrel/umbrel-apps` README says its packages are consumed by umbrelOS and the current official Bitcoin package demonstrates `manifestVersion: 1.1`, Compose-backed services and package metadata. These sources do not document a supported host-side custom-app installation command or prove that this candidate package is accepted by this Umbrel host. References: `https://github.com/getumbrel/umbrel-apps/blob/master/README.md`, `https://github.com/getumbrel/umbrel-apps/blob/master/bitcoin/umbrel-app.yml`, `https://github.com/getumbrel/umbrel-apps/blob/master/bitcoin/docker-compose.yml`.

OPEN_ISSUES: `COMMUNITY_STORE_MECHANISM=VERIFIED` for the documented URL-based Community App Stores UI flow, but `LOCAL_FILESYSTEM_APP_IMPORT=UNVERIFIED` and `CUSTOM_APP_ENTRYPOINT=UNVERIFIED` for this local/hashbound candidate. The candidate Runner UID/GID has `NOT_FOUND` lookup evidence for numeric `1003:1003` but still requires a final collision check and explicit creation decision. Live base-image digest, final image ID/RepoDigest, socket peer authentication, cross-container bind behavior, runtime health and live rollback remain `UNVERIFIED`. No design value is promoted to host fact.

NEXT_ACTION: No generic App Store observation is required. Local candidate control is complete: `umbrel-app.yml`/Compose package shape is locally present, but no immutable store URL/source binding exists in the candidate. `COMMUNITY_STORE_MECHANISM=VERIFIED`; `LOCAL_FILESYSTEM_APP_IMPORT=UNVERIFIED`; `CUSTOM_APP_ENTRYPOINT=UNVERIFIED`. Any store addition, push/publication, external repository or host mutation requires a separate decision.

## First mutation, backup, post-check and rollback

The first permitted mutation is identity allocation through the host-supported mechanism, only after a backup of the Runner decision/evidence references and a final read-only collision check. The allocator must return numeric `RUNNER_UID` and `RUNNER_GID`, re-query both immediately, and stop before directory creation if either value is ambiguous, already present, privileged/reserved by policy, or differs between the identity database and the returned values. No Docker call or service activation occurs in this step.

Only after identity verification may the operator create `/var/lib/zeus-host-runner`, `/var/log/zeus-host-runner` and `/run/zeus-host-runner`, each `root:RUNNER_GID` mode `0770`; the socket is created later by the Runner as `RUNNER_UID:RUNNER_GID` mode `0660`. Post-checks must prove exact owner/mode/path, absence of extra mounts/listeners, and unchanged Production state. If any check fails, stop and retain non-secret evidence with the correlation ID. Rollback disables only the new Runner artifacts and preserves audit, build evidence and historical correlation IDs; deletion of persistent state/audit requires a separate destructive decision.

## Baseline and image-before-start rule

Before any permanent mutation, record a verified baseline of the candidate app-data path, existing service/container list, mounts, networks, Runner paths and Production state, and create a separately verified backup of all Runner decision/evidence references needed for recovery. Do not overwrite or delete existing objects. If identity creation succeeds but path creation fails, retain the identity and evidence for explicit reconciliation; do not guess or reuse it. If any path is created and a later step fails, stop activation, preserve audit/evidence, and remove only newly created empty Runner paths after ownership and provenance are verified; identity deletion is separate and never automatic.

The built image's exact `IMAGE_ID` from the same successful build's fresh iidfile, plus separately recorded RepoDigest, must be verified and bound into the final app configuration before the first Runner start. A tag, later inspect, health result or runtime observation cannot substitute for this binding. If image binding, digest evidence or configuration substitution is incomplete, the Runner must not start.

EXECUTION_RESULT: Local and official investigation complete with no mutation. Alternative B applies: the exact host installation path cannot be belayed from available local/runtime evidence. The existing decision package remains preparation-only; no new RPC or topology is inferred.

## Completed discovery and single remaining read-only identification gate

`HOST-DISCOVERY-UID-APP-MGMT-MOBILE.sh` was run exactly once from its hash-preflighted host path and returned `HOST_DISCOVERY_EXIT=0` and `HOST_DISCOVERY_WRAPPER_EXIT=0`. Its SHA-256 is `e498718d832acdc2e0b52f514163cf9557c42638d69096909e0a5810129971ec`. It is completed evidence, not the next action.

The documented third-party surface is `App Store → … → Community App Stores → [store URL] → Add`, followed by the normal App Store flow; this is `COMMUNITY_STORE_MECHANISM=VERIFIED` from Umbrel support. Adding a store is a mutation and is out of scope. For this candidate, local filesystem import is `UNVERIFIED`: the local package files do not prove a supported direct import or immutable source binding. No local/custom entrypoint is inferred; record `LOCAL_FILESYSTEM_APP_IMPORT=UNVERIFIED` and `CUSTOM_APP_ENTRYPOINT=UNVERIFIED` until a separately approved store source exists. Portainer is not a fallback.

## Local community-store candidate

The local-only wrapper is under `community-store-candidate/`: store ID `zeus`, app ID `zeus-host-runner`, and app-local `umbrel-app.yml` plus `docker-compose.yml` and hashbound build/runtime files. Static checks prove the official store shape, app-ID prefix, relative build context, required dynamic UID/GID parameters, no URL/publication/Docker-socket/secret patterns, and exact source binding to the prior candidate manifest snapshot `7576857c51b5d63a71dd64c6e108f4a65e3660c74dc8c03e0442305792c2140e`. This is `COMMUNITY_STORE_PACKAGE=TESTED_IN_LAB/VERIFIED_STATIC` only. `STORE_URL=UNVERIFIED/ABSENT`, `LOCAL_FILESYSTEM_APP_IMPORT=UNVERIFIED`, and no store is added or published. The wrapper does not install, start or invoke Docker.

### Exact operator observation — no invocation

Open the Umbrel web UI and select only the already-visible `App Store`/`Apps` navigation entry. Inspect whether a community/custom app-store source is already listed and inspect only visible non-mutating source/detail/documentation labels; do not add or configure a source. Do not select `Install`, `Add`, `Save`, `Apply`, `Start`, `Restart`, `Update`, `Remove` or any equivalent control. Report only the defined template below. Do not infer a local/custom API, schema or action from labels alone; record `CUSTOM_APP_ENTRYPOINT=UNVERIFIED` unless same-host documentation/detail explicitly states it.

Evidence level: `CUSTOM_SOURCE=OBSERVED|ABSENT`, `CUSTOM_SURFACE_LABEL`, `UI_ROUTE`, menu labels and action labels are `OBSERVED` only. They may be marked `VERIFIED` for local/custom handling only when a non-mutating same-host detail/documentation view explicitly states the concrete mechanism and action/schema; otherwise `CUSTOM_APP_ENTRYPOINT=UNVERIFIED`. Report exactly: `CUSTOM_SOURCE=OBSERVED|ABSENT`, `UI_SURFACE_LABEL=...`, `UI_ROUTE=...`, `VISIBLE_ACTION_LABELS=...`, `DOC_MECHANISM=...|NONE`, `CUSTOM_APP_ENTRYPOINT=OBSERVED|VERIFIED|UNVERIFIED`. Do not provide screenshots unless needed and never provide secrets.

The script answers only these unresolved factual questions:

- `TARGET_UID_1003` / `TARGET_GID_1003`: whether numeric IDs are found, not found, or lookup-unverified. Raw passwd/group records, passwords and membership lists are never emitted. `NOT_FOUND` does not reserve or authorize the value.
- `UMBREL_VERSION`: one semver-like token from a bounded `--version` probe, otherwise `UNVERIFIED`; raw version text is never emitted.
- `HELP_CAPABILITY`: only exact allowlisted words (`app`, `apps`, `install`, `start`, `restart`, `stop`, `client`, `store`) extracted from bounded top-level help. It does not invoke a client subcommand. `APP_MGMT_ENTRYPOINT=UNVERIFIED` remains explicit because filtered help is not proof of a supported install method.
- `PATH`, `UNIT`, and `SYSTEMD_*`: metadata-only evidence for the discovered local binary paths, observed Umbrel data paths, and relevant service-unit names/states.

No source/configuration content, environment, labels, credentials, token values, Docker operation, service operation, permission change or file write is in scope. The known-broken tRPC help route is not invoked.

The exact one-line wrapper is:

`S=/home/umbrel/umbrel/app-data/openclaw/data/zeus-host-runner-candidate-20260902/HOST-DISCOVERY-UID-APP-MGMT-MOBILE.sh; E=e498718d832acdc2e0b52f514163cf9557c42638d69096909e0a5810129971ec; set -u -o pipefail; test -f "$S" && test ! -L "$S" || { echo HOST_PREFLIGHT_EXIT=20; exit 20; }; printf '%s  %s\n' "$E" "$S" | sha256sum -c - || { echo HOST_PREFLIGHT_EXIT=22; exit 22; }; set +e; bash "$S"; R=$?; set -e; echo HOST_DISCOVERY_WRAPPER_EXIT=$R; exit "$R"`

Exit matrix: wrapper `20` = missing/symlink; wrapper `22` = hash mismatch; script `21` = mandatory read-only tool absent; script `0` = collection completed. Any other script exit is preserved as `HOST_DISCOVERY_WRAPPER_EXIT` and means the corresponding fact remains `UNVERIFIED`.

Return only the defined metadata lines: `HOST_*`, `TARGET_*`, `UMBREL_VERSION=*`, `HELP_*`, `APP_MGMT_*`, `PATH=*`, `TOOL=*`, `UNIT=*`, `SYSTEMD_*`, and `ID_FACTS_*`. Do not return any unexpected or sensitive output.
