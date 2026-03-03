import { test, expect } from "@playwright/test";

test("run summary surfaces mode, provider, and plan count", async ({ page }) => {
  const runId = "playwright-run";

  await page.route(/\/runs\/[^/]+\/graphs\.json$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        action_graph: {
          nodes: [
            { id: "n1", label: "overhear", trace_id: "trace-1", t0: 1, t1: 2, attrs: { "token.approx_in": 10, "token.approx_out": 20 } },
            { id: "n2", label: "ship", trace_id: "trace-1", t0: 3, t1: 4, attrs: { "token.approx_in": 8, "token.approx_out": 7 } },
          ],
          edges: [{ source: "n1", target: "n2" }],
        },
        component_graph: { nodes: [], edges: [] },
      }),
    });
  });

  await page.route(/\/runs\/[^/]+$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: runId,
        thread_id: "ci_flake",
        mode: "offline",
        provider: "offline",
        replay_hash: "abc123",
        verdict: {
          winner_plan_id: "plan-timeout",
          action: "approve",
          certainty: 1,
          rationale: "Selected for reliability",
          uncertainty: "low",
          winner: { plan: { id: "plan-timeout", title: "Extend timeout", confidence: 0.77, hypothesis: "Timeout issue", steps: ["Increase timeout"] } },
        },
        gate: { action: "approve", certainty: 1 },
        plans: [
          { id: "plan-timeout", title: "Extend timeout", confidence: 0.77, blast_radius: "Low", hypothesis: "Timeout issue", steps: ["Increase timeout"] },
          { id: "plan-quarantine", title: "Quarantine test", confidence: 0.52, blast_radius: "Medium", hypothesis: "Flaky test", steps: ["Mark xfail"] },
        ],
        artefacts: {
          safety: {
            allowed: true,
            categories: [],
            justification: "No policy violations detected",
          },
          pr_diff: "diff --git a/foo b/foo",
          jira: { summary: "Issue" },
        },
      }),
    });
  });

  await page.goto(`/run/${runId}`);

  await expect(page.getByText("Mode: offline")).toBeVisible();
  await expect(page.getByText("Provider: offline")).toBeVisible();
  await expect(page.getByText("Plans executed: 2")).toBeVisible();
  await expect(page.getByText("Safety", { exact: true })).toBeVisible();
});

test("history page supports compare controls", async ({ page }) => {
  await page.route(/\/runs\/history(\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        count: 2,
        items: [
          {
            run_id: "run-a",
            thread_id: "ci_flake",
            status: "succeeded",
            winner_plan_id: "plan-timeout",
            action: "approve",
            updated_at_ms: Date.now(),
          },
          {
            run_id: "run-b",
            thread_id: "security_alert",
            status: "succeeded",
            winner_plan_id: "plan-rotate-keys",
            action: "approve",
            updated_at_ms: Date.now(),
          },
        ],
      }),
    });
  });
  await page.route(/\/runs\/compare(\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        diff: {
          thread_id: { left: "ci_flake", right: "security_alert" },
        },
      }),
    });
  });
  await page.goto("/history");
  await expect(page.getByRole("heading", { name: "Run History" })).toBeVisible();
  await expect(page.getByRole("link", { name: "run-a" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Compare Runs" })).toBeVisible();
});

test("admin page renders editors", async ({ page }) => {
  const payload = { feature_flags: { run_execution_enabled: true } };
  await page.route(/\/admin\/settings$/, async (route) => {
    if (route.request().method() === "PUT") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) });
  });
  await page.route(/\/admin\/prompts$/, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ tasks: {} }) });
  });
  await page.route(/\/admin\/policies$/, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ shipping: {} }) });
  });
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Admin" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Prompts" })).toBeVisible();
});
