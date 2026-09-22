"use client";

import { ChangeEvent, DragEvent, useMemo, useRef, useState } from "react";

import {
  calculatedTotal,
  hasReviewWarnings,
  lineTotal,
  type InvoiceItem,
  type InvoiceRecord,
} from "@/lib/invoice";
import { createConfirmedWorkbook } from "@/lib/workbook";

const demoInvoice: InvoiceRecord = {
  id: "INV-00023",
  filename: "فاتورة-0023.jpg",
  status: "review",
  invoiceNumber: "0023",
  issueDate: "2026-09-18",
  seller: "مؤسسة النور للتوريدات",
  customer: "شركة البناء الحديث",
  writtenTotal: "7150",
  reviewNote: "راجِع اسم العميل مع الصورة قبل التأكيد.",
  acknowledged: false,
  items: [
    {
      id: "item-1",
      description: "أسمنت أبيض 50 كجم",
      quantity: "3",
      unitPrice: "850",
      writtenAmount: "2550",
      note: "",
    },
    {
      id: "item-2",
      description: "رمل ناعم مغسول",
      quantity: "2",
      unitPrice: "2300",
      writtenAmount: "4600",
      note: "",
    },
  ],
};

const statusLabel = {
  ready: "بانتظار الاستخراج",
  review: "تحتاج مراجعة",
  confirmed: "تم التأكيد",
} as const;

function formatMoney(value: number | null): string {
  if (value === null) return "—";
  return new Intl.NumberFormat("ar-EG", { maximumFractionDigits: 2 }).format(value);
}

function newItem(): InvoiceItem {
  return {
    id: `item-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    description: "",
    quantity: "",
    unitPrice: "",
    writtenAmount: "",
    note: "",
  };
}

function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  if (name === "sparkles") return <svg {...common}><path d="m12 3-1.1 4.1L7 8.2l3.9 1.1L12 13l1.1-3.7L17 8.2l-3.9-1.1L12 3Z" /><path d="m19 14-.7 2.3L16 17l2.3.7L19 20l.7-2.3L22 17l-2.3-.7L19 14Z" /><path d="m5 15-.7 2.3L2 18l2.3.7L5 21l.7-2.3L8 18l-2.3-.7L5 15Z" /></svg>;
  if (name === "upload") return <svg {...common}><path d="M12 16V4" /><path d="m7 9 5-5 5 5" /><path d="M5 20h14" /></svg>;
  if (name === "file") return <svg {...common}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6" /><path d="M8 13h8M8 17h5" /></svg>;
  if (name === "check") return <svg {...common}><path d="m5 12 4 4L19 6" /></svg>;
  if (name === "download") return <svg {...common}><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 21h14" /></svg>;
  if (name === "plus") return <svg {...common}><path d="M12 5v14M5 12h14" /></svg>;
  if (name === "trash") return <svg {...common}><path d="M4 7h16M10 11v6M14 11v6M9 7l1-3h4l1 3M6 7l1 14h10l1-14" /></svg>;
  if (name === "arrow") return <svg {...common}><path d="M5 12h14M13 6l6 6-6 6" /></svg>;
  if (name === "chevron") return <svg {...common}><path d="m9 18 6-6-6-6" /></svg>;
  if (name === "rotate") return <svg {...common}><path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v5h5" /></svg>;
  return <svg {...common}><circle cx="12" cy="12" r="8" /><path d="M12 8v4M12 16h.01" /></svg>;
}

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [records, setRecords] = useState<InvoiceRecord[]>([demoInvoice]);
  const [activeId, setActiveId] = useState(demoInvoice.id);
  const [notice, setNotice] = useState("هذه واجهة المراجعة. لا يتم إرسال أي صورة إلى مزود ذكاء اصطناعي من هذه الصفحة.");
  const [isDragging, setIsDragging] = useState(false);

  const active = records.find((record) => record.id === activeId) ?? records[0];
  const confirmed = useMemo(() => records.filter((record) => record.status === "confirmed"), [records]);
  const reviewCount = records.filter((record) => record.status === "review").length;
  const waitingCount = records.filter((record) => record.status === "ready").length;
  const requiresAcknowledgement = active ? hasReviewWarnings(active) || Boolean(active.reviewNote.trim()) : false;

  function updateActive(updater: (record: InvoiceRecord) => InvoiceRecord) {
    if (!active) return;
    setRecords((current) => current.map((record) => {
      if (record.id !== active.id) return record;
      const updated = updater(record);
      return record.status === "confirmed" ? { ...updated, status: "review", acknowledged: false } : updated;
    }));
  }

  function updateField(field: keyof Pick<InvoiceRecord, "invoiceNumber" | "issueDate" | "seller" | "customer" | "writtenTotal" | "reviewNote">, value: string) {
    updateActive((record) => ({ ...record, [field]: value }));
  }

  function updateItem(itemId: string, field: keyof InvoiceItem, value: string) {
    updateActive((record) => ({ ...record, items: record.items.map((item) => item.id === itemId ? { ...item, [field]: value } : item) }));
  }

  function addFiles(files: File[]) {
    const accepted = files.filter((file) => file.type.startsWith("image/"));
    if (accepted.length === 0) {
      setNotice("اختر صور فواتير بصيغة JPG أو PNG.");
      return;
    }
    const created: InvoiceRecord[] = accepted.map((file, index) => ({
      id: `LOCAL-${Date.now()}-${index + 1}`,
      filename: file.name,
      status: "ready",
      invoiceNumber: "",
      issueDate: "",
      seller: "",
      customer: "",
      writtenTotal: "",
      reviewNote: "",
      acknowledged: false,
      previewUrl: URL.createObjectURL(file),
      items: [newItem()],
    }));
    setRecords((current) => [...current, ...created]);
    setActiveId(created[0].id);
    setNotice(`تمت إضافة ${created.length} صورة محليًا. اربط زر الاستخراج بخدمة الوكيل قبل إرسالها.`);
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    addFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  }

  function onDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setIsDragging(false);
    addFiles(Array.from(event.dataTransfer.files));
  }

  function prepareForReview(record: InvoiceRecord) {
    setRecords((current) => current.map((candidate) => candidate.id === record.id ? { ...candidate, status: "review", reviewNote: "" } : candidate));
    setNotice("تم فتح نموذج مراجعة فارغ. ما زال استخراج الوكيل غير موصول؛ أدخل البيانات أو اربط نقطة API الآمنة.");
  }

  function confirmActive() {
    if (!active) return;
    if (requiresAcknowledgement && !active.acknowledged) {
      setNotice("أكد أنك راجعت الحقول أو الملاحظات المعلّمة قبل إضافة الفاتورة إلى ملف Excel.");
      return;
    }
    setRecords((current) => current.map((record) => record.id === active.id ? { ...record, status: "confirmed" } : record));
    setNotice("تم تأكيد الفاتورة. ستظهر مرة واحدة فقط في ملف Excel القادم.");
  }

  function exportConfirmed() {
    if (confirmed.length === 0) {
      setNotice("أكد فاتورة واحدة على الأقل قبل إنشاء ملف Excel.");
      return;
    }
    const url = URL.createObjectURL(createConfirmedWorkbook(confirmed));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "الفواتير-المؤكدة.xlsx";
    anchor.click();
    URL.revokeObjectURL(url);
    setNotice(`تم تنزيل ملف Excel يضم ${confirmed.length} فاتورة مؤكدة فقط.`);
  }

  if (!active) return null;
  const calculated = calculatedTotal(active);

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#workspace" aria-label="فاتورتي، صفحة العمل"><span className="brand-mark"><Icon name="sparkles" size={22} /></span><span>فاتورتي <small>مراجعة ذكية</small></span></a>
        <nav className="workflow" aria-label="مراحل العمل">
          <span className="workflow-item active"><b>١</b> رفع الفواتير</span><span className="workflow-line" />
          <span className="workflow-item active"><b>٢</b> مراجعة النتائج</span><span className="workflow-line" />
          <span className="workflow-item"><b>٣</b> تصدير Excel</span>
        </nav>
        <button className="profile-button" type="button" aria-label="الملف الشخصي"><span>م</span><Icon name="chevron" size={15} /></button>
      </header>

      <section className="welcome-row">
        <div><p className="eyebrow"><span /> مساحة عمل آمنة</p><h1>حوّل الفواتير إلى بيانات <em>راجعتها بنفسك.</em></h1><p className="subhead">يرتب الوكيل الاستخراج، وأنت تراجع الصورة والبيانات قبل أن تدخل أي فاتورة إلى ملف Excel.</p></div>
        <button className="export-button" type="button" onClick={exportConfirmed}><Icon name="download" size={18} /> تنزيل Excel {confirmed.length > 0 && <span>{confirmed.length}</span>}</button>
      </section>

      <section className="summary-grid" aria-label="ملخص الدفعة">
        <article className="summary-card blue"><div><span>إجمالي الفواتير</span><strong>{records.length}</strong><small>يمكنك رفع الدفعة كاملة، حتى ٧٠ فاتورة</small></div><i><Icon name="file" size={23} /></i></article>
        <article className="summary-card amber"><div><span>بانتظار المراجعة</span><strong>{reviewCount}</strong><small>{waitingCount ? `${waitingCount} في انتظار الاستخراج` : "كل النتائج جاهزة للمراجعة"}</small></div><i><Icon name="sparkles" size={23} /></i></article>
        <article className="summary-card green"><div><span>فواتير مؤكدة</span><strong>{confirmed.length}</strong><small>هذه فقط تدخل ملف Excel</small></div><i><Icon name="check" size={23} /></i></article>
      </section>

      <section className="drop-zone-wrap">
        <input ref={inputRef} className="sr-only" type="file" accept="image/png,image/jpeg" multiple onChange={onFileChange} />
        <button className={`drop-zone ${isDragging ? "dragging" : ""}`} type="button" onClick={() => inputRef.current?.click()} onDragOver={(event) => { event.preventDefault(); setIsDragging(true); }} onDragLeave={() => setIsDragging(false)} onDrop={onDrop}>
          <span className="upload-icon"><Icon name="upload" size={24} /></span><span><b>أضف صور الفواتير</b><small>اسحب الملفات هنا أو اخترها من جهازك · JPG أو PNG</small></span><span className="select-files">اختيار ملفات</span>
        </button>
      </section>

      <p className="notice" aria-live="polite"><Icon name="sparkles" size={16} /> {notice}</p>

      <section className="workspace" id="workspace">
        <aside className="queue-panel">
          <div className="panel-heading"><div><span>قائمة الدفعة</span><strong>{records.length} فاتورة</strong></div><button type="button" onClick={() => inputRef.current?.click()}><Icon name="plus" size={17} /> إضافة</button></div>
          <div className="queue-filter"><span>الكل</span><small>غير مؤكدة {records.length - confirmed.length}</small></div>
          <div className="queue-list">{records.map((record) => <button type="button" key={record.id} className={`queue-item ${record.id === active.id ? "selected" : ""}`} onClick={() => setActiveId(record.id)}><span className={`queue-file ${record.status}`}><Icon name="file" size={19} /></span><span className="queue-name"><b>{record.filename}</b><small>{record.invoiceNumber ? `رقم ${record.invoiceNumber}` : "بيانات جديدة"}</small></span><span className={`status-dot ${record.status}`} title={statusLabel[record.status]} /></button>)}</div>
          <div className="queue-foot"><span><i className="dot green" /> مؤكد</span><span><i className="dot amber" /> للمراجعة</span><span><i className="dot gray" /> انتظار</span></div>
        </aside>

        <section className="invoice-preview" aria-label="صورة الفاتورة">
          <div className="preview-heading"><div><span>صورة الفاتورة الأصلية</span><b>{active.filename}</b></div><div className="preview-tools"><button type="button" aria-label="تدوير الصورة"><Icon name="rotate" size={17} /></button><button type="button" aria-label="تكبير الصورة">＋</button></div></div>
          <div className="paper-stage">
            {active.previewUrl ? (
              // The local object URL is intentionally never sent anywhere by this UI.
              // eslint-disable-next-line @next/next/no-img-element
              <img src={active.previewUrl} alt={`معاينة ${active.filename}`} className="uploaded-invoice" />
            ) : <article className="paper-demo" aria-label="نموذج فاتورة تجريبي"><div className="paper-logo">النــــور <small>للتوريدات العامة</small></div><div className="paper-meta"><span>رقم الفاتورة: <b>0023</b></span><span>التاريخ: ١٨ / ٠٩ / ٢٠٢٦</span></div><p>السادة / شركة البناء الحديث</p><table><thead><tr><th>البيان</th><th>الكمية</th><th>السعر</th><th>الإجمالي</th></tr></thead><tbody><tr><td>أسمنت أبيض ٥٠ كجم</td><td>٣</td><td>٨٥٠</td><td>٢٬٥٥٠</td></tr><tr><td>رمل ناعم مغسول</td><td>٢</td><td>٢٬٣٠٠</td><td>٤٬٦٠٠</td></tr></tbody></table><div className="paper-total"><span>الإجمالي</span><b>٧٬١٥٠ ج.م</b></div><div className="paper-sign">التوقيع والختم</div></article>}
            <span className="demo-watermark">معاينة {active.previewUrl ? "محلية" : "توضيحية"}</span>
          </div>
          <p className="preview-caption"><Icon name="file" size={15} /> الصورة بجانب النتيجة حتى تقارن كل حقل قبل التأكيد.</p>
        </section>

        <section className="review-panel">
          {active.status === "ready" ? <div className="empty-review"><span className="empty-icon"><Icon name="sparkles" size={27} /></span><h2>الفاتورة جاهزة للاستخراج</h2><p>أضفت الصورة محليًا. عند توصيل خدمة الوكيل، سترسل إليها من خادم آمن وليس من المتصفح.</p><button className="primary-button" type="button" onClick={() => prepareForReview(active)}><Icon name="arrow" size={18} /> فتح نموذج المراجعة</button></div> : <>
            <div className="review-heading"><div><p>نتيجة الاستخراج</p><h2>راجع وصحّح البيانات</h2></div><span className={`review-status ${active.status}`}><i /> {statusLabel[active.status]}</span></div>
            {active.status === "confirmed" && <div className="confirmed-banner"><Icon name="check" size={18} /> هذه الفاتورة ضمن ملف Excel. أي تعديل يعيدها تلقائيًا إلى المراجعة.</div>}
            <div className="review-scroll">
              <section className="form-section"><div className="section-title"><span>بيانات الفاتورة</span><small>يمكن تعديل كل قيمة</small></div><div className="form-grid"><label>رقم الفاتورة<input value={active.invoiceNumber} onChange={(event) => updateField("invoiceNumber", event.target.value)} placeholder="مثال: 0023" dir="ltr" /></label><label>التاريخ<input type="date" value={active.issueDate} onChange={(event) => updateField("issueDate", event.target.value)} /></label><label>اسم البائع<input value={active.seller} onChange={(event) => updateField("seller", event.target.value)} placeholder="اسم البائع" /></label><label className={active.reviewNote ? "attention" : ""}>اسم العميل<input value={active.customer} onChange={(event) => updateField("customer", event.target.value)} placeholder="اسم العميل" /><small>{active.reviewNote ? "راجعه من الصورة" : ""}</small></label><label className="full-width">الإجمالي المكتوب<input value={active.writtenTotal} onChange={(event) => updateField("writtenTotal", event.target.value)} placeholder="اتركه فارغًا إذا لم يكن واضحًا" inputMode="decimal" /></label></div></section>
              <section className="form-section items-section"><div className="section-title"><span>الأصناف والخدمات</span><small>{active.items.length} سطر</small></div><div className="items-table-wrap"><table className="items-table"><thead><tr><th>الوصف</th><th>الكمية</th><th>سعر الوحدة</th><th>المبلغ المكتوب</th><th>المحسوب</th><th aria-label="حذف" /></tr></thead><tbody>{active.items.map((item) => <tr key={item.id}><td><input value={item.description} onChange={(event) => updateItem(item.id, "description", event.target.value)} placeholder="وصف الصنف" /></td><td><input value={item.quantity} onChange={(event) => updateItem(item.id, "quantity", event.target.value)} inputMode="decimal" /></td><td><input value={item.unitPrice} onChange={(event) => updateItem(item.id, "unitPrice", event.target.value)} inputMode="decimal" /></td><td><input value={item.writtenAmount} onChange={(event) => updateItem(item.id, "writtenAmount", event.target.value)} inputMode="decimal" /></td><td className="calculated-cell">{formatMoney(lineTotal(item))}</td><td><button className="delete-item" type="button" aria-label="حذف الصنف" onClick={() => updateActive((record) => ({ ...record, items: record.items.filter((candidate) => candidate.id !== item.id) }))} disabled={active.items.length === 1}><Icon name="trash" size={16} /></button></td></tr>)}</tbody></table></div><button className="add-item" type="button" onClick={() => updateActive((record) => ({ ...record, items: [...record.items, newItem()] }))}><Icon name="plus" size={16} /> إضافة سطر</button></section>
              <section className={`calculation-card ${calculated === null ? "muted" : ""}`}><div><span>الإجمالي المحسوب من الأصناف</span><strong>{formatMoney(calculated)} <small>ج.م</small></strong></div><span>{calculated === null ? "أكمل الكمية وسعر الوحدة" : "قيمة محسوبة، لا تستبدل المكتوب"}</span></section>
              <section className="form-section notes-section"><div className="section-title"><span>ملاحظات المراجع</span><small>تظهر في Excel</small></div><textarea value={active.reviewNote} onChange={(event) => updateField("reviewNote", event.target.value)} placeholder="اكتب أي توضيح أو سبب لترك قيمة فارغة..." rows={2} /></section>
            </div>
            <footer className="review-footer">{requiresAcknowledgement && <label className="acknowledgement"><input type="checkbox" checked={active.acknowledged} onChange={(event) => updateActive((record) => ({ ...record, acknowledged: event.target.checked }))} /><span>راجعت الحقول أو الملاحظة المعلّمة وأوافق على حفظها كما هي.</span></label>}<div className="footer-actions"><button className="secondary-button" type="button" onClick={() => setNotice("حُفظت التعديلات في ذاكرة هذه الواجهة. أضف التخزين الخلفي لحفظها بعد إعادة التشغيل.")}>حفظ مسودة</button><button className="confirm-button" type="button" onClick={confirmActive}><Icon name="check" size={19} /> {active.status === "confirmed" ? "تم التأكيد" : "تأكيد وإضافة إلى Excel"}</button></div></footer>
          </>}
        </section>
      </section>

      <section className="architecture-note"><span><Icon name="sparkles" size={18} /></span><p><b>ربط الوكيل الحقيقي:</b> ارفع الصورة إلى API خاص على الخادم، اطلب من Gemini نتيجةً مطابقةً لمخطط بيانات، خزّن الصورة والنتيجة الخام محليًا، ثم أعد النتيجة لهذه الشاشة للمراجعة. لا تضع مفتاح Gemini في Next.js أو المتصفح.</p></section>
    </main>
  );
}
