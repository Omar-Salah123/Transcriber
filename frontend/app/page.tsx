"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  draftPayload,
  InvoiceItem,
  InvoiceRecord,
  statusLabel,
} from "@/lib/invoice";

const headerFields = [
  ["invoice_number", "رقم الفاتورة"],
  ["date_text", "التاريخ كما هو مكتوب"],
  ["seller", "البائع"],
  ["customer", "العميل"],
  ["written_total_text", "الإجمالي المكتوب"],
  ["written_total_interpreted_text", "تفسير الإجمالي (أرقام 0-9 بلا فواصل)"],
] as const;
const itemFields = [
  ["description", "الوصف"],
  ["quantity_text", "الكمية"],
  ["unit_price_text", "سعر الوحدة"],
  ["written_amount_text", "المبلغ"],
] as const;

function interpretedField(field: (typeof itemFields)[number][0]) {
  if (field === "unit_price_text") return "unit_price_interpreted_text";
  if (field === "written_amount_text") return "written_amount_interpreted_text";
  return null;
}

function itemValue(item: InvoiceItem, field: (typeof itemFields)[number][0]) {
  const interpretation = interpretedField(field);
  return (interpretation ? item[interpretation] : null) ?? item[field] ?? "";
}

function editItemValue(
  item: InvoiceItem,
  field: (typeof itemFields)[number][0],
  value: string,
): InvoiceItem {
  const interpretation = interpretedField(field);
  const next = {
    ...item,
    unresolved_fields: item.unresolved_fields.filter(
      (name) => name !== field && name !== interpretation,
    ),
  };
  if (interpretation && value === "") {
    return { ...next, [field]: null, [interpretation]: null };
  }
  if (interpretation && item[interpretation] != null) {
    return { ...next, [interpretation]: value };
  }
  return { ...next, [field]: value };
}

function retryTime(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;

  return new Intl.DateTimeFormat("ar-SA", {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export default function Home() {
  const [records, setRecords] = useState<InvoiceRecord[]>([]);
  const [draft, setDraft] = useState<InvoiceRecord | null>(null);
  const [dirty, setDirty] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("جارٍ تحميل الفواتير المحفوظة…");
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const dirtyRef = useRef(false);
  const busyRef = useRef(false);
  const activeRef = useRef<string | null>(null);
  const generation = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    if (!activeRef.current)
      activeRef.current = localStorage.getItem("activeInvoiceId");
    const before = generation.current;
    const invoices = await api<InvoiceRecord[]>("invoices");
    if (before !== generation.current || busyRef.current) return;
    setRecords(invoices);
    if (!dirtyRef.current) {
      const selected =
        invoices.find((record) => record.id === activeRef.current) ??
        invoices[0];
      if (selected) {
        activeRef.current = selected.id;
        localStorage.setItem("activeInvoiceId", selected.id);
        setDraft(selected);
      } else {
        activeRef.current = null;
        setDraft(null);
      }
    }
  }, []);

  useEffect(() => {
    let alive = true;
    void refresh()
      .then(() => {
        if (alive)
          setNotice(
            "ارفع الصور، ثم اختر استخراج لإرسالها إلى Gemini. راجع كل نتيجة قبل التأكيد.",
          );
      })
      .catch((error: Error) => {
        if (alive) setNotice(error.message);
      });
    const timer = setInterval(() => {
      void refresh().catch((error: Error) => {
        if (alive) setNotice(error.message);
      });
    }, 3000);
    const unload = (event: BeforeUnloadEvent) => {
      if (dirtyRef.current) event.preventDefault();
    };
    window.addEventListener("beforeunload", unload);
    return () => {
      alive = false;
      clearInterval(timer);
      window.removeEventListener("beforeunload", unload);
    };
  }, [refresh]);

  function select(record: InvoiceRecord) {
    if (
      dirtyRef.current &&
      !window.confirm("هناك تعديلات غير محفوظة. هل تريد تجاهلها؟")
    )
      return;
    generation.current++;
    activeRef.current = record.id;
    localStorage.setItem("activeInvoiceId", record.id);
    dirtyRef.current = false;
    setDirty(false);
    setDraft(record);
    setAcknowledged(false);
    setZoom(1);
    setRotation(0);
  }

  function edit(change: (current: InvoiceRecord) => InvoiceRecord) {
    dirtyRef.current = true;
    generation.current++;
    setDirty(true);
    setAcknowledged(false);
    setDraft((current) => (current ? change(current) : current));
  }

  async function run(action: () => Promise<void>) {
    if (busyRef.current) return;
    generation.current++;
    busyRef.current = true;
    setBusy(true);
    try {
      await action();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "تعذر إكمال العملية");
    } finally {
      busyRef.current = false;
      setBusy(false);
      generation.current++;
    }
  }

  function acceptSaved(record: InvoiceRecord) {
    dirtyRef.current = false;
    setDirty(false);
    setDraft(record);
    setAcknowledged(false);
    setRecords((current) =>
      current.map((item) => (item.id === record.id ? record : item)),
    );
  }

  async function upload(files: File[]) {
    await run(async () => {
      const added: InvoiceRecord[] = [];
      const failures: string[] = [];
      let duplicates = 0;
      for (const file of files) {
        if (
          !["image/jpeg", "image/png"].includes(file.type) ||
          file.size > 10 * 1024 * 1024
        ) {
          failures.push(file.name);
          continue;
        }
        try {
          const body = new FormData();
          body.append("image", file);
          const result = await api<{
            invoice: InvoiceRecord;
            duplicate: boolean;
          }>("invoices", { method: "POST", body });
          added.push(result.invoice);
          if (result.duplicate) duplicates++;
        } catch {
          failures.push(file.name);
        }
      }
      setRecords((current) => [
        ...new Map(
          [...current, ...added].map((record) => [record.id, record]),
        ).values(),
      ]);
      if (added.length && !dirtyRef.current) select(added[0]);
      setNotice(
        `تم حفظ ${added.length - duplicates} صورة. مكررة: ${duplicates}.${failures.length ? ` تعذر رفع: ${failures.join("، ")}. استخدم JPG أو PNG حتى 10 MiB.` : ""}`,
      );
    });
  }

  const confirmed = records.filter(
    (record) => record.status === "confirmed",
  ).length;
  const locked = busy || draft?.status === "processing";

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#workspace">
          فاتورتي <small>مراجعة الفواتير العربية</small>
        </a>
        <nav className="workflow">رفع الصور ← استخراج ← مراجعة ← تصدير</nav>
      </header>
      <section className="welcome-row">
        <div>
          <p className="eyebrow">مساحة عمل محلية</p>
          <h1>
            راجع الفاتورة، <em>ثم أكّدها.</em>
          </h1>
          <p className="subhead">
            تبقى الصور والمراجعات على جهازك. زر الاستخراج يرسل الصورة إلى
            Gemini.
          </p>
        </div>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          {draft && (
            <button
              type="button"
              className="secondary-button"
              onClick={() => window.print()}
              title="طباعة الفاتورة الحالية كملف PDF"
              style={{ padding: "12px 17px", minHeight: "44px" }}
            >
              طباعة PDF
            </button>
          )}
          <button
            className="secondary-button"
            disabled={!records.length || busy || dirty}
            style={{ padding: "12px 17px", minHeight: "44px" }}
            onClick={() =>
              void run(async () => {
                if (
                  !window.confirm(
                    `هل أنت متأكد من حذف جميع الفواتير (${records.length})؟ لا يمكن التراجع عن هذا الإجراء.`,
                  )
                )
                  return;
                const result = await api<{ deleted: number }>("invoices", {
                  method: "DELETE",
                });
                generation.current++;
                activeRef.current = null;
                localStorage.removeItem("activeInvoiceId");
                dirtyRef.current = false;
                setDirty(false);
                setDraft(null);
                setRecords([]);
                setAcknowledged(false);
                setNotice(`تم حذف ${result.deleted} فاتورة.`);
              })
            }
          >
            مسح الكل
          </button>
          <button
            className="export-button"
            disabled={!confirmed || busy || dirty}
            onClick={() =>
              void run(async () => {
                const response = await fetch("/api/exports/invoices", {
                  headers: { Accept: "application/json" },
                  cache: "no-store",
                });
                if (!response.ok)
                  throw new Error("تعذر تصدير الفواتير المؤكدة");
                const url = URL.createObjectURL(await response.blob());
                const anchor = document.createElement("a");
                anchor.href = url;
                anchor.download = "الفواتير-المؤكدة.xlsx";
                anchor.click();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
                setNotice("تم تنزيل الفواتير المؤكدة المحفوظة فقط.");
              })
            }
          >
            تنزيل Excel ({confirmed})
          </button>
        </div>
      </section>
      <section className="summary-grid">
        <article className="summary-card blue">
          <div>
            <span>إجمالي الفواتير</span>
            <strong>{records.length}</strong>
          </div>
        </article>
        <article className="summary-card amber">
          <div>
            <span>قيد المراجعة</span>
            <strong>
              {records.filter((r) => r.status === "review").length}
            </strong>
          </div>
        </article>
        <article className="summary-card green">
          <div>
            <span>مؤكدة</span>
            <strong>{confirmed}</strong>
          </div>
        </article>
      </section>
      <section className="drop-zone-wrap">
        <input
          className="sr-only"
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png"
          multiple
          onChange={(event) => {
            void upload(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
        />
        <button
          className="drop-zone"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            void upload(Array.from(event.dataTransfer.files));
          }}
        >
          <span>
            <b>أضف صور الفواتير</b>
            <small>
              اسحب الصور هنا أو اختر الملفات · JPG / PNG · حتى 10 MiB للصورة
            </small>
          </span>
          <span className="select-files">اختيار ملفات</span>
        </button>
      </section>
      <p className="notice" role="status">
        {busy ? "جارٍ تنفيذ العملية… " : ""}
        {notice}
      </p>
      {!records.length && (
        <p className="empty-review">
          لا توجد فواتير محفوظة بعد. أضف أول صورة للبدء.
        </p>
      )}
      {draft && (
        <section className="workspace" id="workspace">
          <aside className="queue-panel">
            <div className="panel-heading">
              <strong>قائمة الفواتير</strong>
              <button
                disabled={busy || dirty}
                onClick={() =>
                  void run(async () => {
                    let count = 0;
                    for (const record of records.filter(
                      (r) => r.status === "pending" || r.status === "failed",
                    )) {
                      await api(`invoices/${record.id}/extract`, {
                        method: "POST",
                      });
                      count++;
                    }
                    setNotice(`تمت جدولة ${count} فاتورة للاستخراج بالتتابع.`);
                  })
                }
              >
                استخراج الانتظار
              </button>
            </div>
            <div className="queue-list">
              {records.map((record) => (
                <button
                  disabled={busy}
                  type="button"
                  className={`queue-item ${draft.id === record.id ? "selected" : ""}`}
                  key={record.id}
                  onClick={() => select(record)}
                >
                  <span className="queue-name">
                    <b>{record.source_filename}</b>
                    <small>
                      {record.invoice_number || "بدون رقم"} ·{" "}
                      {statusLabel[record.status]}
                    </small>
                    {record.extraction_retry_at && (
                      <small>
                        إعادة المحاولة نحو{" "}
                        {retryTime(record.extraction_retry_at)}
                      </small>
                    )}
                  </span>
                </button>
              ))}
            </div>
          </aside>
          <section className="invoice-preview" aria-label="صورة الفاتورة">
            <div className="preview-heading">
              <b>{draft.source_filename}</b>
              <div className="preview-tools">
                <button
                  aria-label="تدوير الصورة"
                  onClick={() => setRotation((value) => (value + 90) % 360)}
                >
                  ↻
                </button>
                <button
                  aria-label="تكبير الصورة"
                  onClick={() => setZoom((value) => Math.min(3, value + 0.25))}
                >
                  ＋
                </button>
                <button
                  aria-label="تصغير الصورة"
                  onClick={() =>
                    setZoom((value) => Math.max(0.5, value - 0.25))
                  }
                >
                  −
                </button>
                <button
                  onClick={() => {
                    setZoom(1);
                    setRotation(0);
                  }}
                >
                  إعادة
                </button>
              </div>
            </div>
            <div className="image-viewport">
              <div
                style={{
                  width: `${zoom * 100}%`,
                  minHeight: `${zoom * 600}px`,
                }}
              >
                {/* Local Laravel source image; keep the original bytes available for review. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={draft.image_url}
                  alt="صورة الفاتورة الأصلية"
                  style={{ width: "100%", transform: `rotate(${rotation}deg)` }}
                />
              </div>
            </div>
          </section>
          <section className="review-panel">
            <div className="review-heading">
              <div>
                <p>{statusLabel[draft.status]}</p>
                <h2>راجع وصحّح البيانات</h2>
              </div>
              <span>{dirty ? "تعديلات غير محفوظة" : "محفوظة"}</span>
            </div>
            {draft.extraction_error && (
              <p className="notice">{draft.extraction_error}</p>
            )}
            {(draft.status === "pending" || draft.status === "failed") && (
              <button
                className="primary-button"
                disabled={busy || dirty}
                onClick={() =>
                  void run(async () => {
                    acceptSaved(
                      await api<InvoiceRecord>(`invoices/${draft.id}/extract`, {
                        method: "POST",
                      }),
                    );
                    setNotice(
                      "تمت جدولة الاستخراج. شغّل عامل الطابور وخدمة Python.",
                    );
                  })
                }
              >
                استخراج هذه الفاتورة
              </button>
            )}
            {draft.status === "processing" && (
              <p className="notice">
                {draft.extraction_retry_at
                  ? `أوقف Gemini الطلب مؤقتاً. ستتم إعادة المحاولة نحو الساعة ${retryTime(draft.extraction_retry_at)}.`
                  : "بانتظار العامل أو جارٍ الاستخراج. ستظهر النتيجة تلقائياً."}
              </p>
            )}
            {draft.status === "confirmed" && (
              <p className="confirmed-banner">
                أي تعديل محفوظ يعيد الفاتورة إلى المراجعة ويستبعدها من التصدير
                حتى التأكيد مجدداً.
              </p>
            )}
            <fieldset disabled={locked} className="review-fields">
              <div className="review-scroll">
                <section className="form-section">
                  <p className="notice">
                    تُعرض القيمة الرقمية المفسّرة لسعر الوحدة والمبلغ عند
                    توفرها. قارنها بالصورة الأصلية قبل التأكيد. يُحفظ النص
                    الأصلي منفصلاً.
                  </p>
                  <div className="form-grid">
                    {headerFields.map(([field, label]) => (
                      <label key={field}>
                        {label}
                        <input
                          value={draft[field] ?? ""}
                          onChange={(event) =>
                            edit((current) => ({
                              ...current,
                              [field]: event.target.value,
                              ...(field === "written_total_text"
                                ? { written_total_interpreted_text: null }
                                : {}),
                              unresolved_fields:
                                current.unresolved_fields.filter(
                                  (name) => name !== field,
                                ),
                            }))
                          }
                        />
                      </label>
                    ))}
                  </div>
                </section>
                <section className="form-section items-section">
                  <div className="section-title">
                    <span>الأصناف</span>
                    <small>{draft.items.length} سطر</small>
                  </div>
                  <div className="items-table-wrap">
                    <table className="items-table">
                      <thead>
                        <tr>
                          {itemFields.map(([field, label]) => (
                            <th key={field}>{label}</th>
                          ))}
                          <th>المحسوب المحفوظ</th>
                          <th>ملاحظات السطر</th>
                          <th>حذف</th>
                        </tr>
                      </thead>
                      <tbody>
                        {draft.items.map((item, index) => (
                          <tr key={index}>
                            {itemFields.map(([field, label]) => (
                              <td key={field}>
                                <input
                                  aria-label={`${label} السطر ${index + 1}`}
                                  value={itemValue(item, field)}
                                  onChange={(event) =>
                                    edit((current) => ({
                                      ...current,
                                      items: current.items.map((row, i) =>
                                        i === index
                                          ? editItemValue(
                                              row,
                                              field,
                                              event.target.value,
                                            )
                                          : row,
                                      ),
                                    }))
                                  }
                                />
                              </td>
                            ))}
                            <td className="calculated-cell">
                              {dirty
                                ? "احفظ للحساب"
                                : (item.calculated_amount ?? "—")}
                            </td>
                            <td>
                              <input
                                aria-label={`ملاحظات السطر ${index + 1}`}
                                value={item.review_note ?? ""}
                                onChange={(event) =>
                                  edit((current) => ({
                                    ...current,
                                    items: current.items.map((row, i) =>
                                      i === index
                                        ? {
                                            ...row,
                                            review_note: event.target.value,
                                          }
                                        : row,
                                    ),
                                  }))
                                }
                              />
                            </td>
                            <td>
                              <button
                                aria-label={`حذف السطر ${index + 1}`}
                                onClick={() =>
                                  edit((current) => ({
                                    ...current,
                                    items: current.items.filter(
                                      (_, i) => i !== index,
                                    ),
                                  }))
                                }
                              >
                                ×
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <button
                    className="add-item"
                    onClick={() =>
                      edit((current) => ({
                        ...current,
                        items: [
                          ...current.items,
                          {
                            description: null,
                            quantity_text: null,
                            unit_price_text: null,
                            unit_price_interpreted_text: null,
                            written_amount_text: null,
                            written_amount_interpreted_text: null,
                            review_note: null,
                            unresolved_fields: [],
                          } satisfies InvoiceItem,
                        ],
                      }))
                    }
                  >
                    ＋ إضافة سطر
                  </button>
                </section>
                <section className="form-section">
                  <label>
                    ملاحظات المراجع
                    <textarea
                      value={draft.review_notes ?? ""}
                      rows={2}
                      onChange={(event) =>
                        edit((current) => ({
                          ...current,
                          review_notes: event.target.value,
                        }))
                      }
                    />
                  </label>
                </section>
                {!dirty && draft.warnings.length > 0 && (
                  <section className="review-warnings">
                    <b>حقول تحتاج مراجعة أو إقراراً</b>
                    <ul>
                      {draft.warnings.map((warning, index) => (
                        <li key={index}>{warning.message}</li>
                      ))}
                    </ul>
                  </section>
                )}
              </div>
            </fieldset>
            <footer className="review-footer">
              {!dirty &&
                draft.status === "review" &&
                draft.warnings.length > 0 && (
                  <label className="acknowledgement">
                    <input
                      type="checkbox"
                      checked={acknowledged}
                      onChange={(event) =>
                        setAcknowledged(event.target.checked)
                      }
                    />
                    <span>
                      راجعت جميع الحقول الناقصة والفروق والملاحظات وأقرّ حفظها
                      كما هي.
                    </span>
                  </label>
                )}
              <div className="footer-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => window.print()}
                  title="طباعة الفاتورة الحالية كملف PDF"
                >
                  طباعة PDF
                </button>
                <button
                  className="secondary-button"
                  disabled={
                    locked ||
                    (!dirty &&
                      draft.status !== "pending" &&
                      draft.status !== "failed")
                  }
                  onClick={() =>
                    void run(async () => {
                      acceptSaved(
                        await api<InvoiceRecord>(`invoices/${draft.id}`, {
                          method: "PUT",
                          body: JSON.stringify(draftPayload(draft)),
                        }),
                      );
                      setNotice(
                        "حُفظت المسودة والحسابات. راجع التحذيرات قبل التأكيد.",
                      );
                    })
                  }
                >
                  حفظ مسودة
                </button>
                <button
                  className="confirm-button"
                  disabled={
                    locked ||
                    dirty ||
                    draft.status !== "review" ||
                    (draft.warnings.length > 0 && !acknowledged)
                  }
                  onClick={() =>
                    void run(async () => {
                      acceptSaved(
                        await api<InvoiceRecord>(
                          `invoices/${draft.id}/confirm`,
                          {
                            method: "POST",
                            body: JSON.stringify({
                              version: draft.version,
                              acknowledged,
                            }),
                          },
                        ),
                      );
                      setNotice("تم تأكيد الفاتورة وإدراجها في التصدير.");
                    })
                  }
                >
                  تأكيد الفاتورة
                </button>
              </div>
            </footer>
          </section>
        </section>
      )}
    </main>
  );
}
