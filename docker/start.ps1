$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    docker compose build
    if ($LASTEXITCODE -ne 0) { throw 'Image build failed; running services were left untouched.' }
    docker compose down
    if ($LASTEXITCODE -ne 0) { throw 'Could not stop the stack; migration was not started.' }
    docker compose up -d --wait --wait-timeout 180
    if ($LASTEXITCODE -ne 0) { throw 'Startup failed. Inspect docker compose ps -a and docker compose logs.' }
    Write-Host 'Transcriber is ready at http://127.0.0.1:3000'
} finally {
    Pop-Location
}
