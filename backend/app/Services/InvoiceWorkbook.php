<?php

namespace App\Services;

use Illuminate\Support\Collection;
use PhpOffice\PhpSpreadsheet\Cell\Coordinate;
use PhpOffice\PhpSpreadsheet\Cell\DataType;
use PhpOffice\PhpSpreadsheet\Spreadsheet;
use PhpOffice\PhpSpreadsheet\Worksheet\Worksheet;
use PhpOffice\PhpSpreadsheet\Writer\Xlsx;

class InvoiceWorkbook
{
    public function __construct(private InvoiceReviewService $review) {}

    public function build(Collection $invoices): Spreadsheet
    {
        $book = new Spreadsheet;
        $headers = $book->getActiveSheet()->setTitle('الفواتير');
        $items = $book->createSheet()->setTitle('الأصناف');
        $this->row($headers, 1, ['المعرف', 'رقم الفاتورة', 'التاريخ المكتوب', 'البائع', 'العميل', 'الإجمالي المكتوب', 'الإجمالي المحسوب', 'اكتمال الحساب', 'المصدر', 'ملاحظات المراجع', 'تحذيرات أقرها المراجع', 'تفسير الإجمالي المكتوب']);
        $this->row($items, 1, ['معرف الفاتورة', 'ترتيب السطر', 'الوصف', 'الكمية', 'سعر الوحدة', 'المبلغ المكتوب', 'المبلغ المحسوب', 'ملاحظات', 'تفسير سعر الوحدة', 'تفسير المبلغ المكتوب']);
        $invoiceRow = 2;
        $itemRow = 2;
        foreach ($invoices as $invoice) {
            if ($invoice->status !== 'confirmed') {
                continue;
            }
            $this->row($headers, $invoiceRow++, [$invoice->id, WesternDigits::in($invoice->invoice_number), WesternDigits::in($invoice->date_text), WesternDigits::in($invoice->seller), WesternDigits::in($invoice->customer),
                $this->numberOrText($invoice->written_total_text), $this->numeric($invoice->calculated_total),
                $invoice->calculated_total === null ? 'غير مكتمل' : 'مكتمل', WesternDigits::in($invoice->source_filename), WesternDigits::in($invoice->review_notes),
                WesternDigits::in(implode('؛ ', array_column($this->review->warnings($invoice), 'message'))),
                $this->interpretedNumberOrText($invoice->written_total_interpreted_text)]);
            foreach ($invoice->items as $item) {
                $this->row($items, $itemRow++, [$invoice->id, $item->row_order, WesternDigits::in($item->description),
                    $this->numberOrText($item->quantity_text), $this->numberOrText($item->unit_price_text),
                    $this->numberOrText($item->written_amount_text), $this->numeric($item->calculated_amount),
                    WesternDigits::in($item->review_note), $this->interpretedNumberOrText($item->unit_price_interpreted_text),
                    $this->interpretedNumberOrText($item->written_amount_interpreted_text)]);
            }
        }
        foreach ($book->getAllSheets() as $sheet) {
            $sheet->setRightToLeft(true);
            $sheet->freezePane('A2');
            $sheet->setAutoFilter($sheet->calculateWorksheetDimension());
            $sheet->getStyle('A1:'.$sheet->getHighestColumn().'1')->getFont()->setBold(true);
            $sheet->getStyle($sheet->calculateWorksheetDimension())->getAlignment()->setWrapText(true);
            for ($column = 1; $column <= Coordinate::columnIndexFromString($sheet->getHighestColumn()); $column++) {
                $sheet->getColumnDimension(Coordinate::stringFromColumnIndex($column))->setWidth($column === 1 ? 38 : 24);
            }
        }

        return $book;
    }

    private function numeric(?string $value): ?float
    {
        return $value === null ? null : (float) $value;
    }

    private function numberOrText(?string $value): string|float|null
    {
        $number = $this->review->decimal($value);

        return $number === null ? WesternDigits::in($value) : (float) (string) $number;
    }

    private function interpretedNumberOrText(?string $value): string|float|null
    {
        $normalized = WesternDigits::in($value);
        if ($normalized === null || ! preg_match('/^[0-9]+$/D', $normalized)) {
            return $normalized;
        }

        $number = $this->review->decimal($normalized);

        return $number === null ? $normalized : (float) (string) $number;
    }

    private function row(Worksheet $sheet, int $row, array $values): void
    {
        foreach ($values as $index => $value) {
            $type = $value === null ? DataType::TYPE_NULL : (is_int($value) || is_float($value) ? DataType::TYPE_NUMERIC : DataType::TYPE_STRING);
            $sheet->setCellValueExplicit([$index + 1, $row], $value, $type);
        }
    }

    public function write(Collection $invoices, string $path): void
    {
        $book = $this->build($invoices);
        try {
            (new Xlsx($book))->save($path);
        } finally {
            $book->disconnectWorksheets();
        }
    }
}
