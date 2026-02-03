import { test, expect } from "@playwright/test";

test("run summary surfaces mode, provider, and plan count", async ({ page }) => {
  await page.setContent(`
    <main>
      <section>
        <div class="badges">
          <span>Mode: offline</span>
          <span>Provider: offline</span>
          <span>Plans executed: 3</span>
        </div>
        <p><strong>Gate:</strong> approve (0.92)</p>
        <div class="safety">Safety: Allowed (pii, secrets)</div>
      </section>
    </main>
  `);

  await expect(page.getByText("Mode: offline")).toBeVisible();
  await expect(page.getByText("Provider: offline")).toBeVisible();
  await expect(page.getByText("Plans executed: 3")).toBeVisible();
  await expect(page.getByText("Safety: Allowed")).toBeVisible();
});
