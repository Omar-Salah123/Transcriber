<?php

namespace App\Jobs;

use App\Models\Invoice;
use App\Services\InvoiceContract;
use App\Services\InvoiceReviewService;
use App\Services\WesternDigits;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Facades\Validator;
use Illuminate\Validation\ValidationException;
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
        $providerError = null;
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
            $raw = is_array($body) && array_key_exists('raw_model_output', $body)
                ? (is_string($body['raw_model_output']) ? $body['raw_model_output'] : null)
                : $response->body();
            if (! $response->successful()) {
                $error = self::serviceFailureMessage($body);
                if (is_array($body) && is_array($body['provider_error'] ?? null)) {
                    $encoded = json_encode($body['provider_error'], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
                    $providerError = $encoded === false ? null : $encoded;
                }
            } elseif (! is_array($body) || ! is_array($body['extraction'] ?? null)) {
                $error = 'أعادت خدمة الاستخراج استجابة غير صالحة. أعد المحاولة.';
            } else {
                $candidate = Validator::make($body['extraction'], InvoiceContract::rules())->validate();
            }
        } catch (ConnectionException) {
            $error = 'تعذر الاتصال بخدمة Python أو انتهت المهلة. تحقق من تشغيلها ثم أعد المحاولة.';
        } catch (ValidationException) {
            $error = 'بيانات الاستخراج لا تطابق الحقول المطلوبة. أعد المحاولة.';
        } catch (Throwable) {
            // Do not log provider payloads or credentials.
            $error = 'تعذر الاستخراج. تحقق من الخدمة والإعدادات ثم أعد المحاولة.';
        }
        DB::transaction(function () use ($review, $raw, $providerError, $candidate, $error): void {
            DB::table('extraction_attempts')->insertOrIgnore([
                'invoice_id' => $this->invoiceId, 'token' => $this->token,
                'raw_model_output' => $raw, 'extraction' => $candidate === null ? null : json_encode($candidate, JSON_UNESCAPED_UNICODE),
                'error' => $error, 'provider_error' => $providerError, 'created_at' => now(), 'updated_at' => now(),
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

    private static function serviceFailureMessage(mixed $body): string
    {
        $reason = is_array($body) && is_array($body['errors'] ?? null) ? ($body['errors'][0] ?? null) : null;
        if (! is_string($reason)) {
            return 'فشلت خدمة الاستخراج. تحقق من تشغيلها ثم أعد المحاولة.';
        }
        if (preg_match('/^Provider HTTP ([4-5][0-9]{2})$/D', $reason, $matches)) {
            return match ((int) $matches[1]) {
                429 => 'قيّد Gemini الطلب مؤقتاً (429). أعد المحاولة لاحقاً.',
                401, 403 => 'رفض Gemini صلاحية الوصول ('.$matches[1].'). تحقق من إعدادات الحساب.',
                404 => 'نموذج Gemini المحدد غير متاح (404). تحقق من اسم النموذج.',
                400, 413, 422 => 'رفض Gemini الصورة أو إعدادات الطلب ('.$matches[1].'). راجع الصورة والنموذج.',
                408, 500, 502, 503, 504 => 'تعذر إكمال طلب Gemini مؤقتاً ('.$matches[1].'). أعد المحاولة لاحقاً.',
                default => 'رفض Gemini طلب الاستخراج ('.$matches[1].'). تحقق من إعدادات الخدمة.',
            };
        }

        return match ($reason) {
            'Invalid structured output.' => 'لم يُرجع Gemini بيانات منظمة صالحة. أعد المحاولة أو أدخل الفاتورة يدوياً.',
            'Image type or dimensions are not supported.', 'The uploaded file is not a readable invoice image.' => 'الصورة غير قابلة للقراءة أو غير مدعومة. أعد حفظها بصيغة JPG أو PNG.',
            'Extraction failed: TimeoutError' => 'انتهت مهلة طلب Gemini. أعد المحاولة لاحقاً.',
            'Provider request failed', 'Extraction failed: ClientError', 'Extraction failed: ServerError' => 'رفض Gemini طلب الاستخراج. تحقق من الحصة وإعدادات النموذج.',
            default => 'فشلت خدمة الاستخراج. أعد المحاولة أو أدخل الفاتورة يدوياً.',
        };
    }

    public function failed(?Throwable $exception): void
    {
        Invoice::whereKey($this->invoiceId)->where('extraction_token', $this->token)->update([
            'status' => 'failed', 'extraction_token' => null, 'extraction_error' => 'توقفت مهمة الاستخراج. أعد المحاولة.',
        ]);
    }
}
