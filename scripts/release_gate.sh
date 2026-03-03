#!/usr/bin/env bash
set -euo pipefail

uv run ruff check .
uv run mypy .
uv run pytest -q
npm run --prefix apps/ui lint
npm run --prefix apps/ui build
npm run --prefix apps/ui test

echo "Release gate passed."
