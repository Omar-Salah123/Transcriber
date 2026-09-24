#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
docker compose build
docker compose down
docker compose up -d --wait --wait-timeout 180
echo 'Transcriber is ready at http://127.0.0.1:3000'
