import { expect, test } from "@playwright/test";

test("real Laravel and Python fixture: upload, extract, review, reload, confirm, export", async ({ page }) => {
  test.skip(process.env.LIVE_API !== "1", "Requires isolated Laravel and Python fake_service.py on 8101");
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({
    name: "synthetic.png", mimeType: "image/png",
    buffer: Buffer.concat([Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGP8//8/AwMDEwMYAAAkBgMBXaJOiAAAAABJRU5ErkJggg==", "base64"), Buffer.from(String(Date.now()))]),
  });
  await expect(page.getByRole("status")).toContainText("تم حفظ");
  await page.getByRole("button", { name: "استخراج هذه الفاتورة" }).click();
  await expect(page.getByLabel("رقم الفاتورة", { exact: true })).toHaveValue("000081", { timeout: 30000 });
  await page.getByLabel("البائع", { exact: true }).fill("البائع بعد المراجعة");
  await page.getByRole("button", { name: "حفظ مسودة" }).click();
  await expect(page.getByRole("status")).toContainText("حُفظت المسودة");
  await page.reload();
  await expect(page.getByLabel("البائع", { exact: true })).toHaveValue("البائع بعد المراجعة");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "تأكيد الفاتورة", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("تم تأكيد");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: /تنزيل Excel/ }).click();
  await (await download).saveAs("test-results/integration.xlsx");
  await page.screenshot({ path: "test-results/integration.png", fullPage: true });
});
