import json
import logging
from pathlib import Path
from datasets import load_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    output_file = Path("banking_raw.jsonl")
    logger.info("⏳ Fetching 'banking77' dataset from Hugging Face...")
    
    try:
        dataset = load_dataset("banking77", split="train")
    except Exception as e:
        logger.error(f"Error fetching dataset: {e}")
        return

    logger.info(f"✅ Fetched {len(dataset)} rows. Converting to JSONL...")

    with open(output_file, "w", encoding="utf-8") as f:
        for i, row in enumerate(dataset):
            entry = {
                "text": row["text"],
                "category": row["label"], 
                "id": i
            }
            f.write(json.dumps(entry) + "\n")

    logger.info(f"💾 Saved to: {output_file.absolute()}")

if __name__ == "__main__":
    main()

