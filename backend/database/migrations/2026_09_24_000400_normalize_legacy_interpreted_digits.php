<?php

use App\Models\Invoice;
use App\Services\InvoiceReviewService;
use App\Services\WesternDigits;
use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        $review = app(InvoiceReviewService::class);

        Invoice::with('items')->chunkById(100, function ($invoices) use ($review): void {
            foreach ($invoices as $invoice) {
                DB::transaction(function () use ($invoice, $review): void {
                    $changed = false;
                    $normalized = WesternDigits::in($invoice->written_total_interpreted_text);
                    if ($normalized !== $invoice->written_total_interpreted_text) {
                        $invoice->written_total_interpreted_text = $normalized;
                        $changed = true;
                    }

                    foreach ($invoice->items as $item) {
                        foreach (['unit_price_interpreted_text', 'written_amount_interpreted_text'] as $field) {
                            $normalized = WesternDigits::in($item->{$field});
                            if ($normalized !== $item->{$field}) {
                                $item->{$field} = $normalized;
                                $changed = true;
                            }
                        }
                        if ($item->isDirty()) {
                            $item->save();
                        }
                    }

                    if (! $changed) {
                        return;
                    }

                    // A previous confirmation did not cover the recalculated values.
                    if ($invoice->status === 'confirmed') {
                        $invoice->status = 'review';
                    }
                    $invoice->review_acknowledged = false;
                    $invoice->version++;
                    $invoice->save();
                    $review->refreshCalculatedAmounts($invoice);
                });
            }
        });
    }

    public function down(): void
    {
        // The original model candidate and response retain the source digit glyphs.
        // Reviewed values cannot be safely changed back after an operator edits them.
    }
};
