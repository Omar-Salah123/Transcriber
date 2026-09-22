export type InvoiceStatus = "ready" | "review" | "confirmed";

export type InvoiceItem = {
  id: string;
  description: string;
  quantity: string;
  unitPrice: string;
  writtenAmount: string;
  note: string;
};

export type InvoiceRecord = {
  id: string;
  filename: string;
  status: InvoiceStatus;
  invoiceNumber: string;
  issueDate: string;
  seller: string;
  customer: string;
  writtenTotal: string;
  reviewNote: string;
  acknowledged: boolean;
  previewUrl?: string;
  items: InvoiceItem[];
};

const ArabicDigits = "٠١٢٣٤٥٦٧٨٩";
const PersianDigits = "۰۱۲۳۴۵۶۷۸۹";

/** Turns Arabic and Persian numerals into ASCII only for calculations. */
export function normalizeNumerals(value: string): string {
  return value
    .replace(/[٠-٩]/g, (digit) => String(ArabicDigits.indexOf(digit)))
    .replace(/[۰-۹]/g, (digit) => String(PersianDigits.indexOf(digit)))
    .replace(/٬/g, "")
    .replace(/٫/g, ".")
    .trim();
}

export function parseAmount(value: string): number | null {
  const normalized = normalizeNumerals(value).replace(/[^0-9.-]/g, "");
  if (!normalized || !/^-?\d+(\.\d+)?$/.test(normalized)) {
    return null;
  }

  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

export function lineTotal(item: InvoiceItem): number | null {
  const quantity = parseAmount(item.quantity);
  const unitPrice = parseAmount(item.unitPrice);
  if (quantity === null || unitPrice === null) {
    return null;
  }
  return quantity * unitPrice;
}

export function calculatedTotal(invoice: InvoiceRecord): number | null {
  const totals = invoice.items.map(lineTotal);
  const definedTotals = totals.filter((total): total is number => total !== null);
  if (definedTotals.length !== totals.length) {
    return null;
  }
  return definedTotals.reduce((sum, total) => sum + total, 0);
}

export function hasReviewWarnings(invoice: InvoiceRecord): boolean {
  return (
    !invoice.invoiceNumber.trim() ||
    !invoice.customer.trim() ||
    !invoice.writtenTotal.trim() ||
    invoice.items.some(
      (item) =>
        !item.description.trim() ||
        !item.quantity.trim() ||
        !item.unitPrice.trim(),
    )
  );
}
