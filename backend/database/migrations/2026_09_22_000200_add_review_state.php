<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('invoices', function (Blueprint $table): void {
            // SQLite NUMERIC affinity can coerce exact decimals into binary floats.
            $table->string('calculated_total')->nullable()->change();
            $table->json('unresolved_fields')->nullable();
            $table->json('original_extraction')->nullable();
            $table->text('extraction_error')->nullable();
            $table->uuid('extraction_token')->nullable();
            $table->timestamp('extraction_started_at')->nullable();
            $table->unsignedInteger('version')->default(1);
        });
        Schema::table('invoice_items', function (Blueprint $table): void {
            $table->string('calculated_amount')->nullable()->change();
        });
        Schema::create('extraction_attempts', function (Blueprint $table): void {
            $table->id();
            $table->foreignUuid('invoice_id')->constrained()->cascadeOnDelete();
            $table->uuid('token')->unique();
            $table->longText('raw_model_output')->nullable();
            $table->json('extraction')->nullable();
            $table->text('error')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::table('invoices', function (Blueprint $table): void {
            $table->decimal('calculated_total', 20, 4)->nullable()->change();
        });
        Schema::table('invoice_items', function (Blueprint $table): void {
            $table->decimal('calculated_amount', 20, 4)->nullable()->change();
        });
        Schema::dropIfExists('extraction_attempts');
        Schema::table('invoices', function (Blueprint $table): void {
            $table->dropColumn(['unresolved_fields', 'original_extraction', 'extraction_error',
                'extraction_token', 'extraction_started_at', 'version']);
        });
    }
};
