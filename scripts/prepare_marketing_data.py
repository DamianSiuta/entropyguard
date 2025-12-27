#!/usr/bin/env python3
"""
Prepare Marketing Demo Data for EntropyGuard.

This script creates a realistic dataset with exact and semantic duplicates
for marketing screenshots and demonstrations.

Process:
1. Downloads real text data from AG News dataset
2. Extracts 2000 unique rows (Golden Data)
3. Injects 1000 exact duplicates
4. Injects 500 semantic/near-match duplicates
5. Shuffles everything
6. Saves as JSONL format
"""

import csv
import json
import random
import urllib.request
from pathlib import Path
from typing import List, Dict


def download_ag_news_data(url: str) -> List[str]:
    """
    Download AG News dataset and extract text column.
    
    Args:
        url: URL to the CSV file
        
    Returns:
        List of text strings from the dataset
    """
    print(f"📥 Downloading data from {url}...")
    
    try:
        with urllib.request.urlopen(url) as response:
            content = response.read().decode('utf-8')
            
        # Parse CSV
        reader = csv.reader(content.splitlines())
        texts = []
        
        # AG News format: class, title, description
        # We'll use description (column 2) as our text
        for row in reader:
            if len(row) >= 3:
                # Combine title and description for richer text
                title = row[1].strip() if len(row) > 1 else ""
                description = row[2].strip() if len(row) > 2 else ""
                
                # Combine title and description
                combined_text = f"{title}. {description}".strip()
                
                # Only include non-empty texts with reasonable length
                if combined_text and len(combined_text) > 20:
                    texts.append(combined_text)
        
        print(f"✅ Downloaded {len(texts)} text entries")
        return texts
        
    except Exception as e:
        print(f"❌ Error downloading data: {e}")
        raise


def create_semantic_variant(text: str) -> str:
    """
    Create a semantic variant of text by making minor changes.
    
    Changes:
    - Case variations (uppercase/lowercase)
    - Remove trailing punctuation
    - Minor whitespace changes
    
    Args:
        text: Original text
        
    Returns:
        Modified text that is semantically similar
    """
    variant = text
    
    # Randomly change case of first letter
    if random.random() < 0.3:
        if variant and variant[0].islower():
            variant = variant[0].upper() + variant[1:]
        elif variant and variant[0].isupper():
            variant = variant[0].lower() + variant[1:]
    
    # Remove trailing punctuation
    if random.random() < 0.4:
        variant = variant.rstrip('.!?')
    
    # Add or remove trailing period
    if random.random() < 0.3:
        if not variant.endswith('.'):
            variant = variant + '.'
        elif variant.endswith('.'):
            variant = variant[:-1]
    
    # Minor whitespace normalization
    variant = ' '.join(variant.split())
    
    return variant


def prepare_marketing_data(
    output_file: str = "marketing_demo.jsonl",
    golden_rows: int = 2000,
    exact_duplicates: int = 1000,
    semantic_duplicates: int = 500
) -> None:
    """
    Prepare marketing demo data with realistic duplicates.
    
    Args:
        output_file: Path to output JSONL file
        golden_rows: Number of unique "golden" data rows
        exact_duplicates: Number of exact duplicates to inject
        semantic_duplicates: Number of semantic duplicates to inject
    """
    url = "https://raw.githubusercontent.com/mhjabreel/CharCnn_Keras/master/data/ag_news_csv/test.csv"
    
    # Step 1: Download and extract text
    all_texts = download_ag_news_data(url)
    
    if len(all_texts) < golden_rows:
        print(f"⚠️  Warning: Dataset has only {len(all_texts)} rows, requested {golden_rows}")
        golden_rows = len(all_texts)
    
    # Step 2: Get unique texts (Golden Data)
    print(f"🔍 Extracting {golden_rows} unique rows...")
    unique_texts = list(dict.fromkeys(all_texts))  # Preserve order, remove duplicates
    golden_data = unique_texts[:golden_rows]
    
    print(f"✅ Extracted {len(golden_data)} unique golden rows")
    
    # Step 3: Inject exact duplicates
    print(f"📋 Injecting {exact_duplicates} exact duplicates...")
    exact_dups = []
    for _ in range(exact_duplicates):
        if golden_data:
            exact_dups.append(random.choice(golden_data))
    
    # Step 4: Inject semantic duplicates
    print(f"🔄 Injecting {semantic_duplicates} semantic duplicates...")
    semantic_dups = []
    for _ in range(semantic_duplicates):
        if golden_data:
            original = random.choice(golden_data)
            variant = create_semantic_variant(original)
            semantic_dups.append(variant)
    
    # Step 5: Combine all data
    print("🔀 Combining all data...")
    all_data = golden_data + exact_dups + semantic_dups
    
    # Step 6: Shuffle
    print("🎲 Shuffling data...")
    random.shuffle(all_data)
    
    # Step 7: Save as JSONL
    print(f"💾 Saving to {output_file}...")
    output_path = Path(output_file)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for text in all_data:
            json.dump({"text": text}, f, ensure_ascii=False)
            f.write('\n')
    
    total_rows = len(all_data)
    print()
    print("=" * 60)
    print(f"✅ Created {output_file} with {total_rows:,} rows")
    print(f"   - Golden data: {len(golden_data):,} rows")
    print(f"   - Exact duplicates: {len(exact_dups):,} rows")
    print(f"   - Semantic duplicates: {len(semantic_dups):,} rows")
    print(f"   - Total: {total_rows:,} rows")
    print("=" * 60)
    print("Ready for EntropyGuard.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Prepare marketing demo data for EntropyGuard"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="marketing_demo.jsonl",
        help="Output JSONL file path (default: marketing_demo.jsonl)"
    )
    parser.add_argument(
        "--golden-rows",
        type=int,
        default=2000,
        help="Number of unique golden data rows (default: 2000)"
    )
    parser.add_argument(
        "--exact-duplicates",
        type=int,
        default=1000,
        help="Number of exact duplicates to inject (default: 1000)"
    )
    parser.add_argument(
        "--semantic-duplicates",
        type=int,
        default=500,
        help="Number of semantic duplicates to inject (default: 500)"
    )
    
    args = parser.parse_args()
    
    prepare_marketing_data(
        output_file=args.output,
        golden_rows=args.golden_rows,
        exact_duplicates=args.exact_duplicates,
        semantic_duplicates=args.semantic_duplicates
    )




