export type InvoiceStatus =
  "pending" | "processing" | "review" | "failed" | "confirmed";
export type InvoiceItem = {
  id?: number;
  row_order?: number;
  description: string | null;
  quantity_text: string | null;
  unit_price_text: string | null;
  unit_price_interpreted_text?: string | null;
  written_amount_text: string | null;
  written_amount_interpreted_text?: string | null;
  calculated_amount?: string | null;
  unresolved_fields: string[];
  review_note: string | null;
};
export type InvoiceRecord = {
  id: string;
  version: number;
  source_filename: string;
  status: InvoiceStatus;
  invoice_number: string | null;
  date_text: string | null;
  seller: string | null;
  customer: string | null;
  written_total_text: string | null;
  written_total_interpreted_text?: string | null;
  calculated_total: string | null;
  review_notes: string | null;
  review_acknowledged: boolean;
  unresolved_fields: string[];
  extraction_error: string | null;
  image_url: string;
  items: InvoiceItem[];
  warnings: { field: string; message: string }[];
};

export const statusLabel: Record<InvoiceStatus, string> = {
  pending: "بانتظار الاستخراج",
  processing: "جارٍ الاستخراج",
  review: "للمراجعة",
  failed: "تعذر الاستخراج",
  confirmed: "مؤكدة",
};

export function draftPayload(invoice: InvoiceRecord) {
  return {
    version: invoice.version,
    invoice_number: invoice.invoice_number,
    date_text: invoice.date_text,
    seller: invoice.seller,
    customer: invoice.customer,
    written_total_text: invoice.written_total_text,
    written_total_interpreted_text: invoice.written_total_interpreted_text,
    review_notes: invoice.review_notes,
    unresolved_fields: invoice.unresolved_fields,
    items: invoice.items.map(
      ({
        description,
        quantity_text,
        unit_price_text,
        unit_price_interpreted_text,
        written_amount_text,
        written_amount_interpreted_text,
        unresolved_fields,
        review_note,
      }) => ({
        description,
        quantity_text,
        unit_price_text,
        unit_price_interpreted_text,
        written_amount_text,
        written_amount_interpreted_text,
        unresolved_fields,
        review_note,
      }),
    ),
  };
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "X-Invoice-Client": "local-review",
      ...(init.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      body.message || `تعذر الاتصال بالخدمة (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}
