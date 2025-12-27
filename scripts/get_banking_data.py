#!/usr/bin/env python3
"""
Prepare Banking77 Demo Data for EntropyGuard Video.

This script downloads Banking77 dataset from HuggingFace and prepares
a large demo dataset for promotional video recording.

Process:
1. Downloads train.csv and test.csv from HuggingFace
2. Extracts text column from both files
3. Combines and duplicates the dataset 5x
4. Shuffles the data
5. Saves as JSONL format
6. Prints command for video recording
"""

import csv
import json
import random
import time
import urllib.error
import urllib.request
from io import StringIO
from pathlib import Path
from typing import List, Optional


def download_csv_with_retry(url: str, max_retries: int = 3, retry_delay: int = 2) -> Optional[str]:
    """
    Download CSV file from URL with retry logic for network resilience.
    
    Args:
        url: URL to download from
        max_retries: Maximum number of retry attempts
        retry_delay: Delay in seconds between retries
        
    Returns:
        CSV content as string, or None if all retries failed
    """
    for attempt in range(1, max_retries + 1):
        try:
            print(f"📥 Downloading from {url} (attempt {attempt}/{max_retries})...")
            
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0 (compatible; EntropyGuard/1.0)')
            
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read().decode('utf-8')
                print(f"✅ Successfully downloaded {len(content):,} bytes")
                return content
                
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"❌ 404 Not Found: {url}")
                if attempt < max_retries:
                    print(f"⏳ Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    return None
            else:
                print(f"❌ HTTP Error {e.code}: {e.reason}")
                if attempt < max_retries:
                    print(f"⏳ Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    return None
                    
        except urllib.error.URLError as e:
            print(f"❌ Network Error: {e.reason}")
            if attempt < max_retries:
                print(f"⏳ Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                return None
                
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            if attempt < max_retries:
                print(f"⏳ Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                return None
    
    return None


def extract_text_from_csv(csv_content: str) -> List[str]:
    """
    Extract text column from CSV content.
    
    Args:
        csv_content: CSV file content as string
        
    Returns:
        List of text strings from the first column
    """
    texts = []
    reader = csv.reader(StringIO(csv_content))
    
    # Skip header if present (check first row)
    rows = list(reader)
    start_idx = 0
    
    if rows:
        # Check if first row looks like a header (contains common header words)
        first_row = rows[0]
        if first_row and any(header_word in first_row[0].lower() for header_word in ['text', 'question', 'query', 'label', 'category']):
            start_idx = 1
            print(f"📋 Detected header row, skipping...")
    
    # Extract text from first column
    for row in rows[start_idx:]:
        if row and len(row) > 0:
            text = row[0].strip()
            if text:  # Only include non-empty texts
                texts.append(text)
    
    return texts


def download_banking77_data() -> List[str]:
    """
    Download Banking77 train and test datasets from GitHub repository.
    
    Source: https://github.com/PolyAI-LDN/task-specific-datasets/tree/master/banking_data
    
    Returns:
        Combined list of text strings from both datasets
    """
    # Primary URLs (GitHub raw)
    train_url = "https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/master/banking_data/train.csv"
    test_url = "https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/master/banking_data/test.csv"
    
    # Fallback URLs (HuggingFace)
    train_fallback = "https://huggingface.co/datasets/PolyAI/banking77/resolve/main/train.csv"
    test_fallback = "https://huggingface.co/datasets/PolyAI/banking77/resolve/main/test.csv"
    
    # Additional fallback (HuggingFace alternative path)
    train_fallback2 = "https://huggingface.co/datasets/PolyAI/banking77/resolve/main/data/train.csv"
    test_fallback2 = "https://huggingface.co/datasets/PolyAI/banking77/resolve/main/data/test.csv"
    
    all_texts = []
    
    # Download train.csv
    print("\n" + "=" * 60)
    print("📊 Downloading Banking77 Training Data")
    print("=" * 60)
    train_content = download_csv_with_retry(train_url)
    
    if train_content is None:
        print(f"⚠️  Primary URL failed, trying HuggingFace fallback...")
        train_content = download_csv_with_retry(train_fallback)
    
    if train_content is None:
        print(f"⚠️  First fallback failed, trying alternative HuggingFace path...")
        train_content = download_csv_with_retry(train_fallback2)
    
    if train_content is None:
        raise RuntimeError("❌ Failed to download train.csv from all URLs")
    
    train_texts = extract_text_from_csv(train_content)
    print(f"✅ Extracted {len(train_texts):,} texts from train.csv")
    all_texts.extend(train_texts)
    
    # Download test.csv
    print("\n" + "=" * 60)
    print("📊 Downloading Banking77 Test Data")
    print("=" * 60)
    test_content = download_csv_with_retry(test_url)
    
    if test_content is None:
        print(f"⚠️  Primary URL failed, trying HuggingFace fallback...")
        test_content = download_csv_with_retry(test_fallback)
    
    if test_content is None:
        print(f"⚠️  First fallback failed, trying alternative HuggingFace path...")
        test_content = download_csv_with_retry(test_fallback2)
    
    if test_content is None:
        raise RuntimeError("❌ Failed to download test.csv from all URLs")
    
    test_texts = extract_text_from_csv(test_content)
    print(f"✅ Extracted {len(test_texts):,} texts from test.csv")
    all_texts.extend(test_texts)
    
    print(f"\n✅ Total texts collected: {len(all_texts):,}")
    return all_texts


def prepare_banking_demo(
    output_file: str = "banking_demo.jsonl",
    duplication_factor: int = 5
) -> None:
    """
    Prepare Banking77 demo data for video recording.
    
    Args:
        output_file: Path to output JSONL file
        duplication_factor: Number of times to duplicate the dataset (default: 5)
    """
    print("\n" + "=" * 60)
    print("🚀 EntropyGuard Banking77 Demo Data Preparation")
    print("=" * 60)
    
    # Step 1: Download data
    original_texts = download_banking77_data()
    
    if not original_texts:
        raise RuntimeError("❌ No data downloaded. Cannot proceed.")
    
    # Step 2: Duplicate dataset
    print("\n" + "=" * 60)
    print(f"📋 Duplicating dataset {duplication_factor}x...")
    print("=" * 60)
    
    duplicated_texts = []
    for i in range(duplication_factor):
        duplicated_texts.extend(original_texts)
        print(f"   Duplication {i+1}/{duplication_factor}: {len(duplicated_texts):,} total texts")
    
    print(f"✅ Total after duplication: {len(duplicated_texts):,} texts")
    
    # Step 3: Shuffle
    print("\n" + "=" * 60)
    print("🎲 Shuffling data...")
    print("=" * 60)
    random.shuffle(duplicated_texts)
    print("✅ Data shuffled")
    
    # Step 4: Save as JSONL
    print("\n" + "=" * 60)
    print(f"💾 Saving to {output_file}...")
    print("=" * 60)
    
    output_path = Path(output_file)
    written = 0
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for text in duplicated_texts:
            json.dump({"text": text}, f, ensure_ascii=False)
            f.write('\n')
            written += 1
            
            # Progress indicator every 1000 rows
            if written % 1000 == 0:
                print(f"   Written {written:,}/{len(duplicated_texts):,} rows...", end='\r')
    
    print(f"   Written {written:,}/{len(duplicated_texts):,} rows...")
    
    # Get file size
    file_size = output_path.stat().st_size
    file_size_mb = file_size / (1024 * 1024)
    
    # Step 5: Print summary and command
    print("\n" + "=" * 60)
    print("✅ DEMO DATA PREPARATION COMPLETE")
    print("=" * 60)
    print(f"📁 Output file: {output_path.absolute()}")
    print(f"📊 Total rows: {len(duplicated_texts):,}")
    print(f"💾 File size: {file_size_mb:.2f} MB")
    print(f"📈 Original dataset size: {len(original_texts):,} rows")
    print(f"🔄 Duplication factor: {duplication_factor}x")
    print("=" * 60)
    print()
    print("🎬 READY FOR VIDEO RECORDING")
    print()
    print("Use this command:")
    print("-" * 60)
    print(f"cat {output_file} | entropyguard --input - --output - --dedup-threshold 0.85 --profile-memory > clean_banking.jsonl")
    print("-" * 60)
    print()
    print("Or alternatively (without pipe):")
    print("-" * 60)
    print(f"entropyguard --input {output_file} --output clean_banking.jsonl --dedup-threshold 0.85 --profile-memory")
    print("-" * 60)
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Prepare Banking77 demo data for EntropyGuard promotional video"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="banking_demo.jsonl",
        help="Output JSONL file path (default: banking_demo.jsonl)"
    )
    parser.add_argument(
        "--duplication-factor",
        type=int,
        default=5,
        help="Number of times to duplicate the dataset (default: 5)"
    )
    
    args = parser.parse_args()
    
    try:
        prepare_banking_demo(
            output_file=args.output,
            duplication_factor=args.duplication_factor
        )
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        exit(1)

