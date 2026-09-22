<?php

namespace App\Services;

class InvoiceContract
{
    public static function rules(): array
    {
        $rules = [
            'items' => ['present', 'array', 'max:500'],
            'items.*' => ['array:description,quantity_text,unit_price_text,unit_price_interpreted_text,written_amount_text,written_amount_interpreted_text,unresolved_fields,review_note'],
            'unresolved_fields' => ['present', 'array', 'max:100'],
            'unresolved_fields.*' => ['string', 'max:200'],
            'items.*.unresolved_fields' => ['present', 'array', 'max:100'],
            'items.*.unresolved_fields.*' => ['string', 'max:200'],
            'review_notes' => ['sometimes', 'nullable', 'string', 'max:10000'],
            'items.*.review_note' => ['sometimes', 'nullable', 'string', 'max:10000'],
        ];
        foreach (['invoice_number', 'date_text', 'seller', 'customer', 'written_total_text'] as $field) {
            $rules[$field] = ['present', 'nullable', 'string', 'max:1000'];
        }
        $rules['written_total_interpreted_text'] = ['sometimes', 'nullable', 'string', 'max:1000'];
        foreach (['description', 'quantity_text', 'unit_price_text', 'written_amount_text'] as $field) {
            $rules['items.*.'.$field] = ['present', 'nullable', 'string', 'max:1000'];
        }
        foreach (['unit_price_interpreted_text', 'written_amount_interpreted_text'] as $field) {
            $rules['items.*.'.$field] = ['sometimes', 'nullable', 'string', 'max:1000'];
        }

        return $rules;
    }
}
