import { expect, test } from "@playwright/test";
import type { InvoiceRecord } from "../lib/invoice";

test("Arabic review saves drafts, gates confirmation, survives reload, and reopens edits", async ({
  page,
}) => {
  let saved: InvoiceRecord = {
    id: "synthetic",
    version: 1,
    source_filename: "synthetic.png",
    status: "review",
    invoice_number: "000081",
    date_text: "٩ / ؟ / ٢٠٢٦",
    seller: "متجر تجريبي",
    customer: null,
    written_total_text: "٠٫٣",
    calculated_total: "0.3000",
    review_notes: null,
    review_acknowledged: false,
    unresolved_fields: ["customer"],
    extraction_error: null,
    image_url: "/synthetic.svg",
    items: [
      {
        description: "صنف تجريبي",
        quantity_text: "٣",
        unit_price_text: "٠٫١",
        written_amount_text: "٠٫٣",
        calculated_amount: "0.3000",
        unresolved_fields: [],
        review_note: null,
      },
    ],
    warnings: [{ field: "customer", message: "اسم العميل غير واضح" }],
  };
  let confirmations = 0;
  await page.route("**/synthetic.svg", (route) =>
    route.fulfill({
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="500" height="750"><rect width="500" height="750" fill="white"/><text x="250" y="70" text-anchor="middle" font-size="24">فاتورة تجريبية 000081</text></svg>',
    }),
  );
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/invoices") return route.fulfill({ json: [saved] });
    if (path.endsWith("/confirm")) {
      confirmations++;
      expect(request.postDataJSON().acknowledged).toBe(true);
      saved = { ...saved, status: "confirmed", review_acknowledged: true };
    } else if (request.method() === "PUT") {
      const body = request.postDataJSON();
      expect(body.items[0]).not.toHaveProperty("calculated_amount");
      saved = {
        ...saved,
        ...body,
        version: saved.version + 1,
        status: "review",
        review_acknowledged: false,
      };
    }
    await route.fulfill({ json: saved });
  });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByLabel("رقم الفاتورة", { exact: true })).toHaveValue(
    "000081",
  );
  await expect(page.getByLabel("التاريخ كما هو مكتوب")).toHaveValue(
    "٩ / ؟ / ٢٠٢٦",
  );
  const confirm = page.getByRole("button", {
    name: "تأكيد الفاتورة",
    exact: true,
  });
  await expect(confirm).toBeDisabled();
  await page.getByRole("checkbox").check();
  await page.getByLabel("البائع", { exact: true }).fill("متجر بعد المراجعة");
  await expect(confirm).toBeDisabled();
  await page.getByRole("button", { name: "حفظ مسودة" }).click();
  await expect(page.getByRole("status")).toContainText("حُفظت المسودة");
  await page.reload();
  await expect(page.getByLabel("البائع", { exact: true })).toHaveValue(
    "متجر بعد المراجعة",
  );
  await page.getByRole("button", { name: "تكبير الصورة", exact: true }).click();
  await page.getByRole("button", { name: "تدوير الصورة" }).click();
  await expect(page.getByAltText("صورة الفاتورة الأصلية")).toHaveCSS(
    "transform",
    "matrix(0, 1, -1, 0, 0, 0)",
  );
  await page.getByRole("button", { name: "إعادة", exact: true }).click();
  await page.screenshot({
    path: "test-results/arabic-review.png",
    fullPage: true,
  });
  await page.getByRole("checkbox").check();
  await confirm.click();
  await expect(page.getByRole("button", { name: /تنزيل Excel/ })).toBeEnabled();
  expect(confirmations).toBe(1);
  await page.getByLabel("رقم الفاتورة", { exact: true }).fill("000082");
  await expect(
    page.getByRole("button", { name: /تنزيل Excel/ }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "حفظ مسودة" }).click();
  await expect(page.getByRole("status")).toContainText("حُفظت المسودة");
  expect(saved.status).toBe("review");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "test-results/arabic-review-mobile.png",
    fullPage: true,
  });
});

test("polling never overwrites unsaved review text", async ({ page }) => {
  await page.route("**/api/invoices", (route) =>
    route.fulfill({
      json: [
        {
          id: "draft",
          version: 1,
          source_filename: "draft.png",
          status: "review",
          invoice_number: "000081",
          items: [],
          unresolved_fields: [],
          warnings: [],
          image_url: "",
          review_notes: null,
        },
      ],
    }),
  );
  await page.goto("/");
  await page.getByLabel("رقم الفاتورة", { exact: true }).fill("000099");
  const poll = page.waitForResponse((response) =>
    response.url().endsWith("/api/invoices"),
  );
  await poll;
  await expect(page.getByLabel("رقم الفاتورة", { exact: true })).toHaveValue(
    "000099",
  );
});

test("review shows shorthand interpretations and clears a stale suggestion after a source edit", async ({
  page,
}) => {
  const saved: InvoiceRecord = {
    id: "shorthand",
    version: 1,
    source_filename: "synthetic.png",
    status: "review",
    invoice_number: "000081",
    date_text: null,
    seller: null,
    customer: null,
    written_total_text: "١٤٠،~~~",
    written_total_interpreted_text: "140000",
    calculated_total: "140000.0000",
    review_notes: null,
    review_acknowledged: false,
    unresolved_fields: [],
    extraction_error: null,
    image_url: "",
    items: [
      {
        description: "صنف تجريبي",
        quantity_text: "٢",
        unit_price_text: "٧٠،~~~",
        unit_price_interpreted_text: "70000",
        written_amount_text: "١٤٠،~~~",
        written_amount_interpreted_text: "140000",
        calculated_amount: "140000.0000",
        unresolved_fields: [],
        review_note: null,
      },
    ],
    warnings: [
      {
        field: "items.0.unit_price_interpreted_text",
        message: "راجع تفسير اختصار الآلاف لسعر الوحدة في السطر 1",
      },
    ],
  };
  await page.route("**/api/invoices", (route) =>
    route.fulfill({ json: [saved] }),
  );
  await page.route("**/api/invoices/shorthand", async (route) => {
    const body = route.request().postDataJSON();
    expect(body.items[0].unit_price_text).toBe("٧٥،~~~");
    expect(body.items[0].unit_price_interpreted_text).toBeNull();
    await route.fulfill({ json: { ...saved, ...body, version: 2 } });
  });

  await page.goto("/");
  await expect(
    page.getByLabel("تفسير الإجمالي (أرقام 0-9 بلا فواصل)"),
  ).toHaveValue("140000");
  await expect(page.getByLabel("تفسير سعر الوحدة (0-9) السطر 1")).toHaveValue(
    "70000",
  );
  const notesWidth = await page
    .locator(".items-table th")
    .nth(7)
    .evaluate((cell) => cell.getBoundingClientRect().width);
  const deleteWidth = await page
    .locator(".items-table th")
    .nth(8)
    .evaluate((cell) => cell.getBoundingClientRect().width);
  expect(notesWidth).toBeGreaterThan(100);
  expect(deleteWidth).toBeGreaterThan(40);
  await page.getByLabel("ملاحظات السطر 1").scrollIntoViewIfNeeded();
  await expect(page.getByRole("button", { name: "حذف السطر 1" })).toBeVisible();
  await page.screenshot({
    path: "test-results/shorthand-table-end.png",
    fullPage: true,
  });
  await page.getByLabel("سعر الوحدة السطر 1", { exact: true }).fill("٧٥،~~~");
  await expect(page.getByLabel("تفسير سعر الوحدة (0-9) السطر 1")).toHaveValue(
    "",
  );
  await page.getByRole("button", { name: "حفظ مسودة" }).click();
  await expect(page.getByRole("status")).toContainText("حُفظت المسودة");
});
