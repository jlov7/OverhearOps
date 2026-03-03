# Secret Management Baseline

## Policy
- Secrets must come from environment variables or external secret stores.
- Do not commit API keys, OAuth client secrets, tokens, or database credentials.
- Production credentials must be scoped by `OVERHEAROPS_CREDENTIAL_SCOPE=prod` and use `MS_PROD_*` variables.
- Dry-run credentials must use `MS_DRYRUN_*` (or legacy `MS_*` fallback for local compatibility).

## Required Environment Contract
- OpenAI: `OPENAI_API_KEY`
- Graph dry-run: `MS_DRYRUN_TENANT_ID`, `MS_DRYRUN_CLIENT_ID`, `MS_DRYRUN_CLIENT_SECRET`
- Graph production: `MS_PROD_TENANT_ID`, `MS_PROD_CLIENT_ID`, `MS_PROD_CLIENT_SECRET`
- Security mode token map: `OVERHEAROPS_AUTH_TOKENS_JSON`

## Rotation Hooks
- Storage writes can emit per-file key metadata sidecars via:
  - `OVERHEAROPS_STORAGE_CODEC=plain`
  - `OVERHEAROPS_STORAGE_KEY_ID=<rotation-id>`
- Rotate by changing `OVERHEAROPS_STORAGE_KEY_ID`; new files receive the new key marker.

## Verification
- Run `scripts/release_gate.sh` before release.
- Security CI workflow (`.github/workflows/security.yml`) enforces SAST/dependency/secret scans.
