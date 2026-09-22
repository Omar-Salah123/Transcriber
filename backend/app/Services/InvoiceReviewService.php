<?php

namespace App\Services;

use App\Models\Invoice;
use App\Models\InvoiceItem;
use Brick\Math\BigDecimal;
use Brick\Math\Exception\MathException;

class InvoiceReviewService
{
    /** Recompute derived values without changing invoice text supplied by a person or model. */
    public function refreshCalculatedAmounts(Invoice $invoice): void
    {
        $allLinesComplete = true;
        $total = BigDecimal::of(0);

        foreach ($invoice->items as $item) {
            $line = $this->lineTotal($item);
            $item->calculated_amount = $line?->__toString();
            $item->save();

            if ($line === null) {
                $allLinesComplete = false;
                continue;
            }
            $total = $total->plus($line);
        }

        $invoice->calculated_total = $allLinesComplete ? $total->__toString() : null;
        $invoice->save();
    }

    /** @return list<string> */
    public function warnings(Invoice $invoice): array
    {
        $warnings = [];
        foreach (['invoice_number', 'customer', 'written_total_text'] as $field) {
            if (blank($invoice->{$field})) {
                $warnings[] = "Missing {$field}.";
            }
        }

        foreach ($invoice->items as $item) {
            foreach (['description', 'quantity_text', 'unit_price_text'] as $field) {
                if (blank($item->{$field})) {
                    $warnings[] = "Missing {$field} in item {$item->row_order}.";
                }
            }
            foreach ($item->unresolved_fields ?? [] as $field) {
                $warnings[] = "Unresolved {$field} in item {$item->row_order}.";
            }
        }
        foreach ($invoice->items as $item) {
            foreach ($item->unresolved_fields ?? [] as $field) {
                $warnings[] = "Unresolved {$field} in item {$item->row_order}.";
            }
        }
        foreach ($invoice->getAttribute('unresolved_fields') ?? [] as $field) {
            $warnings[] = "Unresolved {$field}.";
        }

        $written = $this->decimal($invoice->written_total_text);
        $calculated = $this->decimal($invoice->calculated_total);
        if ($written !== null && $calculated !== null && !$written->isEqualTo($calculated)) {
            $warnings[] = 'Written total differs from calculated total.';
        }

        return array_values(array_unique($warnings));
    }

    private function lineTotal(InvoiceItem $item): ?BigDecimal
    {
        $quantity = $this->decimal($item->quantity_text);
        $unitPrice = $this->decimal($item->unit_price_text);

        return $quantity !== null && $unitPrice !== null ? $quantity->multipliedBy($unitPrice) : null;
    }

    private function decimal(?string $value): ?BigDecimal
    {
        if ($value === null) {
            return null;
        }

        $normalized = strtr(trim($value), [
            '٠' => '0', '١' => '1', '٢' => '2', '٣' => '3', '٤' => '4',
            '٥' => '5', '٦' => '6', '٧' => '7', '٨' => '8', '٩' => '9',
            '۰' => '0', '۱' => '1', '۲' => '2', '۳' => '3', '۴' => '4',
            '۵' => '5', '۶' => '6', '۷' => '7', '۸' => '8', '۹' => '9',
            '٬' => '', '٫' => '.', ',' => '',
        ]);
        if (!preg_match('/^-?\d+(?:\.\d+)?$/', $normalized)) {
            return null;
        }

        try {
            return BigDecimal::of($normalized);
        } catch (MathException) {
            return null;
        }
    }
}
