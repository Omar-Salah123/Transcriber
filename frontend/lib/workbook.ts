import {
  calculatedTotal,
  lineTotal,
  parseAmount,
  type InvoiceRecord,
} from "@/lib/invoice";

type Cell = string | number | null;

const encoder = new TextEncoder();

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function columnName(index: number): string {
  let value = index + 1;
  let name = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    name = String.fromCharCode(65 + remainder) + name;
    value = Math.floor((value - 1) / 26);
  }
  return name;
}

function cellXml(value: Cell, reference: string, isHeading: boolean): string {
  if (value === null || value === "") {
    return `<c r="${reference}"${isHeading ? ' s="1"' : ""}/>`;
  }

  if (typeof value === "number" && Number.isFinite(value)) {
    return `<c r="${reference}"${isHeading ? ' s="1"' : ""}><v>${value}</v></c>`;
  }

  // Inline strings keep model or invoice text as literal data, never formulas.
  return `<c r="${reference}" t="inlineStr"${isHeading ? ' s="1"' : ""}><is><t xml:space="preserve">${escapeXml(
    String(value),
  )}</t></is></c>`;
}

function worksheetXml(rows: Cell[][]): string {
  const columnCount = Math.max(...rows.map((row) => row.length), 1);
  const lastColumn = columnName(columnCount - 1);
  const body = rows
    .map(
      (row, rowIndex) =>
        `<row r="${rowIndex + 1}">${row
          .map((value, columnIndex) =>
            cellXml(value, `${columnName(columnIndex)}${rowIndex + 1}`, rowIndex === 0),
          )
          .join("")}</row>`,
    )
    .join("");

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews><sheetView workbookViewId="0" rightToLeft="1"><selection activeCell="A2" sqref="A2"/></sheetView></sheetViews>
  <sheetFormatPr defaultRowHeight="18"/>
  <cols><col min="1" max="${columnCount}" width="20" customWidth="1"/></cols>
  <sheetData>${body}</sheetData>
  <autoFilter ref="A1:${lastColumn}${rows.length}"/>
</worksheet>`;
}

function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of data) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function u16(value: number): number[] {
  return [value & 0xff, (value >>> 8) & 0xff];
}

function u32(value: number): number[] {
  return [
    value & 0xff,
    (value >>> 8) & 0xff,
    (value >>> 16) & 0xff,
    (value >>> 24) & 0xff,
  ];
}

function joinBytes(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((size, part) => size + part.length, 0);
  const result = new Uint8Array(total);
  let position = 0;
  for (const part of parts) {
    result.set(part, position);
    position += part.length;
  }
  return result;
}

function zip(files: Array<{ name: string; content: string }>): Uint8Array {
  const localEntries: Uint8Array[] = [];
  const centralEntries: Uint8Array[] = [];
  let offset = 0;

  for (const file of files) {
    const name = encoder.encode(file.name);
    const content = encoder.encode(file.content);
    const crc = crc32(content);
    const local = new Uint8Array([
      ...u32(0x04034b50),
      ...u16(20),
      ...u16(0x0800),
      ...u16(0),
      ...u16(0),
      ...u16(0),
      ...u32(crc),
      ...u32(content.length),
      ...u32(content.length),
      ...u16(name.length),
      ...u16(0),
      ...name,
      ...content,
    ]);
    const central = new Uint8Array([
      ...u32(0x02014b50),
      ...u16(20),
      ...u16(20),
      ...u16(0x0800),
      ...u16(0),
      ...u16(0),
      ...u16(0),
      ...u32(crc),
      ...u32(content.length),
      ...u32(content.length),
      ...u16(name.length),
      ...u16(0),
      ...u16(0),
      ...u16(0),
      ...u16(0),
      ...u32(0),
      ...u32(offset),
      ...name,
    ]);
    localEntries.push(local);
    centralEntries.push(central);
    offset += local.length;
  }

  const centralSize = centralEntries.reduce((size, entry) => size + entry.length, 0);
  const footer = new Uint8Array([
    ...u32(0x06054b50),
    ...u16(0),
    ...u16(0),
    ...u16(files.length),
    ...u16(files.length),
    ...u32(centralSize),
    ...u32(offset),
    ...u16(0),
  ]);
  return joinBytes([...localEntries, ...centralEntries, footer]);
}

/**
 * Produces a standards-compliant .xlsx with two RTL worksheets and no formula
 * cells. It accepts only already-confirmed records from the review queue.
 */
export function createConfirmedWorkbook(invoices: InvoiceRecord[]): Blob {
  const invoiceRows: Cell[][] = [
    [
      "المعرف الداخلي",
      "رقم الفاتورة",
      "التاريخ",
      "البائع",
      "العميل",
      "الإجمالي المكتوب",
      "الإجمالي المحسوب",
      "اسم الملف",
      "ملاحظات المراجع",
    ],
    ...invoices.map((invoice) => [
      invoice.id,
      invoice.invoiceNumber,
      invoice.issueDate,
      invoice.seller,
      invoice.customer,
      parseAmount(invoice.writtenTotal) ?? invoice.writtenTotal,
      calculatedTotal(invoice),
      invoice.filename,
      invoice.reviewNote,
    ]),
  ];
  const itemRows: Cell[][] = [
    [
      "المعرف الداخلي",
      "ترتيب السطر",
      "الوصف",
      "الكمية",
      "سعر الوحدة",
      "المبلغ المكتوب",
      "المبلغ المحسوب",
      "ملاحظات",
    ],
    ...invoices.flatMap((invoice) =>
      invoice.items.map((item, index) => [
        invoice.id,
        index + 1,
        item.description,
        parseAmount(item.quantity) ?? item.quantity,
        parseAmount(item.unitPrice) ?? item.unitPrice,
        parseAmount(item.writtenAmount) ?? item.writtenAmount,
        lineTotal(item),
        item.note,
      ]),
    ),
  ];

  const files = [
    {
      name: "[Content_Types].xml",
      content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>`,
    },
    {
      name: "_rels/.rels",
      content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`,
    },
    {
      name: "xl/workbook.xml",
      content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <bookViews><workbookView activeTab="0"/></bookViews>
  <sheets>
    <sheet name="الفواتير" sheetId="1" state="visible" r:id="rId1"/>
    <sheet name="الأصناف" sheetId="2" state="visible" r:id="rId2"/>
  </sheets>
</workbook>`,
    },
    {
      name: "xl/_rels/workbook.xml.rels",
      content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`,
    },
    {
      name: "xl/styles.xml",
      content: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2"><font><sz val="11"/><name val="Arial"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Arial"/></font></fonts>
  <fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF2563EB"/><bgColor indexed="64"/></patternFill></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="1" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs>
</styleSheet>`,
    },
    { name: "xl/worksheets/sheet1.xml", content: worksheetXml(invoiceRows) },
    { name: "xl/worksheets/sheet2.xml", content: worksheetXml(itemRows) },
  ];

  const archive = zip(files);
  const blobBytes = new Uint8Array(archive.length);
  blobBytes.set(archive);
  return new Blob([blobBytes.buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}
