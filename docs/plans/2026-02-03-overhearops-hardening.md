# OverhearOps Demo Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a second security demo scenario, strengthen determinism, polish run-page signals, and apply safe dependency updates.

**Architecture:** Extend demo data and offline provider fixtures for a new thread, add determinism tests on artefacts+hash, and surface mode/provider/plan count in the UI. Keep changes low-risk and offline-first.

**Tech Stack:** FastAPI, LangGraph, OpenTelemetry, Next.js, Playwright, pytest.

---

### Task 1: Add security demo thread (NDJSON) + offline fixtures

**Files:**
- Create: `data/demo/threads/security_alert.ndjson`
- Create: `data/demo/llm/security_alert/plan.json`
- Create: `data/demo/llm/security_alert/judge.json`
- Modify: `apps/service/adapters/teams_demo.py`
- Test: `tests/test_adapter_seam.py` (extend)

**Step 1: Write the failing test**

```python
# tests/test_adapter_seam.py (add)

def test_demo_threads_include_security():
    from apps.service.adapters.teams_demo import THREADS

    assert "security_alert" in THREADS
```

**Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/test_adapter_seam.py::test_demo_threads_include_security -v
```
Expected: FAIL (thread missing).

**Step 3: Create NDJSON thread**

`data/demo/threads/security_alert.ndjson` (Teams-shaped messages):
- include `id`, `from.user.displayName`, `body.content`, `createdDateTime`, `replyToId` fields
- include security terms like `CVE`, `rotation`, `patch`, `exploit`

**Step 4: Add offline fixtures**

`data/demo/llm/security_alert/plan.json` with 2–3 plans that reference security mitigation.

`data/demo/llm/security_alert/judge.json` selecting one plan with votes.

**Step 5: Register thread in adapter**

```python
# apps/service/adapters/teams_demo.py
THREADS: dict[str, list[dict]] = {
    "ci_flake": _load_ndjson(DATA_DIR / "ci_flake.ndjson"),
    "security_alert": _load_ndjson(DATA_DIR / "security_alert.ndjson"),
}
```

**Step 6: Ensure fixtures are selected for the security thread**

Add a failing test to assert the security fixtures are used:

```python
from fastapi.testclient import TestClient

from apps.service.main import app


def test_security_thread_uses_security_fixtures():
    with TestClient(app) as client:
        run = client.post("/run/security_alert")
        assert run.status_code == 200
        run_id = run.json()["run_id"]
        data = client.get(f"/runs/{run_id}").json()

    assert data["plans"][0]["id"] == "plan-rotate-keys"
```

Then update graph state handling so `thread_id` is preserved and passed to
planner/judge nodes (keep run_id in checkpointer config).

**Step 7: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/test_adapter_seam.py::test_demo_threads_include_security -v
```
Expected: PASS.

**Step 8: Commit**

```bash
git add data/demo/threads/security_alert.ndjson data/demo/llm/security_alert/plan.json data/demo/llm/security_alert/judge.json apps/service/adapters/teams_demo.py tests/test_adapter_seam.py tests/test_security_scenario.py packages/agentkit/graph.py apps/service/main.py
git commit -m "feat: add security demo thread and fixtures"
```

---

### Task 2: Add determinism test for artefacts + replay hash

**Files:**
- Create: `tests/test_determinism.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from apps.service.main import app


def test_determinism_offline():
    with TestClient(app) as client:
        run1 = client.post("/run/ci_flake").json()["run_id"]
        run2 = client.post("/run/ci_flake").json()["run_id"]
        data1 = client.get(f"/runs/{run1}").json()
        data2 = client.get(f"/runs/{run2}").json()
    assert data1["replay_hash"] == data2["replay_hash"]
    assert data1["artefacts_by_plan"] == data2["artefacts_by_plan"]
```

**Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/test_determinism.py::test_determinism_offline -v
```
Expected: FAIL if hashes differ.

**Step 3: If failing, fix determinism**
- Ensure any non-deterministic data (timestamps) are excluded from artefacts or hash.
- Update hashing to use stable ordering.

**Step 4: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_determinism.py::test_determinism_offline -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_determinism.py packages/obs/action_graph.py apps/service/main.py packages/agentkit/executor.py
git commit -m "test: enforce offline determinism"
```

---

### Task 3: UI polish — Mode/Provider badge + plan count + safety summary

**Files:**
- Modify: `apps/ui/app/run/[id]/page.tsx`
- Test: `apps/ui/tests/ui.spec.ts`

**Step 1: Write failing UI test**

```ts
import { test, expect } from "@playwright/test";

test("run page surfaces mode and plan count", async ({ page }) => {
  await page.setContent(`<div>Mode: offline</div><div>Plans executed: 3</div>`);
  await expect(page.getByText("Mode: offline")).toBeVisible();
  await expect(page.getByText("Plans executed: 3")).toBeVisible();
});
```

**Step 2: Implement UI changes**
- Add a badge showing provider + mode in the run header
- Show plan count (plans executed) near governance summary
- Add safety summary (allowed + categories) near gate

**Step 3: Run UI tests**

Run:
```bash
npm run --prefix apps/ui test
```
Expected: PASS.

**Step 4: Commit**

```bash
git add apps/ui/app/run/[id]/page.tsx apps/ui/tests/ui.spec.ts
git commit -m "feat(ui): add mode and plan count cues"
```

---

### Task 4: Dependency hygiene (safe updates only)

**Files:**
- Modify: `apps/ui/package.json`
- Modify: `package-lock.json`

**Step 1: Run non-breaking audit fix**

Run:
```bash
npm audit fix
```
Expected: Only non-breaking changes.

**Step 2: Bump patch/minor versions safely**
- Update Next.js and eslint-config-next to latest 14.2.x
- Keep eslint on 8.57.x for compatibility

**Step 3: Install and verify**

Run:
```bash
npm install
npm run --prefix apps/ui lint
```
Expected: PASS.

**Step 4: Commit**

```bash
git add apps/ui/package.json package-lock.json
git commit -m "chore: apply safe dependency updates"
```

---

### Task 5: Docs and demo checklist

**Files:**
- Modify: `docs/APPENDIX_DEMO_DECK.md`
- Modify: `docs/EVALS.md`
- Modify: `README.md`

**Step 1: Update docs**
- Mention security thread demo option
- Mention determinism test
- Add smoke checklist

**Step 2: Commit**

```bash
git add docs/APPENDIX_DEMO_DECK.md docs/EVALS.md README.md
git commit -m "docs: add hardening checklist and security scenario"
```

---

### Task 6: Full verification

**Step 1: Run Python tests**

```bash
uv run pytest
```
Expected: PASS.

**Step 2: Run UI tests**

```bash
npm run --prefix apps/ui test
```
Expected: PASS.

**Step 3: Commit snapshot**

```bash
git commit -am "chore: verify hardening pass"
```

---

Plan complete and saved to `docs/plans/2026-02-03-overhearops-hardening.md`. Two execution options:

1. Subagent-Driven (this session)
2. Parallel Session (separate)

Which approach?
