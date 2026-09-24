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
        $this->row($headers, 1, ['المعرف', 'رقم الفاتورة', 'التاريخ المكتوب', 'البائع', 'العميل', 'الإجمالي المكتوب', 'الإجمالي المحسوب', 'اكتمال الحساب', 'المصدر', 'ملاحظات المراجع', 'تحذيرات أقرها المراجع']);
        $this->row($items, 1, ['معرف الفاتورة', 'ترتيب السطر', 'الوصف', 'الكمية', 'سعر الوحدة', 'المبلغ المكتوب', 'المبلغ المحسوب', 'ملاحظات']);
        $invoiceRow = 2;
        $itemRow = 2;
        foreach ($invoices as $invoice) {
            if ($invoice->status !== 'confirmed') {
                continue;
            }
            $this->row($headers, $invoiceRow++, [$invoice->id, $this->westernDigits($invoice->invoice_number), $this->westernDigits($invoice->date_text), $this->westernDigits($invoice->seller), $this->westernDigits($invoice->customer),
                $this->numberOrText($invoice->written_total_text), $this->numeric($invoice->calculated_total),
                $invoice->calculated_total === null ? 'غير مكتمل' : 'مكتمل', $this->westernDigits($invoice->source_filename), $this->westernDigits($invoice->review_notes),
                implode('؛ ', array_column($this->review->warnings($invoice), 'message'))]);
            foreach ($invoice->items as $item) {
                $this->row($items, $itemRow++, [$invoice->id, $item->row_order, $this->westernDigits($item->description),
                    $this->numberOrText($item->quantity_text), $this->numberOrText($item->unit_price_text),
                    $this->numberOrText($item->written_amount_text), $this->numeric($item->calculated_amount),
                    $this->westernDigits($item->review_note)]);
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

        return $number === null ? $this->westernDigits($value) : (float) (string) $number;
    }

    private function westernDigits(?string $value): ?string
    {
        if ($value === null) {
            return null;
        }

        return strtr($value, array_combine(
            preg_split('//u', '٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', -1, PREG_SPLIT_NO_EMPTY),
            str_split('01234567890123456789')
        ));
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
