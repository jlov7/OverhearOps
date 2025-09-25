import { test, expect } from "@playwright/test";

test("layout surfaces thread, plans, and safety panes", async ({ page }) => {
  await page.setContent(`
    <main style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem">
      <section class="section-card">
        <h2>CI Flake Thread</h2>
        <article class="adaptive-card">
          <p class="adaptive-text-bolder">CI Bot</p>
          <p>Heads up: nightly pipeline #872 failed with timeout on py312 tests.</p>
        </article>
      </section>
      <section class="section-card">
        <h2>Generate remediations</h2>
        <button type="button">Suggest Plans</button>
        <div>
          <h3>Safety</h3>
          <dl>
            <dt>Allowed</dt><dd>true</dd>
          </dl>
        </div>
        <div>
          <h3>Candidate plans</h3>
          <div class="plan-card">
            <h4>Quarantine flaky test and unblock release</h4>
            <p>Confidence: 0.62</p>
            <ul><li>Mark integration/test_artifacts as xfail</li></ul>
          </div>
        </div>
      </section>
    </main>
  `);

  await expect(page.getByRole("heading", { name: "CI Flake Thread" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Suggest Plans" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Safety" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Candidate plans" })).toBeVisible();
});
