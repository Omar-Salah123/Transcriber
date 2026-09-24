<?php

namespace Tests\Feature;

use App\Jobs\ExtractInvoice;
use App\Models\Invoice;
use App\Services\InvoiceReviewService;
use App\Services\InvoiceWorkbook;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Storage;
use PDOException;
use PhpOffice\PhpSpreadsheet\Cell\DataType;
use PhpOffice\PhpSpreadsheet\IOFactory;
use Tests\TestCase;

class InvoiceWorkflowTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        Storage::fake('local');
        Http::preventStrayRequests();
        Cache::store('file')->flush();
        $this->withHeader('X-Invoice-Client', 'local-review');
    }

    private function upload(): array
    {
        return $this->postJson('/api/invoices', ['image' => UploadedFile::fake()->image('synthetic.png')])->assertCreated()->json('invoice');
    }

    private function candidate(): array
    {
        return [
            'invoice_number' => '000081', 'date_text' => '٩ / ؟ / ٢٠٢٦',
            'seller' => 'متجر تجريبي', 'customer' => null, 'written_total_text' => '٠٫٣',
            'unresolved_fields' => ['date_text'], 'review_notes' => null,
            'items' => [[
                'description' => '=SUM(A1:A2)', 'quantity_text' => '٣', 'unit_price_text' => '٠٫١',
                'written_amount_text' => '٠٫٣', 'unresolved_fields' => [], 'review_note' => null,
            ]],
        ];
    }

    public function test_upload_deduplicates_by_bytes_and_rejects_invalid_files(): void
    {
        $file = UploadedFile::fake()->image('synthetic.png');
        $first = $this->postJson('/api/invoices', ['image' => $file])->assertCreated()->json('invoice');
        $this->postJson('/api/invoices', ['image' => $file])->assertOk()->assertJsonPath('duplicate', true)->assertJsonPath('invoice.id', $first['id']);
        $this->assertDatabaseCount('invoices', 1);
        $this->get('/api/invoices/'.$first['id'].'/image')->assertOk();
        $this->postJson('/api/invoices', ['image' => UploadedFile::fake()->create('bad.jpg', 1, 'text/plain')])->assertUnprocessable();
        $this->postJson('/api/invoices', ['image' => UploadedFile::fake()->image('large.png')->size(10241)])->assertUnprocessable();
    }

    public function test_drafts_confirmation_and_edits_are_persistent_and_versioned(): void
    {
        $invoice = $this->upload();
        $url = '/api/invoices/'.$invoice['id'];
        $draft = $this->putJson($url, $this->candidate() + ['version' => 1])->assertOk()
            ->assertJsonPath('calculated_total', '0.3000')
            ->assertJsonPath('date_text', '9 / ؟ / 2026')
            ->assertJsonPath('items.0.quantity_text', '3')->json();
        $this->getJson($url)->assertOk()->assertJsonPath('invoice_number', '000081')->assertJsonPath('items.0.row_order', 1);
        $this->assertSame('0٫3', Invoice::findOrFail($invoice['id'])->written_total_text);
        $this->postJson($url.'/confirm', ['version' => $draft['version'], 'acknowledged' => false])->assertUnprocessable();
        $this->postJson($url.'/confirm', ['version' => $draft['version'], 'acknowledged' => true])->assertOk()->assertJsonPath('status', 'confirmed');
        $this->postJson($url.'/confirm', ['version' => $draft['version'], 'acknowledged' => true])->assertOk();
        $this->assertDatabaseCount('invoice_items', 1);
        $this->putJson($url, $this->candidate() + ['version' => 1])->assertConflict();
        $this->putJson($url, $this->candidate() + ['version' => $draft['version']])->assertOk()->assertJsonPath('status', 'review')->assertJsonPath('review_acknowledged', false);
        $this->get('/api/exports/invoices')->assertUnprocessable();
    }

    public function test_decimal_parsing_rejects_ambiguous_text_and_empty_lines_do_not_total_zero(): void
    {
        $service = app(InvoiceReviewService::class);
        foreach (['12abc', '1,2', '1.2.3', '', '؟', '1e3'] as $bad) {
            $this->assertNull($service->decimal($bad));
        }
        $this->assertSame('1234.50', (string) $service->decimal('١٬٢٣٤٫٥٠'));
        $this->assertSame('12', (string) $service->decimal('۱۲'));
        $invoice = $this->upload();
        $data = $this->candidate();
        $data['items'] = [];
        $this->putJson('/api/invoices/'.$invoice['id'], $data + ['version' => 1])->assertOk()->assertJsonPath('calculated_total', null);
    }

    public function test_existing_reviews_display_western_digits_without_rewriting_saved_source(): void
    {
        $invoice = $this->upload();
        $url = '/api/invoices/'.$invoice['id'];
        $draft = $this->putJson($url, $this->candidate() + ['version' => 1])->assertOk()->json();
        $model = Invoice::findOrFail($invoice['id']);
        $model->update(['invoice_number' => '٠٠٠٠٨١', 'written_total_text' => '٠٫٣', 'written_total_interpreted_text' => '300']);

        $this->getJson($url)->assertOk()->assertJsonPath('invoice_number', '000081')->assertJsonPath('written_total_text', '0٫3');
        $this->getJson('/api/invoices')->assertOk()->assertJsonPath('0.invoice_number', '000081');
        $this->assertSame('٠٠٠٠٨١', $model->fresh()->invoice_number);

        $edited = $this->candidate();
        unset($edited['written_total_interpreted_text']);
        $this->putJson($url, $edited + ['version' => $draft['version']])->assertOk()
            ->assertJsonPath('written_total_interpreted_text', '300');
    }

    public function test_legacy_interpreted_digits_are_recalculated_and_confirmed_invoices_reopen(): void
    {
        $invoice = $this->upload();
        $url = '/api/invoices/'.$invoice['id'];
        $data = $this->candidate();
        $data['written_total_text'] = '١٤٠،~~~';
        $data['written_total_interpreted_text'] = '140000';
        $data['items'][0]['quantity_text'] = '٢';
        $data['items'][0]['unit_price_text'] = '٧٠،~~~';
        $data['items'][0]['unit_price_interpreted_text'] = '70000';
        $data['items'][0]['written_amount_text'] = '١٤٠،~~~';
        $data['items'][0]['written_amount_interpreted_text'] = '140000';
        $draft = $this->putJson($url, $data + ['version' => 1])->assertOk()->json();
        $this->postJson($url.'/confirm', ['version' => $draft['version'], 'acknowledged' => true])->assertOk();

        $model = Invoice::with('items')->findOrFail($invoice['id']);
        $beforeVersion = $model->version;
        $model->update([
            'written_total_interpreted_text' => '۱۴۰۰۰۰', 'calculated_total' => null,
            'original_extraction' => ['written_total_interpreted_text' => '۱۴۰۰۰۰'],
            'raw_model_output' => 'raw ١',
        ]);
        $model->items[0]->update([
            'unit_price_interpreted_text' => '٧٠٠٠٠',
            'written_amount_interpreted_text' => '١٤٠٠٠٠',
            'calculated_amount' => null,
        ]);
        $this->getJson($url)->assertOk()
            ->assertJsonPath('written_total_interpreted_text', '140000')
            ->assertJsonPath('items.0.unit_price_interpreted_text', '70000')
            ->assertJsonPath('calculated_total', null);
        $legacyWarningFields = array_column(app(InvoiceReviewService::class)->warnings($model->fresh('items')), 'field');
        $this->assertNotContains('items.0.unit_price_text', $legacyWarningFields);
        $this->assertNotContains('written_total_text', $legacyWarningFields);

        $migration = require base_path('database/migrations/2026_09_24_000400_normalize_legacy_interpreted_digits.php');
        $migration->up();

        $model = $model->fresh('items');
        $this->assertSame('review', $model->status);
        $this->assertFalse($model->review_acknowledged);
        $this->assertSame($beforeVersion + 1, $model->version);
        $this->assertSame('140000', $model->written_total_interpreted_text);
        $this->assertSame('70000', $model->items[0]->unit_price_interpreted_text);
        $this->assertSame('140000', $model->items[0]->written_amount_interpreted_text);
        $this->assertSame('140000.0000', $model->calculated_total);
        $this->assertSame('140000.0000', $model->items[0]->calculated_amount);
        $this->assertSame('۱۴۰۰۰۰', $model->original_extraction['written_total_interpreted_text']);
        $this->assertSame('raw ١', $model->raw_model_output);
        $this->get('/api/exports/invoices')->assertUnprocessable();
        $this->getJson($url)->assertOk()->assertJsonPath('calculated_total', '140000.0000');

        $migration->up();
        $this->assertSame($beforeVersion + 1, $model->fresh()->version);
        $this->postJson($url.'/confirm', ['version' => $model->version, 'acknowledged' => true])->assertOk()->assertJsonPath('status', 'confirmed');
    }

    public function test_line_discrepancies_missing_numbers_and_row_order_are_preserved(): void
    {
        $invoice = $this->upload();
        $data = $this->candidate();
        $data['items'][0]['written_amount_text'] = '99';
        $data['items'][] = array_replace($data['items'][0], ['description' => 'ثانٍ', 'quantity_text' => null]);
        $response = $this->putJson('/api/invoices/'.$invoice['id'], $data + ['version' => 1])->assertOk()->assertJsonPath('calculated_total', null)->assertJsonPath('items.1.row_order', 2);
        $this->assertContains('items.0.written_amount_text', array_column($response->json('warnings'), 'field'));
        $this->assertNull($response->json('items.1.calculated_amount'));
    }

    public function test_extraction_is_queued_once_and_cannot_replace_review(): void
    {
        Queue::fake();
        $invoice = $this->upload();
        $url = '/api/invoices/'.$invoice['id'];
        $this->postJson($url.'/extract')->assertAccepted();
        $this->postJson($url.'/extract')->assertConflict();
        $this->putJson($url, $this->candidate() + ['version' => 1])->assertConflict();
        Queue::assertPushed(ExtractInvoice::class, 1);
        $model = Invoice::findOrFail($invoice['id']);
        $job = new ExtractInvoice($model->id, $model->extraction_token);
        Http::fake(['*' => Http::response(['extraction' => $this->candidate(), 'raw_model_output' => 'original tool call'])]);
        $job->handle(app(InvoiceReviewService::class));
        $this->assertSame('review', $model->fresh()->status);
        $this->assertSame('original tool call', $model->fresh()->raw_model_output);
        $this->assertSame('000081', $model->fresh()->original_extraction['invoice_number']);
        $job->handle(app(InvoiceReviewService::class));
        Http::assertSentCount(1);
        $this->postJson($url.'/extract')->assertConflict();
    }

    public function test_sqlite_lock_during_scheduling_returns_a_safe_retry_message(): void
    {
        Queue::fake();
        $invoice = $this->upload();
        $error = new PDOException('SQLSTATE[HY000]: General error: 5 database is locked while updating private invoice');
        $error->errorInfo = ['HY000', 5, 'database is locked'];
        DB::shouldReceive('transaction')->once()->andThrow($error);

        $response = $this->postJson('/api/invoices/'.$invoice['id'].'/extract')->assertStatus(503);

        $this->assertStringContainsString('قاعدة البيانات مشغولة', $response->json('message'));
        $this->assertStringNotContainsString('private invoice', $response->getContent());
        Queue::assertNothingPushed();
        $this->assertSame('pending', Invoice::findOrFail($invoice['id'])->status);
    }

    public function test_extraction_uses_western_digits_without_changing_original_model_data(): void
    {
        Queue::fake();
        $invoice = $this->upload();
        $url = '/api/invoices/'.$invoice['id'];
        $this->postJson($url.'/extract')->assertAccepted();
        $model = Invoice::findOrFail($invoice['id']);
        $candidate = $this->candidate();
        $candidate['invoice_number'] = '۰۰٠۰۸١';
        $candidate['seller'] = 'متجر ۱۲٣';
        $candidate['items'][0]['description'] = 'صنف ٤ / ۵';
        $candidate['items'][0]['review_note'] = 'راجع ٦';
        Http::fake(['*' => Http::response(['extraction' => $candidate, 'raw_model_output' => 'raw ١۲'])]);

        (new ExtractInvoice($model->id, $model->extraction_token))->handle(app(InvoiceReviewService::class));

        $this->getJson($url)->assertOk()
            ->assertJsonPath('invoice_number', '000081')
            ->assertJsonPath('date_text', '9 / ؟ / 2026')
            ->assertJsonPath('seller', 'متجر 123')
            ->assertJsonPath('items.0.description', 'صنف 4 / 5')
            ->assertJsonPath('items.0.quantity_text', '3')
            ->assertJsonPath('items.0.review_note', 'راجع 6');
        $model->refresh();
        $this->assertSame('۰۰٠۰۸١', $model->original_extraction['invoice_number']);
        $this->assertSame('صنف ٤ / ۵', $model->original_extraction['items'][0]['description']);
        $this->assertSame('raw ١۲', $model->raw_model_output);
        $this->assertSame('000081', $model->invoice_number);
    }

    public function test_thousands_shorthand_interpretations_remain_separate_and_require_review(): void
    {
        Queue::fake();
        $invoice = $this->upload();
        $url = '/api/invoices/'.$invoice['id'];
        $this->postJson($url.'/extract')->assertAccepted();
        $model = Invoice::findOrFail($invoice['id']);
        $candidate = $this->candidate();
        $candidate['written_total_text'] = '١٤٠،~~~';
        $candidate['written_total_interpreted_text'] = '۱۴۰۰۰۰';
        $candidate['items'][0]['quantity_text'] = '٢';
        $candidate['items'][0]['unit_price_text'] = '٧٠،~~~';
        $candidate['items'][0]['unit_price_interpreted_text'] = '٧٠٠٠٠';
        $candidate['items'][0]['written_amount_text'] = '١٤٠،~~~';
        $candidate['items'][0]['written_amount_interpreted_text'] = '١٤٠٠٠٠';
        Http::fake(['*' => Http::response(['extraction' => $candidate, 'raw_model_output' => 'synthetic response'])]);

        (new ExtractInvoice($model->id, $model->extraction_token))->handle(app(InvoiceReviewService::class));
        $review = $this->getJson($url)->assertOk()
            ->assertJsonPath('written_total_text', '140،~~~')
            ->assertJsonPath('written_total_interpreted_text', '140000')
            ->assertJsonPath('items.0.unit_price_text', '70،~~~')
            ->assertJsonPath('items.0.unit_price_interpreted_text', '70000')
            ->assertJsonPath('items.0.written_amount_interpreted_text', '140000')
            ->assertJsonPath('items.0.calculated_amount', '140000.0000')
            ->json();
        $this->assertContains('items.0.unit_price_interpreted_text', array_column($review['warnings'], 'field'));
        $this->assertContains('written_total_interpreted_text', array_column($review['warnings'], 'field'));
        $this->postJson($url.'/confirm', ['version' => $review['version'], 'acknowledged' => false])->assertUnprocessable();
        $this->postJson($url.'/confirm', ['version' => $review['version'], 'acknowledged' => true])->assertOk()->assertJsonPath('status', 'confirmed');

        $path = tempnam(sys_get_temp_dir(), 'shorthand-export-');
        try {
            app(InvoiceWorkbook::class)->write(Invoice::with('items')->get(), $path);
            $book = IOFactory::load($path);
            $this->assertSame('140،~~~', $book->getSheet(0)->getCell('F2')->getValue());
            $this->assertSame('K', $book->getSheet(0)->getHighestColumn());
            $this->assertSame('تفسير الإجمالي المكتوب', $book->getSheet(0)->getCell('K1')->getValue());
            $this->assertSame(140000.0, $book->getSheet(0)->getCell('K2')->getValue());
            $this->assertSame(DataType::TYPE_NUMERIC, $book->getSheet(0)->getCell('K2')->getDataType());
            $this->assertSame('H', $book->getSheet(1)->getHighestColumn());
            $this->assertSame(70000.0, $book->getSheet(1)->getCell('E2')->getValue());
            $this->assertSame(DataType::TYPE_NUMERIC, $book->getSheet(1)->getCell('E2')->getDataType());
            $this->assertSame(140000.0, $book->getSheet(1)->getCell('F2')->getValue());
            $this->assertSame(DataType::TYPE_NUMERIC, $book->getSheet(1)->getCell('F2')->getDataType());
            $book->disconnectWorksheets();
        } finally {
            unlink($path);
        }

        $edited = $candidate;
        $edited['written_total_text'] = '١٥٠،~~~';
        unset($edited['written_total_interpreted_text']);
        $edited['items'][0]['unit_price_text'] = '٧٥،~~~';
        $edited['items'][0]['unit_price_interpreted_text'] = null;
        $saved = $this->putJson($url, $edited + ['version' => $review['version']])->assertOk()->json();
        $this->assertNull($saved['written_total_interpreted_text']);
        $this->assertNull($saved['items'][0]['calculated_amount']);
        $this->assertNull($saved['items'][0]['unit_price_interpreted_text']);
        $this->assertContains('written_total_text', array_column($saved['warnings'], 'field'));
        $this->assertSame('synthetic response', $model->fresh()->raw_model_output);
        $this->assertSame('٧٠٠٠٠', $model->fresh()->original_extraction['items'][0]['unit_price_interpreted_text']);
    }

    public function test_failed_response_is_preserved_and_retry_is_possible(): void
    {
        Queue::fake();
        $invoice = $this->upload();
        $url = '/api/invoices/'.$invoice['id'];
        $this->postJson($url.'/extract')->assertAccepted();
        $model = Invoice::findOrFail($invoice['id']);
        Http::fake(['*' => Http::response(['raw_model_output' => 'malformed response'], 422)]);
        (new ExtractInvoice($model->id, $model->extraction_token))->handle(app(InvoiceReviewService::class));
        $this->assertSame('failed', $model->fresh()->status);
        $this->assertSame('malformed response', DB::table('extraction_attempts')->first()->raw_model_output);
        $this->postJson($url.'/extract')->assertAccepted();
        $this->assertDatabaseCount('extraction_attempts', 1);
    }

    public function test_provider_rate_limit_is_shown_without_exposing_service_details(): void
    {
        Queue::fake();
        $invoice = $this->upload();
        $url = '/api/invoices/'.$invoice['id'];
        $this->postJson($url.'/extract')->assertAccepted();
        $model = Invoice::findOrFail($invoice['id']);
        $model->update(['extraction_retry_count' => 3]);
        Http::fake(['*' => Http::response([
            'errors' => ['Provider HTTP 429'],
            'raw_model_output' => null,
            'provider_error' => [
                'http_status' => 429,
                'status' => 'RESOURCE_EXHAUSTED',
                'message' => 'private provider response',
                'response' => ['error' => ['details' => [['retryDelay' => '5s']]]],
            ],
        ], 422)]);

        (new ExtractInvoice($model->id, $model->extraction_token))->handle(app(InvoiceReviewService::class));

        $response = $this->getJson($url)->assertOk()->assertJsonPath('status', 'failed');
        $this->assertStringContainsString('429', $response->json('extraction_error'));
        $this->assertStringNotContainsString('private provider response', $response->getContent());
        $this->assertSame('failed', $model->fresh()->status);
        $attempt = DB::table('extraction_attempts')->first();
        $this->assertNull($attempt->raw_model_output);
        $this->assertSame('private provider response', json_decode($attempt->provider_error, true)['message']);
        $this->assertSame('5s', json_decode($attempt->provider_error, true)['response']['error']['details'][0]['retryDelay']);
        $this->postJson($url.'/extract')->assertAccepted();
    }

    public function test_invalid_model_output_has_a_specific_safe_failure_message(): void
    {
        Queue::fake();
        $invoice = $this->upload();
        $url = '/api/invoices/'.$invoice['id'];
        $this->postJson($url.'/extract')->assertAccepted();
        $model = Invoice::findOrFail($invoice['id']);
        Http::fake(['*' => Http::response([
            'errors' => ['Invalid structured output.'],
            'raw_model_output' => 'private model output',
        ], 422)]);

        (new ExtractInvoice($model->id, $model->extraction_token))->handle(app(InvoiceReviewService::class));

        $response = $this->getJson($url)->assertOk()->assertJsonPath('status', 'failed');
        $this->assertStringContainsString('بيانات منظمة', $response->json('extraction_error'));
        $this->assertStringNotContainsString('private model output', $response->getContent());
        $this->assertSame('private model output', DB::table('extraction_attempts')->first()->raw_model_output);
    }

    public function test_timeout_and_stale_worker_results_do_not_overwrite_review(): void
    {
        Queue::fake();
        $invoice = $this->upload();
        $model = Invoice::findOrFail($invoice['id']);
        $this->postJson('/api/invoices/'.$model->id.'/extract')->assertAccepted();
        $model->refresh();
        Http::fake(fn () => throw new ConnectionException('timeout'));
        (new ExtractInvoice($model->id, $model->extraction_token))->handle(app(InvoiceReviewService::class));
        $this->assertSame('failed', $model->fresh()->status);
        $this->postJson('/api/invoices/'.$model->id.'/extract')->assertAccepted();
        $model->refresh();
        $token = $model->extraction_token;
        $model->update(['extraction_started_at' => now()->subMinutes(6)]);
        $this->getJson('/api/invoices')->assertOk();
        $this->assertSame('failed', $model->fresh()->status);
        (new ExtractInvoice($model->id, $token))->handle(app(InvoiceReviewService::class));
        $this->assertSame('failed', $model->fresh()->status);
    }

    public function test_export_has_only_confirmed_records_literal_text_and_numeric_cells(): void
    {
        $invoice = $this->upload();
        $url = '/api/invoices/'.$invoice['id'];
        $data = $this->candidate();
        $data['written_total_interpreted_text'] = '=SUM(1,2)';
        $data['items'][0]['unit_price_interpreted_text'] = '=SUM(A1:A2)';
        $draft = $this->putJson($url, $data + ['version' => 1])->assertOk()->json();
        $this->postJson($url.'/confirm', ['version' => $draft['version'], 'acknowledged' => true])->assertOk();
        Invoice::create(['source_hash' => str_repeat('a', 64), 'source_filename' => 'pending.png', 'image_path' => 'missing', 'status' => 'pending']);
        $this->get('/api/exports/invoices')->assertOk()->assertHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        $path = tempnam(sys_get_temp_dir(), 'invoice-test-');
        try {
            app(InvoiceWorkbook::class)->write(Invoice::with('items')->get(), $path);
            $book = IOFactory::load($path);
            $this->assertSame(['الفواتير', 'الأصناف'], $book->getSheetNames());
            $headers = $book->getSheet(0);
            $items = $book->getSheet(1);
            $this->assertSame(2, $headers->getHighestRow());
            $this->assertSame('000081', $headers->getCell('B2')->getValue());
            $this->assertSame(DataType::TYPE_STRING, $headers->getCell('B2')->getDataType());
            $this->assertNull($headers->getCell('E2')->getValue());
            $this->assertSame('K', $headers->getHighestColumn());
            $this->assertSame('=SUM(1,2)', $headers->getCell('K2')->getValue());
            $this->assertSame(DataType::TYPE_STRING, $headers->getCell('K2')->getDataType());
            $this->assertSame('H', $items->getHighestColumn());
            $this->assertSame('=SUM(A1:A2)', $items->getCell('E2')->getValue());
            $this->assertSame(DataType::TYPE_STRING, $items->getCell('E2')->getDataType());
            $this->assertSame(DataType::TYPE_NUMERIC, $items->getCell('F2')->getDataType());
            $this->assertSame('=SUM(A1:A2)', $items->getCell('C2')->getValue());
            $this->assertSame(DataType::TYPE_STRING, $items->getCell('C2')->getDataType());
            foreach ($book->getAllSheets() as $sheet) {
                $this->assertTrue($sheet->getRightToLeft());
                $this->assertSame('A2', $sheet->getFreezePane());
            }
        } finally {
            unlink($path);
        }
    }

    public function test_cross_origin_mutations_are_rejected(): void
    {
        $this->withHeader('Origin', 'https://untrusted.example')->postJson('/api/invoices')->assertForbidden();
    }

    public function test_clear_all_deletes_every_invoice_and_stored_image(): void
    {
        Queue::fake();
        $this->upload();
        $this->postJson('/api/invoices', ['image' => UploadedFile::fake()->image('other.png', 2, 3)])->assertCreated();
        $this->assertDatabaseCount('invoices', 2);

        $paths = Invoice::pluck('image_path')->all();

        $response = $this->deleteJson('/api/invoices')->assertOk();
        $this->assertSame(2, $response->json('deleted'));
        $this->assertDatabaseCount('invoices', 0);
        $this->assertDatabaseCount('invoice_items', 0);

        foreach ($paths as $path) {
            Storage::disk('local')->assertMissing($path);
        }
    }

    public function test_clear_all_is_blocked_while_extraction_is_processing(): void
    {
        Queue::fake();
        $invoice = $this->upload();
        $this->postJson('/api/invoices/'.$invoice['id'].'/extract')->assertAccepted();

        $this->deleteJson('/api/invoices')->assertConflict();
        $this->assertDatabaseCount('invoices', 1);
    }
}
