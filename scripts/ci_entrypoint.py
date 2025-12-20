#!/usr/bin/env python3
"""
CI Entrypoint for EntropyGuard GitHub Action.

This script wraps the EntropyGuard CLI for use in GitHub Actions.
It reads inputs from environment variables (GitHub Actions convention)
and blocks the CI/CD pipeline if data quality checks fail.
"""

import json
import os
import sys
from pathlib import Path

# GitHub Actions mounts the workspace at /github/workspace
WORKSPACE_ROOT = Path(os.environ.get("GITHUB_WORKSPACE", "/github/workspace"))

# Read inputs from environment variables (GitHub Actions convention)
# GitHub Actions automatically converts inputs to INPUT_* environment variables
INPUT_FILE = os.environ.get("INPUT_INPUT_FILE", "")
OUTPUT_FILE = os.environ.get("INPUT_OUTPUT_FILE", "")
TEXT_COLUMN = os.environ.get("INPUT_TEXT_COLUMN", "")
DEDUP_THRESHOLD = os.environ.get("INPUT_DEDUP_THRESHOLD", "0.85")
MIN_LENGTH = os.environ.get("INPUT_MIN_LENGTH", "50")
FAIL_ON_DUPLICATES = os.environ.get("INPUT_FAIL_ON_DUPLICATES", "true").lower() == "true"
AUDIT_LOG = os.environ.get("INPUT_AUDIT_LOG", "audit.json")
MODEL_NAME = os.environ.get("INPUT_MODEL_NAME", "all-MiniLM-L6-v2")
BATCH_SIZE = os.environ.get("INPUT_BATCH_SIZE", "10000")

# Alternative: Read from command-line args (for Docker compatibility)
# GitHub Actions passes args to Docker container
if len(sys.argv) > 1:
    # Args format: [input_file, output_file, text_column, dedup_threshold, min_length, fail_on_duplicates, audit_log, model_name, batch_size]
    if len(sys.argv) >= 2:
        INPUT_FILE = sys.argv[1] or INPUT_FILE
    if len(sys.argv) >= 3:
        OUTPUT_FILE = sys.argv[2] or OUTPUT_FILE
    if len(sys.argv) >= 4:
        TEXT_COLUMN = sys.argv[3] or TEXT_COLUMN
    if len(sys.argv) >= 5:
        DEDUP_THRESHOLD = sys.argv[4] or DEDUP_THRESHOLD
    if len(sys.argv) >= 6:
        MIN_LENGTH = sys.argv[5] or MIN_LENGTH
    if len(sys.argv) >= 7:
        FAIL_ON_DUPLICATES = sys.argv[6].lower() == "true" if sys.argv[6] else FAIL_ON_DUPLICATES
    if len(sys.argv) >= 8:
        AUDIT_LOG = sys.argv[7] or AUDIT_LOG
    if len(sys.argv) >= 9:
        MODEL_NAME = sys.argv[8] or MODEL_NAME
    if len(sys.argv) >= 10:
        BATCH_SIZE = sys.argv[9] or BATCH_SIZE


def main() -> int:
    """Main entry point for CI entrypoint."""
    print("🛡️  EntropyGuard RAG Firewall - CI/CD Data Quality Check")
    print("=" * 60)
    print()

    # Validate required inputs
    if not INPUT_FILE:
        print("❌ ERROR: input_file is required", file=sys.stderr)
        return 1

    # Resolve paths relative to workspace root
    input_path = WORKSPACE_ROOT / INPUT_FILE
    if not input_path.exists():
        print(f"❌ ERROR: Input file not found: {input_path}", file=sys.stderr)
        return 1

    # Set output path (if not provided, use input path with .clean suffix)
    if OUTPUT_FILE:
        output_path = WORKSPACE_ROOT / OUTPUT_FILE
    else:
        # Default: don't write output in CI (we only care about validation)
        output_path = WORKSPACE_ROOT / ".entropyguard_output.jsonl"

    # Set audit log path
    audit_log_path = WORKSPACE_ROOT / AUDIT_LOG

    print(f"📁 Input file:  {input_path}")
    print(f"📁 Output file: {output_path}")
    print(f"📁 Audit log:   {audit_log_path}")
    print(f"⚙️  Dedup threshold: {DEDUP_THRESHOLD}")
    print(f"⚙️  Min length: {MIN_LENGTH}")
    print(f"⚙️  Fail on duplicates: {FAIL_ON_DUPLICATES}")
    print()

    # Build CLI arguments
    cli_args = [
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--dedup-threshold",
        str(DEDUP_THRESHOLD),
        "--min-length",
        str(MIN_LENGTH),
        "--audit-log",
        str(audit_log_path),
        "--model-name",
        MODEL_NAME,
        "--batch-size",
        str(BATCH_SIZE),
    ]

    if TEXT_COLUMN:
        cli_args.extend(["--text-column", TEXT_COLUMN])

    # Import and run CLI
    try:
        from entropyguard.cli.main import main as cli_main

        # Temporarily replace sys.argv with our CLI args
        original_argv = sys.argv
        sys.argv = ["entropyguard"] + cli_args

        # Run CLI
        exit_code = cli_main()

        # Restore original argv
        sys.argv = original_argv

        if exit_code != 0:
            print()
            print("❌ EntropyGuard pipeline failed!", file=sys.stderr)
            return exit_code

    except Exception as e:
        print(f"❌ ERROR: Failed to run EntropyGuard: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1

    # Check audit log for duplicates/bad rows
    if FAIL_ON_DUPLICATES and audit_log_path.exists():
        print()
        print("🔍 Checking audit log for duplicates and bad rows...")

        try:
            with open(audit_log_path, "r", encoding="utf-8") as f:
                audit_events = json.load(f)

            if not isinstance(audit_events, list):
                print("⚠️  WARNING: Audit log is not a list, skipping validation", file=sys.stderr)
                return 0

            # Count issues by type
            duplicates = [e for e in audit_events if e.get("reason") == "Duplicate"]
            validation_errors = [
                e
                for e in audit_events
                if e.get("reason", "").startswith("Validation:")
            ]

            total_issues = len(duplicates) + len(validation_errors)

            if total_issues > 0:
                print()
                print("🚨" * 30, file=sys.stderr)
                print("🚨 BLOCKING MERGE: Data quality check FAILED!", file=sys.stderr)
                print("🚨" * 30, file=sys.stderr)
                print(file=sys.stderr)
                print(f"   Found {len(duplicates)} duplicate(s)", file=sys.stderr)
                print(f"   Found {len(validation_errors)} validation error(s)", file=sys.stderr)
                print(f"   Total issues: {total_issues}", file=sys.stderr)
                print(file=sys.stderr)
                print("   This merge is BLOCKED to prevent poisoned data from entering production.", file=sys.stderr)
                print(file=sys.stderr)
                print(f"   Audit log: {audit_log_path}", file=sys.stderr)
                print("🚨" * 30, file=sys.stderr)
                return 1
            else:
                print("✅ No duplicates or validation errors found. Data quality check passed!")
                return 0

        except json.JSONDecodeError as e:
            print(f"⚠️  WARNING: Failed to parse audit log: {e}", file=sys.stderr)
            print("   Continuing without blocking merge...", file=sys.stderr)
            return 0
        except Exception as e:
            print(f"⚠️  WARNING: Error reading audit log: {e}", file=sys.stderr)
            print("   Continuing without blocking merge...", file=sys.stderr)
            return 0

    print()
    print("✅ EntropyGuard data quality check completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

