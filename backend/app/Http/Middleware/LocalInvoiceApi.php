<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;

class LocalInvoiceApi
{
    public function handle(Request $request, Closure $next): mixed
    {
        abort_unless(in_array($request->ip(), ['127.0.0.1', '::1']), 403);
        if (! $request->isMethodSafe()) {
            abort_unless($request->header('X-Invoice-Client') === 'local-review', 403);
        }
        if ($origin = $request->header('Origin')) {
            abort_unless(in_array($origin, ['http://127.0.0.1:3000', 'http://localhost:3000']), 403);
        }

        return $next($request);
    }
}
