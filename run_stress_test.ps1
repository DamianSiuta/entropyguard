$CurrentDir = Get-Location
$Env:PYTHONPATH = "$CurrentDir\src"
Write-Host "Starting EntropyGuard Stress Test (10,000 rows)..." -ForegroundColor Yellow

# Start Timer
$sw = [System.Diagnostics.Stopwatch]::StartNew()

# Run Pipeline
python -m entropyguard.cli.main `
    --input stress_test.jsonl `
    --output stress_clean.jsonl `
    --text-column text `
    --min-length 10 `
    --dedup-threshold 0.85

# Stop Timer
$sw.Stop()
Write-Host "Stress Test Complete." -ForegroundColor Green
Write-Host "Execution Time: $($sw.Elapsed.TotalSeconds) seconds" -ForegroundColor Cyan



