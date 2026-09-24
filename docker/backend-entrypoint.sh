#!/bin/sh
set -eu
umask 0077
if [ "${1:-}" = "initialize" ]; then
    mkdir -p /data/storage/app/private /data/storage/framework/cache/data \
        /data/storage/framework/sessions /data/storage/framework/views /data/storage/logs
    if [ -s /data/database.sqlite ]; then
        if [ ! -s /data/app-key ]; then
            echo 'Existing database has no saved application key; restore its key before starting.' >&2
            exit 1
        fi
        mkdir -p /backups
        tar -czf "/backups/before-migration-$(date -u +%Y%m%dT%H%M%S)-$$.tar.gz" -C /data .
    fi
    if [ ! -s /data/app-key ]; then
        php -r 'echo "base64:".base64_encode(random_bytes(32));' > /data/app-key
    fi
    touch /data/database.sqlite
    export APP_KEY="$(cat /data/app-key)"
    php artisan migrate --force --no-interaction
    chown -R www-data:www-data /data
    exit 0
fi
if [ ! -s /data/app-key ]; then
    echo 'Missing application key. Run the documented Docker startup procedure.' >&2
    exit 1
fi
export APP_KEY="$(cat /data/app-key)"
exec "$@"
