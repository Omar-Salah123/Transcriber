<?php

namespace App\Services;

class WesternDigits
{
    public static function in(?string $value): ?string
    {
        if ($value === null) {
            return null;
        }

        return strtr($value, array_combine(
            preg_split('//u', '٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', -1, PREG_SPLIT_NO_EMPTY),
            str_split('01234567890123456789')
        ));
    }

    public static function inArray(array $values): array
    {
        foreach ($values as $key => $value) {
            if (is_string($value)) {
                $values[$key] = self::in($value);
            } elseif (is_array($value)) {
                $values[$key] = self::inArray($value);
            }
        }

        return $values;
    }
}
