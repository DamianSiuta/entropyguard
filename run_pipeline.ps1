$CurrentDir = Get-Location
$Env:PYTHONPATH = "$CurrentDir\src"
Write-Host "🚀 Starting EntropyGuard Pipeline..." -ForegroundColor Green
python -m entropyguard.cli.main --input demo_dirty.jsonl --output demo_clean.jsonl --text-column text --min-length 10 --dedup-threshold 0.8
Write-Host "✅ Done. Check demo_clean.jsonl" -ForegroundColor Green

