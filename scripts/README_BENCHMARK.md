# 🚀 EntropyGuard Benchmark Tool

Narzędzie do mierzenia wydajności i użycia pamięci EntropyGuard.

## Instalacja

### Wymagane zależności (opcjonalne):

Dla lepszego monitoringu pamięci:
```bash
pip install psutil
```

## Użycie

### Podstawowe użycie:

```bash
# Benchmark z 10K wierszami
python scripts/benchmark.py --size 10K

# Benchmark z wieloma rozmiarami
python scripts/benchmark.py --sizes 1K 10K 100K

# Zapisanie wyników do CSV
python scripts/benchmark.py --size 10K --output results.csv

# Zapisanie wyników do JSON
python scripts/benchmark.py --sizes 1K 10K 100K --format json --output results.json

# Dry-run (pomija kosztowne operacje, szybszy test)
python scripts/benchmark.py --size 10K --dry-run
```

## Parametry

- `--size SIZE`: Pojedynczy rozmiar do testowania (np. '1K', '10K', '100K', '1M')
- `--sizes SIZES ...`: Wiele rozmiarów do testowania (np. '1K 10K 100K')
- `--batch-size N`: Rozmiar batcha dla embeddings (domyślnie: 10000)
- `--output PATH`: Ścieżka do pliku wyjściowego (CSV lub JSON)
- `--format {csv,json}`: Format wyjściowy (domyślnie: csv)
- `--dry-run`: Pomija kosztowne operacje (szybszy, mniej dokładny)

## Metryki

Benchmark mierzy:

- **Processing Speed**: Wiersze na sekundę (rows/second)
- **Memory Usage**: Peak i średnie użycie pamięci (MB)
- **Memory Efficiency**: Pamięć na milion wierszy
- **Scalability**: Testy dla różnych rozmiarów danych (1K, 10K, 100K, 1M)

## Przykładowe wyniki

```
📊 BENCHMARK RESULTS
================================================================================
Size     Rows          Time (s)     Rows/sec        Peak Mem (MB)  
--------------------------------------------------------------------------------
1K       1,000         2.45         408             125.30         
10K      10,000        18.32        546             892.15         
100K     100,000       165.43       604             8156.23        
================================================================================

💾 Memory Efficiency (per 1M rows):
----------------------------------------
  1K: 125300.00 MB per 1M rows
  10K: 89215.00 MB per 1M rows
  100K: 81562.30 MB per 1M rows
```

## Użycie w CI/CD

Benchmark można użyć w CI/CD do śledzenia regresji wydajności:

```yaml
# GitHub Actions example
- name: Run benchmarks
  run: |
    python scripts/benchmark.py --sizes 1K 10K --format json --output benchmark_results.json
    
- name: Check performance regression
  run: |
    # Compare with baseline
    python scripts/compare_benchmarks.py baseline.json benchmark_results.json
```

## Interpretacja wyników

### Rows/second:
- **>1000 rows/sec**: Doskonała wydajność
- **500-1000 rows/sec**: Dobra wydajność
- **<500 rows/sec**: Może wymagać optymalizacji

### Memory per 1M rows:
- **<100 MB per 1M rows**: Bardzo efektywne
- **100-500 MB per 1M rows**: Akceptowalne
- **>500 MB per 1M rows**: Może wymagać optymalizacji

## Uwagi

- Dry-run mode pomija generowanie embeddings, więc wyniki są mniej dokładne
- Wymagane jest `psutil` dla dokładnego monitoringu pamięci (fallback do `tracemalloc`)
- Większe rozmiary (100K+) mogą wymagać więcej czasu i pamięci


