# Setup Playwright for Windows (PowerShell)

Write-Host "🚀 Setting up Playwright..." -ForegroundColor Cyan

# Check if we are in a virtual environment
if ($env:VIRTUAL_ENV -eq $null) {
    Write-Host "⚠️  Warning: You are not in a virtual environment. It is recommended to use one." -ForegroundColor Yellow
    $confirm = Read-Host "Do you want to continue anyway? (y/N)"
    if ($confirm -ne "y") {
        exit
    }
}

Write-Host "📦 Installing playwright python package..." -ForegroundColor Cyan
pip install playwright

Write-Host "🌐 Downloading Chromium browser..." -ForegroundColor Cyan
playwright install chromium

Write-Host "✅ Playwright setup complete!" -ForegroundColor Green
