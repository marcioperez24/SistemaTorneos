param(
    [string]$mensaje = "Actualización automática"
)

Write-Host "--- Iniciando sincronización ---" -ForegroundColor Cyan

git add -A

$changes = git diff --cached --name-only
if (-not $changes) {
    Write-Host "No hay cambios para subir." -ForegroundColor Yellow
    exit 0
}

git commit -m "$mensaje"
git push origin main

Write-Host "--- Cambios subidos a GitHub ---" -ForegroundColor Green
Write-Host "GitHub Actions hará el deploy al VPS." -ForegroundColor Green