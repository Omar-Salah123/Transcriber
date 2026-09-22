<?php

namespace App\Services;

use App\Models\Invoice;
use Brick\Math\BigDecimal;

class InvoiceReviewService
{
    public function decimal(?string $value): ?BigDecimal
    {
        $normalized = strtr(trim($value ?? ''), array_combine(
            preg_split('//u', '٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', -1, PREG_SPLIT_NO_EMPTY),
            str_split('01234567890123456789')
        ));
        $normalized = strtr($normalized, ['٫' => '.', '٬' => ',']);
        if (! preg_match('/^-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,4})?$/D', $normalized)) {
            return null;
        }
        $number = BigDecimal::of(str_replace(',', '', $normalized));

        return $number->abs()->isLessThan('1000000000000000') ? $number : null;
    }

    public function refreshCalculatedAmounts(Invoice $invoice): void
    {
        $total = BigDecimal::of(0);
        $complete = $invoice->items->isNotEmpty();
        foreach ($invoice->items as $item) {
            $quantity = $this->decimal($item->quantity_text);
            $price = $this->decimal($item->unit_price_text);
            $line = $quantity?->multipliedBy($price ?? 0)->stripTrailingZeros();
            if ($quantity === null || $price === null || $line->getScale() > 4 || $line->abs()->isGreaterThanOrEqualTo('1000000000000000')) {
                $line = null;
                $complete = false;
            }
            $item->calculated_amount = $line === null ? null : (string) $line;
            $item->save();
            $total = $total->plus($line ?? 0);
        }
        $invoice->calculated_total = $complete && $total->abs()->isLessThan('1000000000000000') ? (string) $total : null;
        $invoice->save();
    }

    /** @return list<array{field: string, message: string}> */
    public function warnings(Invoice $invoice): array
    {
        $warnings = [];
        $add = function (string $field, string $message) use (&$warnings): void {
            $warnings[] = ['field' => $field, 'message' => $message];
        };
        foreach (['invoice_number', 'date_text', 'seller', 'customer', 'written_total_text'] as $field) {
            if (blank($invoice->{$field})) {
                $add($field, 'قيمة مفقودة: '.$field);
            }
        }
        foreach ($invoice->unresolved_fields ?? [] as $field) {
            $add($field, 'قيمة غير مؤكدة: '.$field);
        }
        if ($invoice->items->isEmpty()) {
            $add('items', 'لا توجد أصناف');
        }
        foreach ($invoice->items as $index => $item) {
            foreach (['description', 'quantity_text', 'unit_price_text', 'written_amount_text'] as $field) {
                if (blank($item->{$field})) {
                    $add("items.$index.$field", 'قيمة مفقودة في السطر '.$item->row_order.': '.$field);
                } elseif ($field !== 'description' && $this->decimal($item->{$field}) === null) {
                    $add("items.$index.$field", 'رقم غير صالح أو خارج النطاق في السطر '.$item->row_order);
                }
            }
            foreach ($item->unresolved_fields ?? [] as $field) {
                $add("items.$index.$field", 'قيمة غير مؤكدة في السطر '.$item->row_order.': '.$field);
            }
            $written = $this->decimal($item->written_amount_text);
            if ($written !== null && $item->calculated_amount !== null && ! $written->isEqualTo($item->calculated_amount)) {
                $add("items.$index.written_amount_text", 'المبلغ المكتوب يختلف عن المحسوب في السطر '.$item->row_order);
            }
            if ($item->calculated_amount === null) {
                $add("items.$index.calculated_amount", 'تعذر حساب السطر '.$item->row_order.' بدقة مدعومة');
            }
            if (filled($item->review_note)) {
                $add("items.$index.review_note", $item->review_note);
            }
        }
        $written = $this->decimal($invoice->written_total_text);
        if (filled($invoice->written_total_text) && $written === null) {
            $add('written_total_text', 'الإجمالي المكتوب غير صالح للحساب');
        }
        if ($written !== null && $invoice->calculated_total !== null && ! $written->isEqualTo($invoice->calculated_total)) {
            $add('written_total_text', 'الإجمالي المكتوب يختلف عن مجموع الأصناف');
        }
        if ($invoice->calculated_total === null) {
            $add('calculated_total', 'الإجمالي المحسوب غير مكتمل');
        }
        if (filled($invoice->review_notes)) {
            $add('review_notes', $invoice->review_notes);
        }

        return $warnings;
    }

    public function present(Invoice $invoice): array
    {
        $invoice->loadMissing('items');
        $result = $invoice->toArray();
        unset($result['image_path'], $result['raw_model_output'], $result['original_extraction'], $result['extraction_token']);
        $result['warnings'] = $this->warnings($invoice);
        $result['image_url'] = '/api/invoices/'.$invoice->id.'/image';

        return $result;
    }
}
