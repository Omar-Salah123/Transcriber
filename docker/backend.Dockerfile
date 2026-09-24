FROM composer:2.8 AS composer
FROM php:8.4-cli-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpng-dev libjpeg62-turbo-dev libfreetype6-dev libzip-dev libsqlite3-dev \
    libonig-dev unzip \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j2 gd zip pdo_sqlite mbstring bcmath pcntl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer /usr/bin/composer /usr/local/bin/composer
WORKDIR /app
COPY backend/composer.json backend/composer.lock ./
RUN composer install --no-dev --no-scripts --no-autoloader --prefer-dist --no-interaction
COPY backend/ ./
RUN mkdir -p bootstrap/cache storage/framework/cache/data storage/framework/sessions storage/framework/views storage/logs \
    && composer dump-autoload --no-dev --optimize \
    && rm -rf storage && ln -s /data/storage storage \
    && chown -R www-data:www-data bootstrap/cache
COPY docker/backend-entrypoint.sh /usr/local/bin/invoice-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/invoice-entrypoint && chmod +x /usr/local/bin/invoice-entrypoint
USER www-data
ENTRYPOINT ["invoice-entrypoint"]
CMD ["php", "-d", "upload_max_filesize=11M", "-d", "post_max_size=12M", "-S", "127.0.0.1:8000", "../vendor/laravel/framework/src/Illuminate/Foundation/resources/server.php"]
