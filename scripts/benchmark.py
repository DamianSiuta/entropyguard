"""
Performance benchmarking script for EntropyGuard.

Measures:
- Processing speed (rows/second)
- Memory usage (peak, average)
- Scalability (1K, 10K, 100K, 1M rows)

Usage:
    python scripts/benchmark.py --size 10K --output benchmark_results.csv
    python scripts/benchmark.py --sizes 1K 10K 100K --format json
"""

import argparse
import json
import sys
import time
import tempfile
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict
import csv

try:
    import tracemalloc
    HAS_TRACEMALLOC = True
except ImportError:
    HAS_TRACEMALLOC = False

try:
    import psutil
    import os
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

import polars as pl

# Add parent directory to path to import entropyguard
sys.path.insert(0, str(Path(__file__).parent.parent))

from entropyguard.core import Pipeline, PipelineConfig


@dataclass
class BenchmarkResult:
    """Single benchmark result."""
    size: str  # e.g., "1K", "10K"
    rows: int
    total_time_seconds: float
    rows_per_second: float
    peak_memory_mb: Optional[float] = None
    average_memory_mb: Optional[float] = None
    exact_dedup_time: Optional[float] = None
    semantic_dedup_time: Optional[float] = None
    embedding_time: Optional[float] = None
    validation_time: Optional[float] = None
    exact_duplicates_removed: int = 0
    semantic_duplicates_removed: int = 0
    final_rows: int = 0
    memory_per_million_rows_mb: Optional[float] = None


def generate_test_data(num_rows: int, duplicate_rate: float = 0.1) -> pl.DataFrame:
    """
    Generate test data for benchmarking.
    
    Args:
        num_rows: Number of rows to generate
        duplicate_rate: Percentage of rows that should be duplicates (0.0-1.0)
    
    Returns:
        DataFrame with test data
    """
    # Generate base texts
    base_texts = [
        "This is a sample text for benchmarking EntropyGuard performance.",
        "Another example text to test deduplication algorithms.",
        "Machine learning models require clean training data.",
        "Data quality is crucial for successful ML projects.",
        "EntropyGuard helps remove duplicate and low-quality data.",
        "Benchmarking helps identify performance bottlenecks.",
        "Polars provides excellent performance for data processing.",
        "Python is great for data science and ML workflows.",
        "Testing is essential for production-ready software.",
        "Open source tools empower developers worldwide.",
    ]
    
    # Generate texts with duplicates
    texts = []
    num_duplicates = int(num_rows * duplicate_rate)
    num_unique = num_rows - num_duplicates
    
    # Add unique texts
    for i in range(num_unique):
        base_idx = i % len(base_texts)
        texts.append(f"{base_texts[base_idx]} Variation {i}")
    
    # Add exact duplicates
    for i in range(num_duplicates):
        # Repeat some existing texts
        texts.append(texts[i % num_unique])
    
    # Shuffle to mix duplicates with unique texts
    import random
    random.seed(42)  # For reproducibility
    random.shuffle(texts)
    
    return pl.DataFrame({
        "text": texts[:num_rows],
        "id": list(range(num_rows)),
    })


def parse_size(size_str: str) -> int:
    """
    Parse size string like "1K", "10K", "100K", "1M" to integer.
    
    Args:
        size_str: Size string (e.g., "1K", "10K", "1M")
    
    Returns:
        Number of rows
    """
    size_str = size_str.upper().strip()
    
    if size_str.endswith("K"):
        multiplier = 1000
        base = size_str[:-1]
    elif size_str.endswith("M"):
        multiplier = 1000000
        base = size_str[:-1]
    else:
        # Try to parse as integer
        try:
            return int(size_str)
        except ValueError:
            raise ValueError(f"Invalid size format: {size_str}. Use format like '1K', '10K', '1M'")
    
    try:
        return int(base) * multiplier
    except ValueError:
        raise ValueError(f"Invalid size format: {size_str}. Could not parse base number")


def measure_memory_usage(func, *args, **kwargs):
    """
    Measure memory usage during function execution.
    
    Returns:
        Tuple of (result, peak_memory_mb, average_memory_mb)
    """
    peak_mb = None
    avg_mb = None
    
    if HAS_PSUTIL:
        process = psutil.Process(os.getpid())
        
        # Start monitoring
        memory_samples = []
        
        def monitor_memory():
            """Sample memory usage periodically."""
            samples = []
            start_time = time.time()
            while time.time() - start_time < 300:  # Max 5 minutes
                try:
                    mem_info = process.memory_info()
                    samples.append(mem_info.rss / (1024 * 1024))  # MB
                    time.sleep(0.1)  # Sample every 100ms
                except Exception:
                    break
            return samples
        
        import threading
        monitor_thread = threading.Thread(target=lambda: memory_samples.extend(monitor_memory()), daemon=True)
        monitor_thread.start()
        
        # Execute function
        result = func(*args, **kwargs)
        
        # Wait a bit for final samples
        time.sleep(0.2)
        
        if memory_samples:
            peak_mb = max(memory_samples)
            avg_mb = sum(memory_samples) / len(memory_samples)
    
    elif HAS_TRACEMALLOC:
        tracemalloc.start()
        result = func(*args, **kwargs)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Convert bytes to MB
        peak_mb = peak / (1024 * 1024)
        avg_mb = current / (1024 * 1024)  # Approximate average
    
    else:
        # No memory monitoring available
        result = func(*args, **kwargs)
    
    return result, peak_mb, avg_mb


def run_benchmark(num_rows: int, batch_size: int = 10000, dry_run: bool = False) -> BenchmarkResult:
    """
    Run a single benchmark with specified number of rows.
    
    Args:
        num_rows: Number of rows to process
        batch_size: Batch size for embeddings
        dry_run: If True, skip expensive operations
    
    Returns:
        BenchmarkResult with performance metrics
    """
    print(f"\n🚀 Benchmarking with {num_rows:,} rows...", file=sys.stderr)
    
    # Generate test data
    print("  📝 Generating test data...", file=sys.stderr)
    df = generate_test_data(num_rows, duplicate_rate=0.1)
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ndjson', delete=False) as f:
        input_path = f.name
        df.write_ndjson(input_path)
    
    output_path = tempfile.mktemp(suffix='.ndjson')
    
    try:
        # Create config
        config = PipelineConfig(
            input_path=input_path,
            output_path=output_path,
            text_column="text",
            min_length=10,
            dedup_threshold=0.95,
            batch_size=batch_size,
            show_progress=False,  # Disable progress bars for benchmarking
            dry_run=dry_run,
        )
        
        # Measure execution time
        print("  ⏱️  Running pipeline...", file=sys.stderr)
        start_time = time.time()
        
        # Run with memory monitoring
        def run_pipeline():
            pipeline = Pipeline(model_name=config.model_name)
            return pipeline.run(config)
        
        result, peak_mb, avg_mb = measure_memory_usage(run_pipeline)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Extract stats
        stats = result["stats"]
        
        # Calculate rows per second
        rows_per_second = num_rows / total_time if total_time > 0 else 0
        
        # Calculate memory per million rows
        memory_per_million_mb = None
        if peak_mb is not None:
            memory_per_million_mb = (peak_mb / num_rows) * 1000000
        
        size_str = f"{num_rows // 1000}K" if num_rows >= 1000 else str(num_rows)
        if num_rows >= 1000000:
            size_str = f"{num_rows // 1000000}M"
        
        benchmark_result = BenchmarkResult(
            size=size_str,
            rows=num_rows,
            total_time_seconds=total_time,
            rows_per_second=rows_per_second,
            peak_memory_mb=peak_mb,
            average_memory_mb=avg_mb,
            exact_duplicates_removed=stats.get("exact_duplicates_removed", 0),
            semantic_duplicates_removed=stats.get("semantic_duplicates_removed", 0),
            final_rows=stats.get("final_rows", 0),
            memory_per_million_rows_mb=memory_per_million_mb,
        )
        
        print(f"  ✅ Completed: {total_time:.2f}s ({rows_per_second:,.0f} rows/sec)", file=sys.stderr)
        if peak_mb:
            print(f"     Memory: {peak_mb:.2f} MB peak", file=sys.stderr)
        
        return benchmark_result
        
    finally:
        # Cleanup
        if Path(input_path).exists():
            Path(input_path).unlink()
        if Path(output_path).exists():
            Path(output_path).unlink()


def save_results_csv(results: list[BenchmarkResult], output_path: str):
    """Save benchmark results to CSV file."""
    with open(output_path, 'w', newline='') as f:
        # Get all field names from dataclass
        fieldnames = [
            'size', 'rows', 'total_time_seconds', 'rows_per_second',
            'peak_memory_mb', 'average_memory_mb', 'memory_per_million_rows_mb',
            'exact_dedup_time', 'semantic_dedup_time', 'embedding_time', 'validation_time',
            'exact_duplicates_removed', 'semantic_duplicates_removed', 'final_rows'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            row_dict = asdict(result)
            # Filter out None values for cleaner CSV
            row_dict = {k: v for k, v in row_dict.items() if k in fieldnames}
            writer.writerow(row_dict)


def save_results_json(results: list[BenchmarkResult], output_path: str):
    """Save benchmark results to JSON file."""
    with open(output_path, 'w') as f:
        json.dump([asdict(r) for r in results], f, indent=2)


def print_results_table(results: list[BenchmarkResult]):
    """Print results as a formatted table."""
    print("\n" + "=" * 80, file=sys.stderr)
    print("📊 BENCHMARK RESULTS", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print(f"{'Size':<8} {'Rows':<12} {'Time (s)':<12} {'Rows/sec':<15} {'Peak Mem (MB)':<15}", file=sys.stderr)
    print("-" * 80, file=sys.stderr)
    
    for result in results:
        peak_mem_str = f"{result.peak_memory_mb:.2f}" if result.peak_memory_mb else "N/A"
        print(
            f"{result.size:<8} {result.rows:<12,} {result.total_time_seconds:<12.2f} "
            f"{result.rows_per_second:<15,.0f} {peak_mem_str:<15}",
            file=sys.stderr
        )
    
    print("=" * 80, file=sys.stderr)
    
    # Print memory per million rows if available
    if any(r.memory_per_million_rows_mb for r in results):
        print("\n💾 Memory Efficiency (per 1M rows):", file=sys.stderr)
        print("-" * 40, file=sys.stderr)
        for result in results:
            if result.memory_per_million_rows_mb:
                print(
                    f"  {result.size}: {result.memory_per_million_rows_mb:.2f} MB per 1M rows",
                    file=sys.stderr
                )


def main():
    """Main entry point for benchmark script."""
    parser = argparse.ArgumentParser(
        description="Performance benchmarking tool for EntropyGuard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Benchmark with 10K rows
  python scripts/benchmark.py --size 10K

  # Benchmark multiple sizes
  python scripts/benchmark.py --sizes 1K 10K 100K

  # Save results to CSV
  python scripts/benchmark.py --size 10K --output results.csv

  # Save results to JSON
  python scripts/benchmark.py --sizes 1K 10K 100K --format json --output results.json

  # Dry run (skip expensive operations)
  python scripts/benchmark.py --size 10K --dry-run
        """,
    )
    
    parser.add_argument(
        "--size",
        type=str,
        help="Single size to benchmark (e.g., '1K', '10K', '100K', '1M')"
    )
    
    parser.add_argument(
        "--sizes",
        nargs="+",
        type=str,
        help="Multiple sizes to benchmark (e.g., '1K 10K 100K')"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="Batch size for embedding processing (default: 10000)"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path for results (CSV or JSON based on --format)"
    )
    
    parser.add_argument(
        "--format",
        type=str,
        choices=["csv", "json"],
        default="csv",
        help="Output format (default: csv)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip expensive operations (faster, less accurate)"
    )
    
    args = parser.parse_args()
    
    # Determine sizes to benchmark
    sizes = []
    if args.size:
        sizes.append(args.size)
    if args.sizes:
        sizes.extend(args.sizes)
    
    if not sizes:
        # Default sizes
        sizes = ["1K", "10K"]
        print("ℹ️  No size specified, using default: 1K, 10K", file=sys.stderr)
    
    # Parse sizes to row counts
    row_counts = []
    for size_str in sizes:
        try:
            row_counts.append(parse_size(size_str))
        except ValueError as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            return 1
    
    # Check memory monitoring availability
    if not HAS_PSUTIL and not HAS_TRACEMALLOC:
        print(
            "⚠️  Warning: No memory monitoring available. "
            "Install 'psutil' for better memory tracking: pip install psutil",
            file=sys.stderr
        )
    
    # Run benchmarks
    results = []
    for num_rows in row_counts:
        try:
            result = run_benchmark(num_rows, batch_size=args.batch_size, dry_run=args.dry_run)
            results.append(result)
        except Exception as e:
            print(f"❌ Error during benchmark: {e}", file=sys.stderr)
            if args.output:
                import traceback
                traceback.print_exc()
            return 1
    
    # Print results
    print_results_table(results)
    
    # Save results if output path specified
    if args.output:
        output_path = Path(args.output)
        if args.format == "csv":
            save_results_csv(results, str(output_path))
        else:
            save_results_json(results, str(output_path))
        print(f"\n💾 Results saved to: {output_path}", file=sys.stderr)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

