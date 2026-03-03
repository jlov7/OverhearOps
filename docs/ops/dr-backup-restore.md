# Backup, Restore, and DR Drill

## Backup
- Command:
  - `uv run python scripts/backup_restore.py backup --output backups/overhearops-$(date +%Y%m%d-%H%M%S).tar.gz`
- Includes:
  - `runs/`
  - `overhearops.db`
  - `overhearops_queue.db`

## Restore
- Command:
  - `uv run python scripts/backup_restore.py restore --archive backups/<file>.tar.gz`
- Restore into the repo root with overwrite behavior for included paths.

## Quarterly DR Drill
1. Take fresh backup from staging.
2. Restore into isolated environment.
3. Run `scripts/release_gate.sh`.
4. Verify:
   - API health
   - queue dispatch
   - run replay hash stability
5. Record drill outcome and remediation actions.
