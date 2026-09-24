<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('extraction_attempts', function (Blueprint $table): void {
            $table->json('provider_error')->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('extraction_attempts', function (Blueprint $table): void {
            $table->dropColumn('provider_error');
        });
    }
};
