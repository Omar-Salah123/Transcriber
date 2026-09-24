<?php

use App\Http\Controllers\InvoiceController;
use App\Http\Middleware\LocalInvoiceApi;
use Illuminate\Support\Facades\Route;

Route::middleware(LocalInvoiceApi::class)->group(function (): void {
    Route::get('invoices', [InvoiceController::class, 'index']);
    Route::post('invoices', [InvoiceController::class, 'store']);
    Route::delete('invoices', [InvoiceController::class, 'destroyAll']);
    Route::get('exports/invoices', [InvoiceController::class, 'export']);
    Route::get('invoices/{invoice}', [InvoiceController::class, 'show']);
    Route::get('invoices/{invoice}/image', [InvoiceController::class, 'image']);
    Route::put('invoices/{invoice}', [InvoiceController::class, 'update']);
    Route::post('invoices/{invoice}/extract', [InvoiceController::class, 'extract']);
    Route::post('invoices/{invoice}/confirm', [InvoiceController::class, 'confirm']);
});
