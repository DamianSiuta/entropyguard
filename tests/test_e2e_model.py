"""
End-to-end tests with the real all-MiniLM-L6-v2 model.

Skipped when the model cannot be downloaded; CI sets EG_REQUIRE_MODEL=1 so they
must run there. They check that near-duplicates disappear, that the original text
is written unchanged, and that every removed row is in the audit log.
"""

from __future__ import annotations

import importlib
import io
import json
from pathlib import Path

import pytest

from entropyguard.core import Pipeline, PipelineConfig

# (kept original, near-duplicate variants that must be removed)
NEAR_DUPLICATE_GROUPS = [
    (
        "How do I reset my password on the website?",
        ["How do I reset my password on the website??", "how do I reset my pasword on the website?"],
    ),
    (
        "The quarterly report is due next Friday at noon.",
        ["The quarterly report is due next Friday at noon!", "The quarterly report is due on next Friday at noon."],
    ),
    (
        "Python lists are mutable, while tuples are immutable.",
        ["Python lists are mutable whereas tuples are immutable."],
    ),
]

UNRELATED = [
    "The Eiffel Tower is located in Paris, France.",
    "Photosynthesis converts light energy into chemical energy in plants.",
    "Our team won the regional football championship last weekend.",
    "def add(a, b):\n    return a + b",
]


def build_rows() -> list[dict]:
    rows: list[dict] = []
    for original, _ in NEAR_DUPLICATE_GROUPS:
        rows.append({"text": original, "kind": "original"})
    for text in UNRELATED:
        rows.append({"text": text, "kind": "unrelated"})
    for _, variants in NEAR_DUPLICATE_GROUPS:
        for variant in variants:
            rows.append({"text": variant, "kind": "near_duplicate"})
    rows.append({"text": rows[0]["text"].upper(), "kind": "exact_duplicate"})
    rows.append({"text": None, "kind": "null"})
    for i, row in enumerate(rows):
        row["id"] = i
    return rows


@pytest.fixture
def dataset(tmp_path: Path) -> tuple[list[dict], Path]:
    rows = build_rows()
    path = tmp_path / "input.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return rows, path


def test_near_duplicates_removed_original_text_kept_and_audited(embedder, dataset, tmp_path):
    rows, input_path = dataset
    out, audit_path = tmp_path / "out.jsonl", tmp_path / "audit.json"
    config = PipelineConfig(
        input_path=str(input_path),
        output_path=str(out),
        audit_log_path=str(audit_path),
        text_column="text",
        min_length=10,
        dedup_threshold=0.9,
        show_progress=False,
    )
    result = Pipeline(embedder=embedder).run(config)

    output = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in rows}

    # Exactly the originals and the unrelated rows survive, with unchanged text.
    kept_kinds = sorted(r["kind"] for r in output)
    assert kept_kinds == sorted(["original"] * len(NEAR_DUPLICATE_GROUPS) + ["unrelated"] * len(UNRELATED))
    for r in output:
        assert r == by_id[r["id"]], "output row differs from input row"

    # Every removed row is in the audit log exactly once, with a reason.
    removed_ids = {r["id"] for r in rows} - {r["id"] for r in output}
    assert sorted(e["row_index"] for e in audit) == sorted(removed_ids)
    reasons = {e["row_index"]: e["reason"] for e in audit}
    for rid in removed_ids:
        kind = by_id[rid]["kind"]
        expected = {
            "near_duplicate": "semantic_duplicate",
            "exact_duplicate": "exact_duplicate",
            "null": "Validation: empty_or_null",
        }[kind]
        assert reasons[rid] == expected, (by_id[rid]["text"], reasons[rid])

    # Each semantic duplicate points to the original of its group.
    for event in audit:
        if event["reason"] == "semantic_duplicate":
            variant = by_id[event["row_index"]]["text"]
            group = next(g for g in NEAR_DUPLICATE_GROUPS if variant in g[1])
            assert by_id[event["duplicate_of"]]["text"] == group[0]
            assert event["similarity"] >= 0.9

    stats = result["stats"]
    n_variants = sum(len(v) for _, v in NEAR_DUPLICATE_GROUPS)
    assert stats["semantic_duplicates_removed"] == n_variants
    assert stats["exact_duplicates_removed"] == 1
    assert stats["total_dropped"] == len(audit)


@pytest.mark.parametrize("index_type", ["flat", "hnsw"])
def test_index_types_agree_on_small_data(embedder, dataset, tmp_path, index_type):
    _, input_path = dataset
    out = tmp_path / f"out_{index_type}.jsonl"
    Pipeline(embedder=embedder).run(
        PipelineConfig(
            input_path=str(input_path), output_path=str(out), text_column="text",
            min_length=10, dedup_threshold=0.9, show_progress=False, index_type=index_type,
        )
    )
    ids = [json.loads(line)["id"] for line in out.read_text().splitlines()]
    assert len(ids) == len(NEAR_DUPLICATE_GROUPS) + len(UNRELATED)


def test_unrelated_texts_survive_default_threshold(embedder, tmp_path):
    path = tmp_path / "in.jsonl"
    path.write_text("".join(json.dumps({"text": t}) + "\n" for t in UNRELATED))
    out = tmp_path / "out.jsonl"
    result = Pipeline(embedder=embedder).run(
        PipelineConfig(input_path=str(path), output_path=str(out), text_column="text",
                       min_length=1, show_progress=False)
    )
    assert result["stats"]["final_rows"] == len(UNRELATED)


def test_cli_pipe_with_real_model(embedder, dataset, monkeypatch, capsys):
    """stdin -> stdout through the real CLI and model."""
    cli = importlib.import_module("entropyguard.cli.main")
    _, input_path = dataset
    monkeypatch.setattr("sys.stdin", io.StringIO(input_path.read_text(encoding="utf-8")))
    code = cli.main(["--text-column", "text", "--min-length", "10", "--dedup-threshold", "0.9"])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    output = [json.loads(line) for line in captured.out.splitlines()]
    assert len(output) == len(NEAR_DUPLICATE_GROUPS) + len(UNRELATED)
