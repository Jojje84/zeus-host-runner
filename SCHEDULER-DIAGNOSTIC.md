# Native scheduler diagnostic — V31-ISO-20260902-002

Observed 2026-09-02: OpenClaw `2026.7.1-2 (0790d9f)` has no `automations` CLI command. Native `cron` help exposes add/disable/edit/enable/get/list/run/runs/show/status. Local scheduler reports SQLite storage at `/data/.openclaw/state/openclaw.sqlite`, logical store path `/data/.openclaw/cron/jobs.json`, one scheduler job and `nextWakeAtMs=null`; `cron list` returns zero visible jobs and `cron get` for the historical ID is unreadable. Job enabled-state and current session binding are therefore `UNVERIFIED`, not inferred disabled.

Installed code resolves explicit `session:<key>` targets through `resolveCronSessionTargetSessionKey`; `current` resolves to `session:<key>` only when a current key is supplied, otherwise `isolated`. Agent-turn jobs are required for isolated/current/named-session targets. Historical runs timed out during setup before runner/session resolution; no new retry was made.

CLI startup also emitted a Codex plugin registration error (`openSyncKeyedStore`). Its causal impact on cron listing/get is `UNVERIFIED`; the scheduler status command still returned metadata, while list returned an empty result. No config, job, plugin or runtime mutation was performed.

Decision gap: do not enable/create a job until a supported in-session automation API or a verified persistent named-session bridge is available and job state can be read unambiguously. Any new session/tool boundary remains a single Jorge decision.
