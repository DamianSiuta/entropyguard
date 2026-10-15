"""
Pipeline tests with a deterministic bag-of-words embedder (no model download).

They check the pipeline contract: original text in the output, no internal columns,
opt-in PII redaction, nulls in metadata preserved, every removed row audited once,
and that the semantic stage really runs (regression for v1.22-v1.23).
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from tests.conftest import BagOfWordsEmbedder
from entropyguard.core import Pipeline, PipelineConfig
from entropyguard.core.errors import ProcessingError, ValidationError
from entropyguard.core.pipeline import INTERNAL_COLUMNS


def write_jsonl(path: Path, rows: list[dict]) -> str:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return str(path)


def run(tmp_path: Path, rows: list[dict], embedder=None, **overrides):
    """Run the pipeline on ``rows``; return (result, output rows, audit events)."""
    params = dict(
        input_path=write_jsonl(tmp_path / "in.jsonl", rows),
        output_path=str(tmp_path / "out.jsonl"),
        audit_log_path=str(tmp_path / "audit.json"),
        text_column="text",
        min_length=5,
        dedup_threshold=0.95,
        show_progress=False,
    )
    params.update(overrides)
    config = PipelineConfig(**params)
    result = Pipeline(embedder=embedder or BagOfWordsEmbedder()).run(config)
    out_path = Path(config.output_path)
    output = (
        [json.loads(line) for line in out_path.read_text().splitlines()]
        if out_path.exists() and not config.dry_run
        else []
    )
    audit = json.loads(Path(config.audit_log_path).read_text()) if config.audit_log_path else []
    return result, output, audit


ROWS = [
    {"id": 0, "text": "def Parse(Input):\n    return Input.Strip()", "lang": "py"},
    {"id": 1, "text": "The cat sat on the mat today", "lang": None},
    {"id": 2, "text": "the  CAT sat on the mat today", "lang": "en"},  # exact dup of 1 (case/space)
    {"id": 3, "text": "today the cat sat on the mat", "lang": "en"},  # semantic dup of 1 (word order)
    {"id": 4, "text": "Write to jane.doe@example.com or call 555-123-4567", "lang": None},
    {"id": 5, "text": None, "lang": "en"},  # null text
    {"id": 6, "text": "   ", "lang": "en"},  # blank text
    {"id": 7, "text": "tiny", "lang": "en"},  # below min_length
    {"id": 8, "text": "A completely different sentence about rockets", "lang": None},
]


class TestOutputIsNotModified:
    def test_original_text_is_written(self, tmp_path):
        _, output, _ = run(tmp_path, ROWS)
        texts = [r["text"] for r in output]
        assert "def Parse(Input):\n    return Input.Strip()" in texts
        assert "The cat sat on the mat today" in texts

    def test_output_has_exactly_the_input_columns(self, tmp_path):
        _, output, _ = run(tmp_path, ROWS)
        assert output and all(list(r.keys()) == ["id", "text", "lang"] for r in output)
        for col in INTERNAL_COLUMNS + ("_original_index", "_text_hash", "_hash_rank"):
            assert all(col not in r for r in output)

    def test_output_keeps_input_order(self, tmp_path):
        _, output, _ = run(tmp_path, ROWS)
        assert [r["id"] for r in output] == [0, 1, 4, 8]

    def test_pii_is_kept_by_default(self, tmp_path):
        _, output, _ = run(tmp_path, ROWS)
        assert any("jane.doe@example.com" in r["text"] for r in output)

    def test_pii_redaction_is_opt_in(self, tmp_path):
        _, output, _ = run(tmp_path, ROWS, redact_pii=True)
        text = next(r["text"] for r in output if r["id"] == 4)
        assert "jane.doe@example.com" not in text and "555-123-4567" not in text
        assert "[EMAIL_REMOVED]" in text and "[PHONE_REMOVED]" in text

    def test_nulls_in_other_columns_are_kept(self, tmp_path):
        _, output, _ = run(tmp_path, ROWS)
        assert {r["id"] for r in output if r["lang"] is None} == {1, 4, 8}


class TestAuditAndStats:
    def test_every_removed_row_is_audited_exactly_once(self, tmp_path):
        result, output, audit = run(tmp_path, ROWS)
        kept = {r["id"] for r in output}
        removed = [e["row_index"] for e in audit]
        assert len(removed) == len(set(removed))
        assert kept | set(removed) == {r["id"] for r in ROWS}
        assert not kept & set(removed)
        stats = result["stats"]
        assert stats["total_dropped"] == len(audit) == stats["audit_events"]
        assert stats["original_rows"] == len(ROWS)
        assert stats["final_rows"] == len(output)

    def test_reasons(self, tmp_path):
        _, _, audit = run(tmp_path, ROWS)
        reasons = {e["row_index"]: e["reason"] for e in audit}
        assert reasons == {
            2: "exact_duplicate",
            3: "semantic_duplicate",
            5: "Validation: empty_or_null",
            6: "Validation: empty_after_strip",
            7: "Validation: below_min_length",
        }

    def test_duplicates_point_to_kept_rows(self, tmp_path):
        _, output, audit = run(tmp_path, ROWS)
        kept = {r["id"] for r in output}
        dups = [e for e in audit if "duplicate_of" in e]
        assert {e["row_index"]: e["duplicate_of"] for e in dups} == {2: 1, 3: 1}
        assert all(e["duplicate_of"] in kept for e in dups)
        semantic = next(e for e in audit if e["reason"] == "semantic_duplicate")
        assert semantic["similarity"] >= 0.95

    def test_stage_counters(self, tmp_path):
        result, _, _ = run(tmp_path, ROWS)
        s = result["stats"]
        assert s["validation_dropped"] == 3
        assert s["exact_duplicates_removed"] == 1
        assert s["semantic_duplicates_removed"] == 1
        assert s["duplicates_removed"] == 2
        assert s["index_type"] == "flat"


class TestSemanticStageRuns:
    """Regression: in v1.22.0-v1.23.0 the semantic stage was never executed."""

    def test_embedder_is_called_and_paraphrase_removed(self, tmp_path):
        embedder = BagOfWordsEmbedder()
        result, output, _ = run(tmp_path, ROWS, embedder=embedder)
        assert embedder.calls >= 1
        assert result["stats"]["semantic_duplicates_removed"] == 1
        assert 3 not in {r["id"] for r in output}

    def test_batches_span_multiple_embed_calls(self, tmp_path):
        rows = [{"text": f"alpha beta gamma number {i}"} for i in range(30)]
        rows += [{"text": f"number {i} gamma beta alpha"} for i in range(30)]
        embedder = BagOfWordsEmbedder()
        result, output, _ = run(tmp_path, rows, embedder=embedder, batch_size=7)
        assert embedder.calls == -(-60 // 7)
        assert result["stats"]["semantic_duplicates_removed"] == 30
        assert len(output) == 30

    def test_hnsw_index(self, tmp_path):
        result, output, _ = run(tmp_path, ROWS, index_type="hnsw")
        assert result["stats"]["index_type"] == "hnsw"
        assert [r["id"] for r in output] == [0, 1, 4, 8]

    def test_threshold_one_keeps_paraphrases_with_different_vectors(self, tmp_path):
        rows = [{"text": "red green blue"}, {"text": "red green blue yellow"}]
        _, output, _ = run(tmp_path, rows, dedup_threshold=1.0)
        assert len(output) == 2


class TestModes:
    def test_dry_run_writes_audit_but_not_output(self, tmp_path):
        result, _, audit = run(tmp_path, ROWS, dry_run=True)
        assert not (tmp_path / "out.jsonl").exists()
        assert result["stats"]["dry_run"] is True
        assert result["stats"]["would_write_rows"] == 4
        assert len(audit) == 5

    def test_all_rows_invalid_gives_empty_output(self, tmp_path):
        result, output, audit = run(tmp_path, [{"text": ""}, {"text": "x"}])
        assert result["stats"]["final_rows"] == 0
        assert output == [] and len(audit) == 2

    def test_auto_detect_text_column(self, tmp_path):
        result, output, _ = run(tmp_path, [{"n": 1, "body": "hello there world"}], text_column="")
        assert result["success"] and output == [{"n": 1, "body": "hello there world"}]

    def test_chunking_audits_chunks(self, tmp_path):
        text = "first part words here. " * 3 + "\n\n" + "first part words here. " * 3
        result, output, audit = run(tmp_path, [{"text": text}], chunk_size=80, chunk_overlap=0)
        assert result["stats"]["after_chunking_rows"] > 1
        assert all("chunk_index" in e for e in audit)
        assert result["stats"]["total_dropped"] == len(audit)


class TestErrors:
    def test_missing_input_file(self, tmp_path):
        config = PipelineConfig(
            input_path=str(tmp_path / "missing.jsonl"),
            output_path=str(tmp_path / "out.jsonl"),
            text_column="text",
        )
        with pytest.raises(ValidationError, match="Cannot load input"):
            Pipeline(embedder=BagOfWordsEmbedder()).run(config)

    def test_missing_required_column(self, tmp_path):
        with pytest.raises(ValidationError) as exc_info:
            run(tmp_path, [{"id": 1}], required_columns=["text", "id"])
        assert exc_info.value.code == 2
        assert "Missing required columns" in exc_info.value.message

    def test_unknown_text_column(self, tmp_path):
        with pytest.raises(ValidationError, match="not found"):
            run(tmp_path, [{"body": "hello world"}], text_column="text")

    @pytest.mark.parametrize("threshold", [-0.1, 1.1])
    def test_threshold_out_of_range(self, tmp_path, threshold):
        with pytest.raises(ValidationError):
            run(tmp_path, ROWS, dedup_threshold=threshold)

    def test_embedder_failure_is_processing_error(self, tmp_path):
        class Broken(BagOfWordsEmbedder):
            def embed(self, texts):
                raise RuntimeError("boom")

        with pytest.raises(ProcessingError, match="boom"):
            run(tmp_path, ROWS, embedder=Broken())


class TestCheckpointResume:
    def test_resume_after_failure_in_semantic_stage(self, tmp_path):
        class FailOnce(BagOfWordsEmbedder):
            def embed(self, texts):
                raise RuntimeError("simulated crash")

        ckpt = str(tmp_path / "ckpt")
        with pytest.raises(ProcessingError):
            run(tmp_path, ROWS, embedder=FailOnce(), checkpoint_dir=ckpt)
        assert (tmp_path / "ckpt" / "after_exact_dedup.parquet").exists()

        result, output, audit = run(tmp_path, ROWS, checkpoint_dir=ckpt)
        assert result["stats"]["resumed_from"] == "after_exact_dedup"
        assert [r["id"] for r in output] == [0, 1, 4, 8]
        assert sorted(e["row_index"] for e in audit) == [2, 3, 5, 6, 7]
        # A completed run removes its checkpoints.
        assert not list((tmp_path / "ckpt").glob("*.parquet"))

    def test_checkpoint_ignored_when_input_changes(self, tmp_path):
        class FailOnce(BagOfWordsEmbedder):
            def embed(self, texts):
                raise RuntimeError("simulated crash")

        ckpt = str(tmp_path / "ckpt")
        with pytest.raises(ProcessingError):
            run(tmp_path, ROWS, embedder=FailOnce(), checkpoint_dir=ckpt)
        result, output, _ = run(tmp_path, ROWS[:2], checkpoint_dir=ckpt)
        assert result["stats"]["resumed_from"] is None
        assert [r["id"] for r in output] == [0, 1]


def test_csv_and_parquet_inputs(tmp_path):
    df = pl.DataFrame({"text": ["one two three four", "four three two one", "other words entirely"]})
    for name, writer in (("in.csv", df.write_csv), ("in.parquet", df.write_parquet)):
        path = tmp_path / name
        writer(path)
        config = PipelineConfig(
            input_path=str(path), output_path=str(tmp_path / f"{name}.out.jsonl"),
            text_column="text", min_length=1, show_progress=False,
        )
        result = Pipeline(embedder=BagOfWordsEmbedder()).run(config)
        assert result["stats"]["final_rows"] == 2
