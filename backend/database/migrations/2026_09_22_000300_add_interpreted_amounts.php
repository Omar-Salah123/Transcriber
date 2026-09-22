<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('invoices', function (Blueprint $table): void {
            $table->string('written_total_interpreted_text')->nullable();
        });

        Schema::table('invoice_items', function (Blueprint $table): void {
            $table->string('unit_price_interpreted_text')->nullable();
            $table->string('written_amount_interpreted_text')->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('invoice_items', function (Blueprint $table): void {
            $table->dropColumn(['unit_price_interpreted_text', 'written_amount_interpreted_text']);
        });

        Schema::table('invoices', function (Blueprint $table): void {
            $table->dropColumn('written_total_interpreted_text');
        });
    }
};
