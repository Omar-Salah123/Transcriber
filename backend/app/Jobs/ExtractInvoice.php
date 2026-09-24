<?php

namespace App\Jobs;

use App\Models\Invoice;
use App\Services\InvoiceContract;
use App\Services\InvoiceReviewService;
use App\Services\WesternDigits;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Facades\Validator;
use Throwable;

class ExtractInvoice implements ShouldQueue
{
    use Queueable;

    public int $tries = 1;

    public int $timeout = 150;

    public function __construct(public string $invoiceId, public string $token) {}

    public function handle(InvoiceReviewService $review): void
    {
        $invoice = Invoice::whereKey($this->invoiceId)->where('extraction_token', $this->token)->where('status', 'processing')->first();
        if (! $invoice) {
            return;
        }
        // Atomic claim also makes accidental duplicate delivery a no-op.
        if (! Invoice::whereKey($invoice->id)->where('extraction_token', $this->token)->whereNull('extraction_started_at')->update(['extraction_started_at' => now()])) {
            return;
        }
        $raw = null;
        $candidate = null;
        $error = null;
        try {
            $url = config('invoices.ai_url');
            if (! in_array(parse_url($url, PHP_URL_HOST), ['127.0.0.1', 'localhost', '::1', '[::1]'])) {
                throw new \RuntimeException('AI service must be local');
            }
            $response = Http::connectTimeout(5)->timeout(config('invoices.ai_timeout'))->withHeaders(['X-Invoice-Service' => 'laravel'])->post(rtrim($url, '/').'/v1/extractions', [
                'source_filename' => $invoice->source_filename,
                'media_type' => Storage::disk('local')->mimeType($invoice->image_path),
                'image_base64' => base64_encode(Storage::disk('local')->get($invoice->image_path)),
            ]);
            $body = $response->json();
            $raw = is_array($body) && is_string($body['raw_model_output'] ?? null) ? $body['raw_model_output'] : $response->body();
            if (! $response->successful() || ! is_array($body) || ! is_array($body['extraction'] ?? null)) {
                throw new \RuntimeException('Invalid extraction response');
            }
            $candidate = Validator::make($body['extraction'], InvoiceContract::rules())->validate();
        } catch (Throwable) {
            // Do not log provider payloads or credentials.
            $error = 'تعذر الاستخراج. تحقق من الخدمة والإعدادات ثم أعد المحاولة.';
        }
        DB::transaction(function () use ($review, $raw, $candidate, $error): void {
            DB::table('extraction_attempts')->insertOrIgnore([
                'invoice_id' => $this->invoiceId, 'token' => $this->token,
                'raw_model_output' => $raw, 'extraction' => $candidate === null ? null : json_encode($candidate, JSON_UNESCAPED_UNICODE),
                'error' => $error, 'created_at' => now(), 'updated_at' => now(),
            ]);
            $invoice = Invoice::lockForUpdate()->findOrFail($this->invoiceId);
            if ($invoice->status !== 'processing' || $invoice->extraction_token !== $this->token) {
                return;
            }
            $invoice->raw_model_output = $raw;
            $invoice->extraction_error = $error;
            $invoice->extraction_token = null;
            $invoice->version++;
            if ($error !== null) {
                $invoice->status = 'failed';
                $invoice->save();

                return;
            }
            $invoice->original_extraction = $candidate;
            $reviewed = WesternDigits::inArray($candidate);
            $invoice->fill(Arr::except($reviewed, ['items']));
            $invoice->status = 'review';
            $invoice->review_acknowledged = false;
            $invoice->save();
            $invoice->items()->delete();
            foreach ($reviewed['items'] as $index => $item) {
                $invoice->items()->create($item + ['row_order' => $index + 1]);
            }
            $invoice->load('items');
            $review->refreshCalculatedAmounts($invoice);
        });
    }

    public function failed(?Throwable $exception): void
    {
        Invoice::whereKey($this->invoiceId)->where('extraction_token', $this->token)->update([
            'status' => 'failed', 'extraction_token' => null, 'extraction_error' => 'توقفت مهمة الاستخراج. أعد المحاولة.',
        ]);
    }
}
