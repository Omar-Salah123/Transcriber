<?php

namespace App\Services;

use DateTimeInterface;
use Illuminate\Support\Facades\Cache;

class VertexRequestCooldown
{
    private const KEY = 'vertex-gemini-429-cooldown-until';

    private const LOCK_KEY = 'vertex-gemini-429-cooldown-lock';

    public static function remainingSeconds(): int
    {
        $until = (int) Cache::store('file')->get(self::KEY, 0);

        return max(0, $until - now()->getTimestamp());
    }

    public static function extendUntil(DateTimeInterface $until): void
    {
        $store = Cache::store('file');
        $untilTimestamp = $until->getTimestamp();

        $store->lock(self::LOCK_KEY, 10)->block(3, function () use ($store, $untilTimestamp): void {
            $current = (int) $store->get(self::KEY, 0);
            if ($untilTimestamp <= $current) {
                return;
            }

            $ttl = max(1, $untilTimestamp - now()->getTimestamp() + 60);
            $store->put(self::KEY, $untilTimestamp, $ttl);
        });
    }
}
