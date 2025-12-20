#!/usr/bin/env python3
"""Create test data file for telemetry testing."""

import json

data = [
    {"text": "Siemens energy solution", "id": 1},
    {"text": "Siemens energy solution", "id": 2},
    {"text": "Unique data point", "id": 3},
]

with open("demo_dirty.jsonl", "w", encoding="utf-8") as f:
    for item in data:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print("Created demo_dirty.jsonl")

