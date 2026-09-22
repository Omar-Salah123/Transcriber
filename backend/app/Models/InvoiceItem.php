<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class InvoiceItem extends Model
{
    protected $fillable = [
        'row_order',
        'description',
        'quantity_text',
        'unit_price_text',
        'written_amount_text',
        'calculated_amount',
        'unresolved_fields',
        'review_note',
    ];

    protected function casts(): array
    {
        return [
            'calculated_amount' => 'decimal:4',
            'unresolved_fields' => 'array',
        ];
    }

    /** @return BelongsTo<Invoice, $this> */
    public function invoice(): BelongsTo
    {
        return $this->belongsTo(Invoice::class);
    }
}
