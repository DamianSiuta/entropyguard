# 🛡️ EntropyGuard - Kompleksowa Dokumentacja Projektu

## 📋 Spis Treści

1. [Wprowadzenie i Cel Projektu](#wprowadzenie-i-cel-projektu)
2. [Problem: Model Collapse](#problem-model-collapse)
3. [Architektura Systemu](#architektura-systemu)
4. [Szczegółowy Pipeline](#szczegółowy-pipeline)
5. [Komponenty i Moduły](#komponenty-i-moduły)
6. [Hybrid Deduplication Engine](#hybrid-deduplication-engine)
7. [Memory Management i Optymalizacje](#memory-management-i-optymalizacje)
8. [CLI Interface](#cli-interface)
9. [Error Handling](#error-handling)
10. [Configuration Management](#configuration-management)
11. [Performance i Benchmarking](#performance-i-benchmarking)
12. [Testing Strategy](#testing-strategy)
13. [Deployment i Distribution](#deployment-i-distribution)
14. [Roadmap i Wersjonowanie](#roadmap-i-wersjonowanie)

---

## 1. Wprowadzenie i Cel Projektu

### 1.1 Co to jest EntropyGuard?

**EntropyGuard** to zaawansowany, produkcyjny system inżynierii danych zaprojektowany specjalnie do optymalizacji danych treningowych dla Large Language Models (LLM). Jest to kompleksowe narzędzie CLI, które rozwiązuje krytyczny problem degradacji jakości modeli ML spowodowany treningiem na niskiej jakości, zduplikowanych lub zanieczyszczonych danych.

### 1.2 Główne Cele Projektu

1. **Zapobieganie Model Collapse**: Eliminacja zduplikowanych i niskiej jakości danych przed treningiem modeli
2. **Lokalne Przetwarzanie**: 100% lokalne wykonanie, bez wysyłania danych do zewnętrznych API
3. **Wysoka Wydajność**: Optymalizacja pod kątem szybkości i efektywności pamięciowej
4. **Enterprise-Grade**: Produkcyjna jakość kodu z pełnym testowaniem i dokumentacją
5. **Uniwersalność**: Obsługa wielu formatów danych i integracja z istniejącymi pipeline'ami

### 1.3 Kluczowe Wartości

- **Privacy-First**: Wszystkie dane przetwarzane lokalnie, zero wycieków do chmury
- **Air-Gap Compatible**: Działa w środowiskach izolowanych, bez dostępu do internetu
- **CPU-Only**: Nie wymaga GPU, działa na standardowych serwerach
- **Open Source Core**: Podstawowa funkcjonalność dostępna jako open source (MIT License)

---

## 2. Problem: Model Collapse

### 2.1 Czym jest Model Collapse?

**Model Collapse** to zjawisko, w którym modele ML stopniowo tracą jakość podczas treningu na danych zawierających:
- **Duplikaty**: Identyczne lub bardzo podobne przykłady
- **Niską jakość**: Puste, zanieczyszczone lub nieprawidłowe dane
- **Bias**: Przesunięcie w kierunku najczęściej występujących wzorców

### 2.2 Dlaczego to Problem?

1. **Degradacja Jakości**: Model uczy się zamiast rzeczywistych wzorców, powtarza zduplikowane dane
2. **Waste of Resources**: Przetwarzanie zduplikowanych danych marnuje czas i zasoby
3. **Koszty**: W przypadku API (np. OpenAI embeddings), duplikaty generują niepotrzebne koszty
4. **Compliance**: Zduplikowane dane mogą naruszać zasady GDPR/CCPA

### 2.3 Jak EntropyGuard to Rozwiązuje?

EntropyGuard implementuje **hybrid deduplication strategy**:
- **Stage 1**: Szybkie usuwanie dokładnych duplikatów (hash-based)
- **Stage 2**: Wykrywanie semantycznych duplikatów (AI-based)
- **Stage 3**: Walidacja i filtrowanie niskiej jakości danych

---

## 3. Architektura Systemu

### 3.1 Ogólna Architektura

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Interface (main.py)                  │
│  - Argument parsing                                         │
│  - Signal handling (SIGINT/SIGTERM)                        │
│  - Error handling & reporting                              │
│  - Configuration loading                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Core Pipeline (pipeline.py)               │
│  - Orchestration logic                                      │
│  - Stage coordination                                       │
│  - Memory profiling                                         │
│  - Progress tracking                                        │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────┘
       │          │          │          │          │
       ▼          ▼          ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│Ingestion │ │Sanitize  │ │Chunking  │ │Dedupe    │ │Validation│
│          │ │          │ │          │ │          │ │          │
│loader.py │ │sanitize  │ │splitter  │ │embedder  │ │validator │
│          │ │_lazy.py  │ │.py       │ │+index.py │ │.py       │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

### 3.2 Struktura Modułów

```
src/entropyguard/
├── __init__.py              # Package initialization, version
├── cli/
│   └── main.py              # CLI entry point, argument parsing
├── core/
│   ├── __init__.py          # Core exports
│   ├── pipeline.py          # Main pipeline orchestration
│   ├── errors.py            # Exception hierarchy
│   ├── types.py             # Type definitions (TypedDict, dataclass)
│   ├── config_loader.py     # Config file loading (JSON/YAML/TOML)
│   ├── memory_profiler.py   # Memory usage tracking
│   └── sanitization_lazy.py # Lazy sanitization functions
├── ingestion/
│   └── loader.py            # Universal data loader (Excel/Parquet/CSV/JSONL)
├── sanitization/
│   └── core.py              # PII removal, HTML stripping
├── chunking/
│   └── splitter.py          # Text chunking for RAG
├── deduplication/
│   ├── embedder.py          # Sentence-transformers wrapper
│   └── index.py             # FAISS vector index wrapper
└── validation/
    └── validator.py         # Data quality validation
```

### 3.3 Design Principles

1. **Separation of Concerns**: Business logic (`core/`) oddzielona od CLI (`cli/`)
2. **Lazy Evaluation**: Polars LazyFrame dla efektywności pamięciowej
3. **Type Safety**: Pełne type hints, TypedDict, dataclasses
4. **Structured Errors**: Hierarchia wyjątków z kodami błędów
5. **Testability**: Każdy moduł testowalny niezależnie

---

## 4. Szczegółowy Pipeline

### 4.1 Przepływ Danych

```
[Raw Data Input]
    │
    ├─ JSONL/NDJSON
    ├─ CSV
    ├─ Excel (.xlsx)
    ├─ Parquet
    └─ stdin (Unix pipes)
    │
    ▼
[STEP 1: Ingestion]
    │
    ├─ Auto-detect format
    ├─ Load as Polars LazyFrame
    └─ Schema detection (lazy)
    │
    ▼
[STEP 2: Schema Validation]
    │
    ├─ Check required columns (if specified)
    ├─ Auto-detect text column (if not specified)
    └─ All operations on LazyFrame (no materialization)
    │
    ▼
[STEP 3: Sanitization]
    │
    ├─ Lowercase normalization
    ├─ Whitespace normalization
    ├─ Drop nulls
    └─ PII removal (hybrid: lazy + chunked materialization)
    │
    ▼
[STEP 4: Chunking (Optional)]
    │
    ├─ Only if --chunk-size provided
    ├─ Recursive splitting (paragraph → line → word → char)
    ├─ Configurable separators
    └─ Overlap support for RAG
    │
    ▼
[STEP 5: Materialization]
    │
    ├─ Collect LazyFrame to DataFrame
    ├─ Add _original_index column
    └─ Prepare for deduplication
    │
    ▼
[STEP 6: Stage 1 - Exact Deduplication]
    │
    ├─ Calculate xxhash for each text
    ├─ Group by hash
    ├─ Keep first occurrence
    └─ Fast hash-based filtering
    │
    ▼
[STEP 7: Stage 2 - Semantic Deduplication]
    │
    ├─ Process in batches (configurable --batch-size)
    ├─ Generate embeddings (sentence-transformers)
    ├─ Add to FAISS index incrementally
    ├─ Find duplicates (cosine similarity)
    └─ Filter semantic duplicates
    │
    ▼
[STEP 8: Validation]
    │
    ├─ Check min_length
    ├─ Drop empty/null texts
    └─ Final quality gates
    │
    ▼
[STEP 9: Output]
    │
    ├─ Write to file (NDJSON)
    ├─ Or stdout (for pipes)
    └─ Generate audit log (optional)
```

### 4.2 Szczegóły Każdego Etapu

#### STEP 1: Ingestion (`ingestion/loader.py`)

**Cel**: Załadowanie danych z różnych formatów do jednolitej reprezentacji Polars LazyFrame.

**Obsługiwane formaty**:
- **NDJSON/JSONL**: `pl.scan_ndjson()` - natywne wsparcie Polars
- **CSV**: `pl.scan_csv()` - z auto-detection separatorów
- **Parquet**: `pl.scan_parquet()` - efektywny format kolumnowy
- **Excel**: `pl.read_excel()` → `.lazy()` - wymaga `fastexcel`
- **JSON**: `pl.read_json()` → `.lazy()` - dla pojedynczych plików JSON

**Dlaczego LazyFrame?**
- **Memory Efficiency**: Nie ładuje całego datasetu do pamięci
- **Query Optimization**: Polars optymalizuje zapytania przed wykonaniem
- **Streaming**: Możliwość przetwarzania danych większych niż RAM

**Implementacja**:
```python
def load_dataset(input_path: str) -> pl.LazyFrame:
    """Universal loader with format auto-detection."""
    path = Path(input_path)
    suffix = path.suffix.lower()
    
    if suffix in ['.ndjson', '.jsonl']:
        return pl.scan_ndjson(input_path)
    elif suffix == '.csv':
        return pl.scan_csv(input_path)
    elif suffix == '.parquet':
        return pl.scan_parquet(input_path)
    # ... etc
```

#### STEP 2: Schema Validation

**Cel**: Weryfikacja struktury danych bez materializacji.

**Operacje**:
- Sprawdzenie wymaganych kolumn (jeśli `--required-columns` podane)
- Auto-detection kolumny tekstowej (pierwsza kolumna typu `Utf8`)
- Wszystko na `lf.schema` (tylko metadane, zero materializacji)

**Dlaczego Lazy?**
- Szybkość: Sprawdzenie schematu to O(1) operacja
- Memory: Nie ładujemy danych do pamięci
- Early Validation: Błędy wykrywane przed kosztownym przetwarzaniem

#### STEP 3: Sanitization (`core/sanitization_lazy.py`)

**Cel**: Normalizacja i czyszczenie tekstu.

**Operacje Lazy (na LazyFrame)**:
- `str.to_lowercase()` - lowercase
- `str.strip_chars()` - usuwanie białych znaków
- `drop_nulls()` - usuwanie nulli

**Operacje Wymagające Materializacji**:
- **PII Removal**: Wymaga Python functions (regex), więc materializujemy w chunkach
- **Hybrid Approach**: Lazy operations → chunked materialization → lazy again

**Dlaczego Hybrid?**
- PII removal jest wczesnym etapem (przed kosztownym embedding)
- Główny OOM risk jest w Stage 2 (embeddings)
- Chunked materialization pozwala przetwarzać duże pliki bez OOM

**Implementacja**:
```python
def sanitize_lazyframe(lf: pl.LazyFrame, config, text_columns):
    # Lazy operations first
    lf = lf.with_columns([
        pl.col(col).str.to_lowercase().str.strip_chars()
        for col in text_columns
    ])
    lf = lf.drop_nulls()
    
    # PII removal requires materialization (chunked)
    if config.remove_pii:
        df = lf.collect()  # Materialize
        # Apply PII removal in chunks
        # ...
        lf = df.lazy()  # Back to lazy
    
    return lf
```

#### STEP 4: Chunking (`chunking/splitter.py`)

**Cel**: Podział długich tekstów na mniejsze fragmenty (dla RAG).

**Kiedy używane?**
- Tylko jeśli `--chunk-size` jest podane
- Typowo dla RAG workflows (Retrieval-Augmented Generation)

**Strategia**:
1. **Recursive Splitting**: Próbuje podzielić w kolejności:
   - Paragraph breaks (`\n\n`)
   - Line breaks (`\n`)
   - Word boundaries (` `)
   - Character-level (dla CJK languages)

2. **Overlap**: Konfigurowalny overlap między chunkami (domyślnie 50 znaków)

3. **Separators**: Możliwość podania własnych separatorów

**Dlaczego Materializacja?**
- Chunking wymaga Python functions (regex, string manipulation)
- Ale dzieje się PRZED kosztownym embedding stage
- Akceptowalne trade-off

#### STEP 5: Materialization

**Cel**: Konwersja LazyFrame do DataFrame dla deduplication.

**Dlaczego Teraz?**
- Hash calculation (Stage 1) wymaga dostępu do wartości
- Polars hash operations są szybkie
- Główny OOM risk jest w Stage 2 (embeddings), nie tutaj

**Operacje**:
- `lf.collect()` - materializacja
- Dodanie `_original_index` kolumny (dla tracking)
- Sprawdzenie czy dataset nie jest pusty

#### STEP 6: Stage 1 - Exact Deduplication

**Cel**: Szybkie usunięcie dokładnych duplikatów.

**Algorytm**:
1. Dla każdego tekstu: oblicz `xxhash` (lub MD5 fallback)
2. Normalizacja przed hashowaniem: lowercase + whitespace normalization
3. Grupowanie po hash: `rank().over("_text_hash")`
4. Filtrowanie: `filter(rank == 1)` - zostaw tylko pierwszy

**Dlaczego xxhash?**
- **Szybkość**: xxhash jest ~10x szybszy niż MD5
- **Non-cryptographic**: Nie potrzebujemy kryptograficznego hash (tylko deduplication)
- **Deterministic**: Ten sam tekst → ten sam hash

**Performance**:
- ~5000-6000 rows/second (na CPU)
- Memory: O(n) gdzie n = liczba unikalnych hashów

**Implementacja**:
```python
# Calculate hashes
text_hashes = [calculate_text_hash(text) for text in texts]

# Add hash column
df = df.with_columns(pl.Series("_text_hash", text_hashes))

# Group by hash, keep first
lf_dedup = df.lazy().with_columns(
    pl.col("_original_index").rank("dense").over("_text_hash").alias("_hash_rank")
).filter(pl.col("_hash_rank") == 1)
```

#### STEP 7: Stage 2 - Semantic Deduplication

**Cel**: Wykrywanie semantycznych duplikatów (różne słowa, podobne znaczenie).

**Algorytm**:
1. **Batched Embeddings**: 
   - Podziel teksty na batche (domyślnie 10,000)
   - Dla każdego batcha: wygeneruj embeddings (sentence-transformers)
   - Dodaj do FAISS index incrementally

2. **FAISS Index**:
   - Typ: `IndexFlatL2` (L2 distance)
   - Dimension: 384 (dla `all-MiniLM-L6-v2`)
   - Keep index in memory (nie release chunks)

3. **Duplicate Detection**:
   - Po dodaniu wszystkich embeddings: `index.find_duplicates(threshold)`
   - Threshold: `(2.0 * (1.0 - similarity)) ** 0.5` (konwersja cosine → L2)
   - Dla każdej grupy duplikatów: zostaw pierwszy, usuń resztę

**Dlaczego Batched?**
- **Memory Safety**: Nie ładujemy wszystkich embeddings naraz
- **Scalability**: Możemy przetwarzać miliony wierszy
- **Performance**: Batch processing jest efektywny dla GPU/CPU

**Dlaczego FAISS?**
- **Speed**: FAISS jest zoptymalizowany do vector search
- **Memory**: Kompaktowa reprezentacja wektorów
- **Scalability**: Obsługuje miliony wektorów

**Model Selection**:
- **Default**: `all-MiniLM-L6-v2` (384 dim, 22M params, fast)
- **Multilingual**: `paraphrase-multilingual-MiniLM-L12-v2` (384 dim, slower)
- **Configurable**: `--model-name` flag

**Implementacja**:
```python
# Initialize FAISS index
index = VectorIndex(dimension=384)

# Process in batches
for batch_idx in range(0, len(texts), batch_size):
    batch_texts = texts[batch_idx:batch_idx + batch_size]
    
    # Generate embeddings
    batch_embeddings = embedder.embed(batch_texts)
    
    # Add to index
    index.add_vectors(batch_embeddings)

# Find duplicates
duplicate_groups = index.find_duplicates(threshold=distance_threshold)
```

#### STEP 8: Validation

**Cel**: Finalne quality gates przed zapisem.

**Sprawdzane**:
- `min_length`: Minimalna długość tekstu (domyślnie 50 znaków)
- Empty/null texts: Usuwanie pustych wartości
- Stripped length: Po usunięciu białych znaków

**Dlaczego Ostatnie?**
- Sprawdzamy po wszystkich transformacjach
- Zapewniamy że output jest wysokiej jakości

#### STEP 9: Output

**Cel**: Zapis przetworzonych danych.

**Formaty**:
- **NDJSON/JSONL**: Jeden JSON object per line
- **stdout**: Dla Unix pipes (wszystkie logi na stderr)

**Audit Log** (opcjonalny):
- JSON file z każdym usuniętym wierszem
- Powód usunięcia (exact_duplicate, semantic_duplicate, validation)
- Original index dla traceability

---

## 5. Komponenty i Moduły

### 5.1 Core Module (`core/`)

#### `pipeline.py` - Main Orchestration

**Klasa**: `Pipeline`

**Odpowiedzialność**:
- Koordynacja wszystkich etapów pipeline
- Zarządzanie komponentami (validator, chunker, embedder, index)
- Error handling z structured exceptions
- Progress tracking (tqdm)
- Memory profiling integration

**Kluczowe Metody**:
- `__init__(model_name)`: Inicjalizacja komponentów
- `run(config: PipelineConfig) -> PipelineResult`: Główna metoda wykonania

**Design Decisions**:
- **Separation**: Business logic oddzielona od CLI
- **Config Object**: Typed `PipelineConfig` dataclass zamiast dict
- **Result Object**: Typed `PipelineResult` TypedDict dla type safety
- **Exception Hierarchy**: Structured errors zamiast generic exceptions

#### `errors.py` - Exception Hierarchy

**Struktura**:
```python
PipelineError (base)
├── ValidationError (code=2)    # Input validation issues
├── ResourceError (code=3)      # OOM, disk space, IO
└── ProcessingError (code=1)    # Embedding, FAISS failures
```

**Dlaczego Hierarchia?**
- **Structured Handling**: CLI może obsłużyć różne typy błędów inaczej
- **Exit Codes**: Różne kody wyjścia dla różnych błędów
- **User-Friendly**: Konkretne komunikaty błędów z hints

**Atrybuty**:
- `message`: Główny komunikat błędu
- `code`: Exit code (1, 2, 3)
- `category`: Kategoria błędu (validation, resource, processing)
- `hint`: Opcjonalna wskazówka dla użytkownika

#### `types.py` - Type Definitions

**Typy**:
- `PipelineStats` (TypedDict): Statystyki pipeline (rows, duplicates, etc.)
- `PipelineResult` (TypedDict): Wynik pipeline (success, stats, output_path)
- `PipelineConfig` (dataclass): Konfiguracja pipeline

**Dlaczego TypedDict + dataclass?**
- **Type Safety**: MyPy może sprawdzić typy
- **Runtime Validation**: Pydantic może walidować (future)
- **IDE Support**: Autocomplete i type hints

#### `config_loader.py` - Configuration Management

**Funkcje**:
- `load_config_file(path)`: Ładowanie z JSON/YAML/TOML
- `merge_config_with_args(config, args)`: Merge config file + CLI args

**Auto-Detection**:
- Szuka `.entropyguardrc.json/yaml/toml` w:
  - Current directory
  - Home directory

**Priority**:
1. CLI arguments (najwyższy priorytet)
2. Config file
3. Defaults

**Dlaczego Config Files?**
- **Convenience**: Nie trzeba powtarzać argumentów
- **Team Consistency**: Wspólna konfiguracja w repo
- **CI/CD**: Łatwiejsza automatyzacja

#### `memory_profiler.py` - Memory Tracking

**Klasa**: `MemoryProfiler`

**Funkcje**:
- `snapshot(stage)`: Wykonanie snapshot pamięci na etapie
- `get_report() -> dict`: Generowanie raportu
- `save_report_json(path)`: Zapis do JSON
- `print_summary()`: Wyświetlenie podsumowania

**Backend Options**:
- **psutil** (preferred): Dokładne monitorowanie procesu
- **tracemalloc** (fallback): Built-in Python, mniej dokładny

**Użycie**:
- `--profile-memory`: Włącza profiling
- `--memory-report-path`: Ścieżka do zapisu raportu

**Dlaczego Memory Profiling?**
- **Debugging OOM**: Identyfikacja etapów z wysokim użyciem pamięci
- **Optimization**: Znajdowanie bottlenecków pamięciowych
- **Capacity Planning**: Planowanie zasobów dla dużych datasetów

#### `sanitization_lazy.py` - Lazy Sanitization

**Funkcja**: `sanitize_lazyframe(lf, config, text_columns) -> LazyFrame`

**Operacje**:
- Lazy: lowercase, strip, drop_nulls
- Hybrid: PII removal (chunked materialization)

**Dlaczego Lazy?**
- **Memory Efficiency**: Nie materializujemy całego datasetu
- **Performance**: Polars optymalizuje operacje
- **Scalability**: Możemy przetwarzać dane > RAM

### 5.2 Ingestion Module (`ingestion/`)

#### `loader.py` - Universal Data Loader

**Funkcja**: `load_dataset(input_path) -> LazyFrame`

**Obsługiwane Formaty**:
- **NDJSON/JSONL**: `pl.scan_ndjson()` - streaming support
- **CSV**: `pl.scan_csv()` - auto-detection separatorów
- **Parquet**: `pl.scan_parquet()` - columnar format
- **Excel**: `pl.read_excel()` → `.lazy()` - wymaga fastexcel
- **JSON**: `pl.read_json()` → `.lazy()` - single JSON file

**Auto-Detection**:
- Na podstawie file extension
- Fallback: próba wszystkich formatów

**Error Handling**:
- `FileNotFoundError`: Plik nie istnieje
- `ValueError`: Nieobsługiwany format lub corrupted file

### 5.3 Sanitization Module (`sanitization/`)

#### `core.py` - PII Removal & Text Cleaning

**Funkcje**:
- `remove_pii(text)`: Usuwanie emails, phones, IDs (regex-based)
- `remove_html_tags(text)`: Usuwanie HTML tags
- `normalize_text(text)`: Normalizacja whitespace

**PII Patterns**:
- Email: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
- Phone: Różne formaty (US, EU, etc.)
- SSN/ID: Konfigurowalne wzorce

**Dlaczego Regex?**
- **Speed**: Regex jest szybki dla prostych wzorców
- **No Dependencies**: Nie wymaga zewnętrznych bibliotek
- **Configurable**: Łatwo dodać nowe wzorce

### 5.4 Chunking Module (`chunking/`)

#### `splitter.py` - Text Chunking

**Klasa**: `Chunker`

**Strategia**:
1. **Recursive Splitting**: Próbuje podzielić w kolejności separatorów
2. **Overlap**: Konfigurowalny overlap między chunkami
3. **Fallback**: Character-level dla CJK languages

**Separators Hierarchy**:
- Default: `["\n\n", "\n", " ", ""]` (paragraph → line → word → char)
- Custom: `--separators` flag

**Użycie**:
- RAG workflows (Retrieval-Augmented Generation)
- Long document processing
- Context window limitations

### 5.5 Deduplication Module (`deduplication/`)

#### `embedder.py` - Sentence Embeddings

**Klasa**: `Embedder`

**Backend**: `sentence-transformers`

**Funkcje**:
- `embed(texts: list[str]) -> np.ndarray`: Generowanie embeddings
- Batch processing dla efektywności

**Model Selection**:
- Default: `all-MiniLM-L6-v2` (384 dim, fast, English)
- Multilingual: `paraphrase-multilingual-MiniLM-L12-v2` (384 dim, slower)

**Dlaczego sentence-transformers?**
- **State-of-the-art**: Najlepsze modele dla sentence embeddings
- **Easy Integration**: Prosty API
- **Model Hub**: Dostęp do wielu pre-trained models

#### `index.py` - FAISS Vector Index

**Klasa**: `VectorIndex`

**Backend**: `faiss-cpu`

**Typ Indexu**: `IndexFlatL2` (L2 distance)

**Funkcje**:
- `add_vectors(embeddings)`: Dodawanie wektorów do indexu
- `find_duplicates(threshold) -> list[list[int]]`: Znajdowanie duplikatów

**Algorytm Duplicate Detection**:
1. Dla każdego wektora: znajdź najbliższych sąsiadów (L2 distance)
2. Jeśli distance < threshold: to duplikat
3. Grupowanie: connected components (jeśli A podobny do B i B podobny do C, to A, B, C są w jednej grupie)

**Dlaczego FAISS?**
- **Speed**: Zoptymalizowany do vector search
- **Memory**: Kompaktowa reprezentacja
- **Scalability**: Obsługuje miliony wektorów

### 5.6 Validation Module (`validation/`)

#### `validator.py` - Data Quality Validation

**Klasa**: `DataValidator`

**Funkcje**:
- `validate_data(df, text_column, min_text_length) -> ValidationResult`
- Sprawdzanie `min_length`
- Usuwanie empty/null texts

**Result Object**:
- `success: bool`
- `df: Optional[DataFrame]`
- `error: Optional[str]`
- `report: Optional[dict]`

---

## 6. Hybrid Deduplication Engine

### 6.1 Dlaczego Hybrid?

**Problem**: Semantyczna deduplication jest kosztowna (embeddings + vector search).

**Rozwiązanie**: Dwuetapowa strategia:
1. **Stage 1 (Fast)**: Usuń dokładne duplikaty (hash-based, ~5000 rows/sec)
2. **Stage 2 (Smart)**: Usuń semantyczne duplikaty (AI-based, tylko na survivors)

**Korzyści**:
- **Performance**: Stage 1 usuwa 50-80% duplikatów szybko
- **Cost Savings**: Mniej embeddings do wygenerowania
- **Accuracy**: Stage 2 znajduje duplikaty, które Stage 1 przegapił

### 6.2 Stage 1: Exact Deduplication

**Algorytm**:
1. Normalizacja tekstu (lowercase + whitespace)
2. Hash calculation (xxhash lub MD5)
3. Grupowanie po hash
4. Zostaw pierwszy, usuń resztę

**Performance**:
- ~5000-6000 rows/second
- Memory: O(n) gdzie n = unikalne hashe
- CPU-only, zero GPU

**Przykład**:
```
Text 1: "Hello World"
Text 2: "hello world"  (lowercase)
Text 3: "Hello  World"  (extra spaces)

Po normalizacji: wszystkie → "hello world"
Hash: wszystkie → same hash
Result: Zostaje tylko Text 1
```

### 6.3 Stage 2: Semantic Deduplication

**Algorytm**:
1. Batch processing (domyślnie 10,000 rows/batch)
2. Embedding generation (sentence-transformers)
3. FAISS index (L2 distance)
4. Duplicate detection (threshold-based)
5. Filtering (zostaw pierwszy w każdej grupie)

**Performance**:
- ~500-1000 rows/second (zależy od modelu)
- Memory: O(n * d) gdzie n = liczba wektorów, d = dimension (384)
- CPU-only (może użyć GPU jeśli dostępne)

**Przykład**:
```
Text 1: "What is the weather today?"
Text 2: "How's the weather?"
Text 3: "Tell me about today's weather"

Wszystkie mają podobne znaczenie
Embeddings: Wszystkie blisko siebie w przestrzeni wektorowej
Result: Zostaje tylko Text 1
```

### 6.4 Threshold Configuration

**Default**: `--dedup-threshold 0.95` (95% similarity)

**Interpretacja**:
- `0.95`: Bardzo podobne (stricter, mniej duplikatów)
- `0.85`: Umiarkowanie podobne (looser, więcej duplikatów)
- `0.99`: Prawie identyczne (very strict)

**Konwersja**:
- Cosine similarity → L2 distance: `distance = sqrt(2 * (1 - similarity))`
- Przykład: similarity=0.95 → distance ≈ 0.316

---

## 7. Memory Management i Optymalizacje

### 7.1 Lazy Evaluation Strategy

**Polars LazyFrame**:
- **Query Planning**: Polars planuje zapytania przed wykonaniem
- **Optimization**: Automatyczne optymalizacje (predicate pushdown, projection)
- **Materialization**: Dane materializowane tylko gdy potrzebne

**Kiedy Materializujemy?**
1. **Chunking**: Wymaga Python functions (regex)
2. **Stage 1 Deduplication**: Hash calculation wymaga wartości
3. **Stage 2 Deduplication**: Embeddings wymagają wartości

**Kiedy NIE Materializujemy?**
1. **Schema Validation**: Tylko metadane (`lf.schema`)
2. **Lazy Sanitization**: Operacje na LazyFrame (lowercase, strip)
3. **Filtering**: Polars może filtrować lazy

### 7.2 Batched Embeddings

**Problem**: Embedding całego datasetu naraz → OOM dla dużych plików.

**Rozwiązanie**: Batch processing.

**Algorytm**:
```python
batch_size = 10000  # Configurable via --batch-size

for batch_idx in range(0, len(texts), batch_size):
    batch_texts = texts[batch_idx:batch_idx + batch_size]
    batch_embeddings = embedder.embed(batch_texts)
    index.add_vectors(batch_embeddings)
    # Release batch_texts from memory
    del batch_texts
```

**Korzyści**:
- **Memory Safety**: Tylko jeden batch w pamięci naraz
- **Scalability**: Możemy przetwarzać miliony wierszy
- **Configurable**: `--batch-size` dla różnych systemów

**Rekomendacje**:
- **Low-memory (4-8GB)**: `--batch-size 1000`
- **Medium (16GB)**: `--batch-size 10000` (default)
- **High-memory (32GB+)**: `--batch-size 50000`

### 7.3 FAISS Index Management

**Strategia**: Keep index in memory, nie release chunks.

**Dlaczego?**
- FAISS index jest kompaktowy (tylko wektory, nie teksty)
- Potrzebujemy całego indexu do duplicate detection
- Release chunks przed detection → błąd (brak wektorów)

**Memory Usage**:
- FAISS index: ~n * d * 4 bytes (float32)
- Przykład: 1M wektorów × 384 dim × 4 bytes = ~1.5 GB

**Optimization**:
- Używamy `IndexFlatL2` (najprostszy, najszybszy)
- Można użyć `IndexIVFFlat` dla większych datasetów (future)

### 7.4 STDIN Handling

**Problem**: Polars nie może czytać bezpośrednio z `sys.stdin`.

**Rozwiązanie**: Temporary file.

**Algorytm**:
1. Stream stdin do temporary file (chunked, 64KB chunks)
2. Użyj `pl.scan_ndjson(temp_file)` dla lazy loading
3. Cleanup temp file po zakończeniu

**Dlaczego Chunked?**
- Unikamy załadowania całego stdin do RAM
- 64KB chunks są efektywne dla I/O

**Implementacja**:
```python
def read_stdin_as_tempfile() -> str:
    CHUNK_SIZE = 64 * 1024  # 64KB
    
    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp:
        while True:
            chunk = sys.stdin.buffer.read(CHUNK_SIZE)
            if not chunk:
                break
            tmp.write(chunk)
        return tmp.name
```

### 7.5 Memory Profiling

**Narzędzie**: `MemoryProfiler` class

**Backend Options**:
- **psutil** (preferred): Dokładne monitorowanie procesu
- **tracemalloc** (fallback): Built-in Python

**Snapshots**:
- Wykonywane na każdym etapie pipeline
- Tracking: peak memory, average memory, growth

**Użycie**:
```bash
entropyguard --input data.jsonl --output clean.jsonl \
  --profile-memory --memory-report-path report.json
```

**Raport**:
```json
{
  "initial_memory_mb": 125.30,
  "snapshots": [
    {"stage": "after_load", "memory_mb": 145.20},
    {"stage": "after_semantic_dedup", "memory_mb": 892.15}
  ],
  "summary": {
    "peak_memory_mb": 892.15,
    "memory_growth_mb": 766.85
  }
}
```

---

## 8. CLI Interface

### 8.1 Argument Parsing (`cli/main.py`)

**Framework**: `argparse`

**Struktura**:
- Standard flags (`--version`, `--verbose`, `--help`)
- Input/Output (`--input`, `--output`)
- Processing options (`--text-column`, `--min-length`, `--dedup-threshold`)
- Advanced options (`--batch-size`, `--profile-memory`, `--config`)

### 8.2 Signal Handling

**Obsługiwane Signale**:
- `SIGINT` (Ctrl+C): Graceful exit z kodem 130
- `SIGTERM` (Docker/K8s): Graceful exit

**Implementacja**:
```python
def signal_handler(sig, frame):
    print("\n⚠️  Process interrupted by user. Exiting...", file=sys.stderr)
    cleanup_temp_files()
    sys.exit(130)
```

**Dlaczego Graceful?**
- Cleanup temporary files
- User-friendly message
- Standard exit code (130 = SIGINT)

### 8.3 Error Handling

**Structured Errors**:
- `ValidationError` (code=2): Input validation issues
- `ResourceError` (code=3): OOM, disk space, IO
- `ProcessingError` (code=1): Embedding, FAISS failures

**Error Messages**:
- User-friendly: "❌ Error: ..." zamiast traceback
- Hints: Opcjonalne wskazówki jak naprawić
- Verbose mode: `--verbose` pokazuje pełny traceback

**JSON Output**:
- `--json` flag: Machine-readable error output
- Format: `{"success": false, "error": "...", "error_code": 2}`

### 8.4 Progress Bars

**Framework**: `tqdm`

**Etapy z Progress Bars**:
- Stage 1: Exact deduplication (rows)
- Stage 2: Semantic deduplication (batches)

**Redirect**:
- Wszystkie progress bars na `stderr`
- `stdout` pozostaje czysty dla JSONL output

**Quiet Mode**:
- `--quiet` flag: Wyłącza progress bars
- Przydatne dla non-interactive environments (CI/CD)

### 8.5 Output Modes

**Human-Readable** (default):
- Summary table na `stderr`
- Metrics: rows, duplicates, tokens saved, storage saved

**JSON Output** (`--json`):
- Machine-readable format
- Przydatne dla CI/CD i automatyzacji
- Format: `{"success": true, "stats": {...}, "output_path": "..."}`

**Stdout Mode** (`--output -`):
- Wszystkie logi na `stderr`
- Tylko JSONL data na `stdout`
- Idealne dla Unix pipes

---

## 9. Error Handling

### 9.1 Exception Hierarchy

```
PipelineError (base)
├── ValidationError (code=2)
│   └── Input validation issues
│       - Missing required columns
│       - Empty dataset
│       - Invalid schema
├── ResourceError (code=3)
│   └── Resource issues
│       - Out of Memory (OOM)
│       - Disk space
│       - IO errors
└── ProcessingError (code=1)
    └── Processing failures
        - Embedding generation errors
        - FAISS index errors
        - Unexpected exceptions
```

### 9.2 Error Codes

| Code | Error Type | Description | When Raised |
|------|------------|-------------|-------------|
| 0 | Success | Pipeline completed | Normal completion |
| 1 | Processing Error | Embedding/FAISS failures | Stage 2 errors |
| 2 | Validation Error | Input validation issues | Schema, empty data |
| 3 | Resource Error | OOM, disk, IO | Memory, file system |
| 130 | SIGINT | User interrupt | Ctrl+C |

### 9.3 Error Messages

**Format**:
```
❌ [Error Type]: [Message]
   Hint: [Optional hint]
```

**Przykłady**:
```
❌ Validation Error: Missing required columns: 'text'
   Hint: Available columns: 'id', 'content', 'metadata'

❌ Resource Error: Out of memory during embedding generation
   Hint: Try reducing --batch-size or use a smaller dataset
```

### 9.4 JSON Error Output

**Format**:
```json
{
  "success": false,
  "error": "Missing required columns: 'text'",
  "error_code": 2,
  "error_category": "validation",
  "hint": "Available columns: 'id', 'content'"
}
```

**Użycie**:
- CI/CD pipelines
- Automation scripts
- Error monitoring systems

---

## 10. Configuration Management

### 10.1 Config File Support

**Formaty**:
- JSON (`.entropyguardrc.json`)
- YAML (`.entropyguardrc.yaml` / `.entropyguardrc.yml`)
- TOML (`.entropyguardrc.toml`)

**Auto-Detection**:
- Current directory (`.entropyguardrc.*`)
- Home directory (`~/.entropyguardrc.*`)

**Explicit Path**:
- `--config /path/to/config.json`

### 10.2 Config File Format

**Example `.entropyguardrc.json`**:
```json
{
  "text_column": "text",
  "min_length": 50,
  "dedup_threshold": 0.95,
  "model_name": "all-MiniLM-L6-v2",
  "batch_size": 10000,
  "chunk_size": 512,
  "chunk_overlap": 50,
  "show_progress": true
}
```

### 10.3 Priority Order

1. **CLI Arguments** (highest priority)
2. **Config File**
3. **Defaults**

**Przykład**:
```bash
# Config file: dedup_threshold=0.95
# CLI: --dedup-threshold 0.85
# Result: 0.85 (CLI overrides config)
```

### 10.4 Config Merging

**Algorytm**:
1. Load config file (if exists)
2. Parse CLI arguments
3. Merge: CLI args override config file values
4. Apply defaults for missing values

**Implementation**: `core/config_loader.py`

---

## 11. Performance i Benchmarking

### 11.1 Performance Metrics

**Measured**:
- **Rows/second**: Processing speed
- **Peak Memory**: Maximum memory usage
- **Memory per 1M rows**: Memory efficiency
- **Total Time**: End-to-end processing time

### 11.2 Benchmark Tool

**Location**: `scripts/benchmark.py`

**Usage**:
```bash
# Single size
python scripts/benchmark.py --size 10K

# Multiple sizes
python scripts/benchmark.py --sizes 1K 10K 100K

# Save results
python scripts/benchmark.py --size 10K --output results.csv
```

**Output Formats**:
- CSV (default)
- JSON (`--format json`)

### 11.3 Typical Performance

**Stage 1 (Exact Deduplication)**:
- ~5000-6000 rows/second
- Memory: O(n) gdzie n = unikalne hashe

**Stage 2 (Semantic Deduplication)**:
- ~500-1000 rows/second (zależy od modelu)
- Memory: O(n * d) gdzie n = wektory, d = dimension (384)

**Overall**:
- 1K rows: ~2-3 seconds
- 10K rows: ~15-20 seconds
- 100K rows: ~2-3 minutes

### 11.4 Memory Efficiency

**Per 1M rows**:
- Small datasets (<10K): ~650 MB per 1M rows
- Medium datasets (10K-100K): ~560 MB per 1M rows
- Large datasets (>100K): ~500 MB per 1M rows

**Optimization Tips**:
- Reduce `--batch-size` for low-memory systems
- Use `--dry-run` for testing (skips expensive operations)
- Enable `--profile-memory` to identify bottlenecks

---

## 12. Testing Strategy

### 12.1 Test Coverage

**Current**: ~74% overall coverage

**Module Coverage**:
- `core/types.py`: 100%
- `core/errors.py`: 62%
- `core/memory_profiler.py`: 77%
- `ingestion/loader.py`: 90%
- `cli/main.py`: 51%

### 12.2 Test Types

**Unit Tests**:
- Individual functions
- Edge cases
- Error handling

**Integration Tests**:
- Full pipeline execution
- End-to-end workflows
- CLI integration

**Performance Tests**:
- Benchmark script
- Memory profiling
- Scalability tests

### 12.3 Test Files

```
tests/
├── test_core_errors.py          # Exception hierarchy
├── test_core_types.py           # Type definitions
├── test_core_pipeline_v1_20.py # Pipeline integration
├── test_core_sanitization_lazy.py # Lazy sanitization
├── test_cli_main.py             # CLI functions
├── test_cli_integration.py      # CLI end-to-end
├── test_ingestion_loader.py     # Data loading
├── test_memory_profiler.py      # Memory profiling
└── ...
```

### 12.4 Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src/entropyguard --cov-report=html

# Specific test file
pytest tests/test_core_pipeline_v1_20.py -v
```

---

## 13. Deployment i Distribution

### 13.1 Installation Methods

**Developer Workflow**:
```bash
git clone https://github.com/DamianSiuta/entropyguard.git
cd entropyguard
python -m poetry install
```

**End User (pip + Git)**:
```bash
pip install "git+https://github.com/DamianSiuta/entropyguard.git"
```

**Docker**:
```bash
docker build -t entropyguard .
docker run -v $(pwd)/data:/data entropyguard \
  --input /data/file.jsonl --output /data/clean.jsonl
```

### 13.2 Dependencies

**Core Dependencies**:
- `polars ^0.20.0`: DataFrame library
- `sentence-transformers ^2.0.0`: Embeddings
- `faiss-cpu ^1.7.4`: Vector search
- `xxhash ^3.4.0`: Fast hashing
- `tqdm ^4.66.0`: Progress bars

**Optional Dependencies**:
- `psutil`: Better memory profiling
- `PyYAML`: YAML config support
- `tomli`: TOML config support (Python <3.11)

### 13.3 Python Version Support

**Supported**: Python 3.10, 3.11, 3.12

**Not Supported**: Python 3.13 (missing wheels for `numpy < 2.0`, `faiss-cpu`)

### 13.4 Docker Image

**Base**: `python:3.10-slim`

**Size**: ~1.5 GB (includes PyTorch, sentence-transformers, FAISS)

**Optimization**:
- Multi-stage build (future)
- Layer caching
- Minimal dependencies

---

## 14. Roadmap i Wersjonowanie

### 14.1 Version History

**v1.11** (Proof of Concept):
- Basic hybrid deduplication
- Unix pipes support
- CLI interface

**v1.20** (Production-Grade):
- Structured error handling
- Memory profiling
- JSON output
- Config file support
- Progress bars
- Batched embeddings

**v1.21** (Current Development):
- Performance benchmarks
- Memory profiling tools
- Documentation updates
- Test coverage improvements

### 14.2 Future Plans

**v1.22+**:
- Streaming FAISS (dla 100GB+ datasets)
- GPU support (optional)
- More embedding models
- Performance optimizations

**Enterprise Features** (Separate):
- Web Dashboard
- RESTful API
- Real-time Monitoring
- Alert System
- SSO Integration

### 14.3 Open Core Strategy

**Community Edition** (Open Source):
- CLI tool
- Core pipeline
- All data processing features
- MIT License

**Enterprise Edition** (Commercial):
- Everything in Community
- Web Dashboard
- API
- Monitoring & Alerts
- SSO
- Commercial License

---

## 15. Podsumowanie

### 15.1 Kluczowe Cechy

1. **Hybrid Deduplication**: Dwuetapowa strategia (hash + AI)
2. **Lazy Evaluation**: Polars LazyFrame dla memory efficiency
3. **Batched Processing**: Scalable embedding generation
4. **Structured Errors**: Production-grade error handling
5. **Memory Profiling**: Debugging OOM issues
6. **Config Files**: Convenience dla teams
7. **Unix Pipes**: Integration z existing workflows
8. **Type Safety**: Full type hints, TypedDict, dataclasses

### 15.2 Design Decisions

**Dlaczego Polars?**
- Lazy evaluation
- High performance
- Memory efficiency
- Modern API

**Dlaczego FAISS?**
- Fast vector search
- Scalable
- Industry standard

**Dlaczego sentence-transformers?**
- State-of-the-art models
- Easy integration
- Model hub access

**Dlaczego Hybrid Deduplication?**
- Performance: Stage 1 usuwa 50-80% szybko
- Accuracy: Stage 2 znajduje semantyczne duplikaty
- Cost: Mniej embeddings = mniej kosztów

### 15.3 Use Cases

1. **LLM Training Data Preparation**: Clean datasets przed treningiem
2. **RAG Pipeline**: Chunking + deduplication dla retrieval
3. **Data Quality**: Validation i sanitization
4. **Compliance**: Audit logs dla GDPR/CCPA
5. **Cost Optimization**: Redukcja duplikatów = mniej API calls

---

**Koniec Dokumentacji**

*Ostatnia aktualizacja: v1.20.0*


