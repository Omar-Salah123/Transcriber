<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /** Run the migrations. */
    public function up(): void
    {
        Schema::create('invoices', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->string('source_filename');
            $table->char('source_hash', 64)->unique();
            $table->string('image_path');
            $table->string('status')->default('pending')->index();
            $table->string('invoice_number')->nullable();
            $table->string('date_text')->nullable();
            $table->text('seller')->nullable();
            $table->text('customer')->nullable();
            $table->string('written_total_text')->nullable();
            $table->decimal('calculated_total', 20, 4)->nullable();
            $table->longText('raw_model_output')->nullable();
            $table->text('review_notes')->nullable();
            $table->boolean('review_acknowledged')->default(false);
            $table->timestamps();
        });

        Schema::create('invoice_items', function (Blueprint $table): void {
            $table->id();
            $table->foreignUuid('invoice_id')->constrained()->cascadeOnDelete();
            $table->unsignedInteger('row_order');
            $table->text('description')->nullable();
            $table->string('quantity_text')->nullable();
            $table->string('unit_price_text')->nullable();
            $table->string('written_amount_text')->nullable();
            $table->decimal('calculated_amount', 20, 4)->nullable();
            $table->json('unresolved_fields')->nullable();
            $table->text('review_note')->nullable();
            $table->timestamps();

            $table->unique(['invoice_id', 'row_order']);
        });
    }

    /** Reverse the migrations. */
    public function down(): void
    {
        Schema::dropIfExists('invoice_items');
        Schema::dropIfExists('invoices');
    }
};
