<?php

namespace App\Http\Controllers;

use App\Jobs\ExtractInvoice;
use App\Models\Invoice;
use App\Services\InvoiceContract;
use App\Services\InvoiceReviewService;
use App\Services\InvoiceWorkbook;
use Illuminate\Http\Request;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

class InvoiceController extends Controller
{
    public function __construct(private InvoiceReviewService $review) {}

    public function index(): mixed
    {
        // Recover a worker killed mid-request. Tokens make any late result harmless.
        Invoice::where('status', 'processing')->where('extraction_started_at', '<', now()->subMinutes(5))
            ->update(['status' => 'failed', 'extraction_token' => null, 'extraction_error' => 'انتهت مهلة الاستخراج. أعد المحاولة.']);

        return response()->json(Invoice::with('items')->orderBy('created_at')->get()->map(fn ($invoice) => $this->review->present($invoice)));
    }

    public function store(Request $request): mixed
    {
        $request->validate(['image' => ['required', 'file', 'image', 'mimes:jpg,jpeg,png', 'max:10240', 'dimensions:max_width=12000,max_height=12000']]);
        $file = $request->file('image');
        $hash = hash_file('sha256', $file->getRealPath());
        $existing = Invoice::where('source_hash', $hash)->first();
        if ($existing) {
            return response()->json(['invoice' => $this->review->present($existing), 'duplicate' => true]);
        }
        $path = 'invoices/'.$hash.'.'.$file->extension();
        abort_unless(Storage::disk('local')->put($path, file_get_contents($file->getRealPath())), 500, 'تعذر حفظ الصورة');
        $invoice = Invoice::firstOrCreate(['source_hash' => $hash], [
            'source_filename' => mb_substr(basename($file->getClientOriginalName()), 0, 255),
            'image_path' => $path, 'status' => 'pending', 'unresolved_fields' => [],
        ]);

        return response()->json(['invoice' => $this->review->present($invoice), 'duplicate' => ! $invoice->wasRecentlyCreated], $invoice->wasRecentlyCreated ? 201 : 200);
    }

    public function show(Invoice $invoice): mixed
    {
        return response()->json($this->review->present($invoice));
    }

    public function image(Invoice $invoice): mixed
    {
        return response()->file(Storage::disk('local')->path($invoice->image_path), ['Cache-Control' => 'no-store', 'X-Content-Type-Options' => 'nosniff']);
    }

    public function update(Request $request, Invoice $invoice): mixed
    {
        $data = $request->validate(InvoiceContract::rules() + ['version' => ['required', 'integer', 'min:1']]);

        return DB::transaction(function () use ($data, $invoice) {
            $invoice = Invoice::lockForUpdate()->findOrFail($invoice->id);
            abort_if($invoice->version !== $data['version'], 409, 'تغيرت الفاتورة. أعد تحميلها قبل الحفظ.');
            abort_if($invoice->status === 'processing', 409, 'انتظر انتهاء الاستخراج');
            $invoice->fill(Arr::except($data, ['items', 'version']));
            $invoice->status = 'review';
            $invoice->review_acknowledged = false;
            $invoice->version++;
            $invoice->save();
            $invoice->items()->delete();
            foreach ($data['items'] as $index => $item) {
                $invoice->items()->create($item + ['row_order' => $index + 1]);
            }
            $invoice->load('items');
            $this->review->refreshCalculatedAmounts($invoice);

            return response()->json($this->review->present($invoice->fresh('items')));
        });
    }

    public function confirm(Request $request, Invoice $invoice): mixed
    {
        $data = $request->validate(['version' => ['required', 'integer'], 'acknowledged' => ['required', 'boolean']]);

        return DB::transaction(function () use ($invoice, $data) {
            $invoice = Invoice::with('items')->lockForUpdate()->findOrFail($invoice->id);
            abort_if($invoice->version !== $data['version'], 409, 'تغيرت الفاتورة. أعد تحميلها.');
            if ($invoice->status === 'confirmed') {
                return response()->json($this->review->present($invoice));
            }
            abort_unless($invoice->status === 'review', 409, 'احفظ المراجعة أولاً');
            $this->review->refreshCalculatedAmounts($invoice);
            abort_if(count($this->review->warnings($invoice)) > 0 && ! $data['acknowledged'], 422, 'يجب الإقرار بالحقول والملاحظات المعلّمة');
            $invoice->update(['status' => 'confirmed', 'review_acknowledged' => $data['acknowledged']]);

            return response()->json($this->review->present($invoice));
        });
    }

    public function extract(Invoice $invoice): mixed
    {
        return DB::transaction(function () use ($invoice) {
            $invoice = Invoice::lockForUpdate()->findOrFail($invoice->id);
            // Never allow a retry to replace a saved human review.
            abort_unless(in_array($invoice->status, ['pending', 'failed']), 409, 'الاستخراج جارٍ أو تمت مراجعة الفاتورة');
            $token = (string) Str::uuid();
            $invoice->update(['status' => 'processing', 'extraction_token' => $token, 'extraction_started_at' => null, 'extraction_error' => null]);
            ExtractInvoice::dispatch($invoice->id, $token)->afterCommit();

            return response()->json($this->review->present($invoice), 202);
        });
    }

    public function export(InvoiceWorkbook $workbook): mixed
    {
        $invoices = DB::transaction(fn () => Invoice::with('items')->where('status', 'confirmed')->orderBy('created_at')->get());
        abort_if($invoices->isEmpty(), 422, 'لا توجد فواتير مؤكدة');

        return response()->streamDownload(function () use ($workbook, $invoices): void {
            $workbook->write($invoices, 'php://output');
        }, 'confirmed-invoices.xlsx', ['Content-Type' => 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Cache-Control' => 'no-store']);
    }
}
