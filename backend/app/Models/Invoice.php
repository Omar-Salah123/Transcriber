<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Invoice extends Model
{
    use HasUuids;

    public $incrementing = false;

    protected $keyType = 'string';

    protected $fillable = [
        'source_filename',
        'source_hash',
        'image_path',
        'status',
        'invoice_number',
        'date_text',
        'seller',
        'customer',
        'written_total_text',
        'calculated_total',
        'raw_model_output',
        'review_notes',
        'review_acknowledged',
        'unresolved_fields',
        'original_extraction',
        'extraction_error',
        'extraction_token',
        'extraction_started_at',
        'version',
    ];

    protected function casts(): array
    {
        return [
            'review_acknowledged' => 'boolean',
            'calculated_total' => 'decimal:4',
            'unresolved_fields' => 'array',
            'original_extraction' => 'array',
            'extraction_started_at' => 'datetime',
            'version' => 'integer',
        ];
    }

    /** @return HasMany<InvoiceItem, $this> */
    public function items(): HasMany
    {
        return $this->hasMany(InvoiceItem::class)->orderBy('row_order');
    }
}
