# Checkpoint/Resume Guide

## Przegląd

EntropyGuard v1.21 wprowadza mechanizm checkpoint/resume, który pozwala na:
- Zapis stanu pośredniego po każdym etapie przetwarzania
- Wznowienie przetwarzania z ostatniego checkpointu po błędzie
- Oszczędność czasu przy długotrwałych operacjach

## Użycie

### Podstawowe użycie

```bash
# Uruchom pipeline z checkpointami
entropyguard \
  --input data.jsonl \
  --output cleaned.jsonl \
  --text-column text \
  --checkpoint-dir ./checkpoints
```

### Resume po błędzie

```bash
# Jeśli pipeline się przerwie, wznowij z checkpointu
entropyguard \
  --input data.jsonl \
  --output cleaned.jsonl \
  --text-column text \
  --checkpoint-dir ./checkpoints \
  --resume
```

## Jak to działa

### Etapy z checkpointami

Checkpointy są zapisywane po następujących etapach:

1. **after_exact_dedup** - Po deduplikacji dokładnej (hash-based)
2. **after_semantic_dedup** - Po deduplikacji semantycznej (embedding-based)

### Format checkpointów

- **Pliki danych**: Parquet (efektywny format dla dużych zbiorów)
- **Metadata**: JSON z informacjami o checkpointie
- **Lokalizacja**: `{checkpoint_dir}/{stage}.parquet`

### Walidacja checkpointów

Przed użyciem checkpointu, system weryfikuje:
- ✅ Hash pliku wejściowego (czy plik się nie zmienił)
- ✅ Hash konfiguracji (czy parametry się nie zmieniły)
- ✅ Istnienie pliku checkpointu

Jeśli walidacja się nie powiedzie, checkpoint jest ignorowany i przetwarzanie zaczyna się od początku.

## Przykłady

### Przykład 1: Długotrwałe przetwarzanie

```bash
# Uruchom pipeline (może trwać kilka godzin)
entropyguard \
  --input 100gb_data.jsonl \
  --output cleaned.jsonl \
  --text-column text \
  --checkpoint-dir ./checkpoints

# Jeśli się przerwie (np. OOM), wznowij:
entropyguard \
  --input 100gb_data.jsonl \
  --output cleaned.jsonl \
  --text-column text \
  --checkpoint-dir ./checkpoints \
  --resume
```

### Przykład 2: Testowanie z checkpointami

```bash
# Przetwórz mały zbiór z checkpointami
entropyguard \
  --input test_data.jsonl \
  --output test_cleaned.jsonl \
  --text-column text \
  --checkpoint-dir ./test_checkpoints

# Sprawdź checkpointy
ls ./test_checkpoints/
# after_exact_dedup.parquet
# after_semantic_dedup.parquet
# checkpoint_metadata.json

# Wyczyść checkpointy po sukcesie
rm -rf ./test_checkpoints
```

## Ograniczenia

1. **Zmiana pliku wejściowego**: Jeśli plik wejściowy się zmieni, checkpointy są nieważne
2. **Zmiana konfiguracji**: Jeśli parametry się zmienią, checkpointy są nieważne
3. **Miejsce na dysku**: Checkpointy zajmują miejsce (mniej więcej tyle samo co dane pośrednie)

## Troubleshooting

### Problem: "Checkpoint invalid or not found"

**Przyczyna**: Plik wejściowy lub konfiguracja się zmieniły

**Rozwiązanie**: Uruchom bez `--resume` lub usuń stare checkpointy

### Problem: "Failed to load checkpoint"

**Przyczyna**: Plik checkpointu jest uszkodzony

**Rozwiązanie**: Usuń uszkodzony checkpoint i uruchom ponownie

### Problem: Checkpointy zajmują dużo miejsca

**Rozwiązanie**: Usuń checkpointy po sukcesie:
```bash
rm -rf ./checkpoints
```

Lub użyj `cleanup_checkpoints()` w kodzie Python.

## API (Python)

```python
from entropyguard.core.checkpoint import CheckpointManager
import polars as pl

# Utwórz manager
manager = CheckpointManager(checkpoint_dir="./checkpoints")

# Zapisz checkpoint
df = pl.DataFrame({"text": ["test"]})
manager.save_checkpoint(
    "after_exact_dedup",
    df,
    "input.jsonl",
    {"input_path": "input.jsonl", "dedup_threshold": 0.95}
)

# Wczytaj checkpoint
loaded_df = manager.load_checkpoint(
    "after_exact_dedup",
    "input.jsonl",
    {"input_path": "input.jsonl", "dedup_threshold": 0.95}
)

# Wyczyść checkpointy
manager.cleanup_checkpoints(keep_latest=False)
```

## Best Practices

1. **Używaj checkpointów dla dużych zbiorów** (>10GB)
2. **Wyczyść checkpointy po sukcesie** (oszczędność miejsca)
3. **Nie zmieniaj pliku wejściowego** podczas przetwarzania
4. **Nie zmieniaj konfiguracji** między uruchomieniami z resume
5. **Używaj osobnych katalogów** dla różnych zadań

## Zobacz też

- `IMPROVEMENTS_PLAN_V1.21.md` - Pełny plan ulepszeń
- `BRUTAL_AUDIT_V1.20.md` - Audit, który zidentyfikował potrzebę checkpointów

