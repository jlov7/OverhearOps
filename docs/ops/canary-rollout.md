# Canary + Rollback

Use canary rollout for prompt/model config changes:

```bash
uv run python scripts/canary_rollout.py --candidate-settings /path/to/runtime_settings.json --candidate-prompts /path/to/prompt_registry.json
```

Behavior:
- Backs up active runtime settings and prompt registry.
- Applies candidates.
- Runs eval and security suites.
- Restores backups automatically on failure.
