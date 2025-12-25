# ============================================
# EntropyGuard PyPI Publishing Script
# ============================================
# This script builds and publishes the package to PyPI
# Usage: .\scripts\publish.ps1

$ErrorActionPreference = "Stop"

# Colors for output
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

Write-ColorOutput "🚀 EntropyGuard PyPI Publishing Script" "Green"
Write-ColorOutput "=====================================" "Green"
Write-Host ""

# Step 1: Reminder about PyPI token
Write-ColorOutput "📋 Step 1: PyPI Token Configuration" "Yellow"
Write-ColorOutput "=====================================" "Yellow"
Write-Host ""
Write-ColorOutput "⚠️  IMPORTANT: Make sure you have configured your PyPI token!" "Yellow"
Write-Host ""
Write-ColorOutput "If you have not configured it yet, run:" "Cyan"
Write-ColorOutput "  python -m poetry config pypi-token.pypi pypi-<your-token>" "Cyan"
Write-Host ""
Write-Host "Press any key to continue (or Ctrl+C to cancel)..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
Write-Host ""

# Step 2: Build package
Write-ColorOutput "📦 Step 2: Building package..." "Yellow"
Write-ColorOutput "=====================================" "Yellow"
Write-Host ""

try {
    python -m poetry build
    if ($LASTEXITCODE -ne 0) {
        throw "Poetry build failed with exit code $LASTEXITCODE"
    }
    Write-ColorOutput "✅ Package built successfully" "Green"
} catch {
    Write-ColorOutput "❌ Build failed: $_" "Red"
    exit 1
}
Write-Host ""

# Step 3: Publish to PyPI
Write-ColorOutput "🚀 Step 3: Publishing to PyPI..." "Yellow"
Write-ColorOutput "=====================================" "Yellow"
Write-Host ""

Write-ColorOutput "⚠️  This will publish the package to PyPI. Are you sure?" "Yellow"
Write-Host ""
Write-Host "Press any key to continue (or Ctrl+C to cancel)..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
Write-Host ""

try {
    python -m poetry publish
    if ($LASTEXITCODE -ne 0) {
        throw "Poetry publish failed with exit code $LASTEXITCODE"
    }
    Write-ColorOutput "✅ Package published successfully to PyPI!" "Green"
} catch {
    Write-ColorOutput "❌ Publish failed: $_" "Red"
    exit 1
}
Write-Host ""

Write-ColorOutput "🎉 Publishing complete!" "Green"
Write-ColorOutput "=====================================" "Green"
Write-Host ""
Write-ColorOutput "Your package is now available on PyPI:" "Cyan"
Write-ColorOutput "  pip install entropyguard" "Cyan"
Write-Host ""

