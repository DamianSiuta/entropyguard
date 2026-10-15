"""
CLI tests. The embedding model is replaced by the deterministic bag-of-words
embedder, so these tests need no network; see test_e2e_model.py for the real model.
"""

from __future__ import annotations

import importlib
import io
import json
from pathlib import Path

import pytest

from entropyguard.core.pipeline import Pipeline
from tests.conftest import BagOfWordsEmbedder

# entropyguard.cli re-exports the main() function, so import the module explicitly.
cli = importlib.import_module("entropyguard.cli.main")

ROWS = [
    {"id": 1, "text": "How Do I Learn Python Quickly?", "src": "a"},
    {"id": 2, "text": "how do i learn python quickly?", "src": None},
    {"id": 3, "text": "Quickly, how do I learn Python?", "src": "b"},  # same words: semantic dup
    {"id": 4, "text": "What is the capital city of France?", "src": "c"},
]


@pytest.fixture(autouse=True)
def fake_model(monkeypatch):
    """Make the CLI build pipelines with the bag-of-words embedder."""
    original = cli.Pipeline

    def factory(model_name: str = "all-MiniLM-L6-v2"):
        return original(model_name=model_name, embedder=BagOfWordsEmbedder())

    monkeypatch.setattr(cli, "Pipeline", factory)


@pytest.fixture
def data_file(tmp_path: Path) -> Path:
    path = tmp_path / "in.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in ROWS))
    return path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_basic_run(tmp_path, data_file, capsys):
    out = tmp_path / "out.jsonl"
    code = cli.main(["--input", str(data_file), "--output", str(out),
                     "--text-column", "text", "--min-length", "5"])
    assert code == 0
    rows = read_jsonl(out)
    assert [r["id"] for r in rows] == [1, 4]  # 2: exact dup, 3: semantic dup of 1
    assert rows[0]["text"] == "How Do I Learn Python Quickly?"
    assert "Summary:" in capsys.readouterr().err


def test_stdin_to_stdout_pipe(monkeypatch, data_file, capsys):
    """The README example: cat data.jsonl | entropyguard --text-column text > clean.jsonl"""
    monkeypatch.setattr("sys.stdin", io.StringIO(data_file.read_text()))
    code = cli.main(["--text-column", "text", "--min-length", "5"])
    captured = capsys.readouterr()
    assert code == 0
    rows = [json.loads(line) for line in captured.out.splitlines()]
    assert [r["id"] for r in rows] == [1, 4]
    # Only data on stdout; everything else on stderr.
    assert "Summary:" in captured.err and "Summary:" not in captured.out


def test_auto_detects_text_column(tmp_path, data_file, capsys):
    out = tmp_path / "out.jsonl"
    assert cli.main(["--input", str(data_file), "--output", str(out), "--min-length", "5"]) == 0
    assert "Auto-detected text column: 'text'" in capsys.readouterr().err


def test_audit_log_and_dry_run(tmp_path, data_file):
    out, audit = tmp_path / "out.jsonl", tmp_path / "audit.json"
    code = cli.main(["--input", str(data_file), "--output", str(out), "--text-column", "text",
                     "--min-length", "5", "--audit-log", str(audit), "--dry-run"])
    assert code == 0
    assert not out.exists()
    events = json.loads(audit.read_text())
    assert [(e["row_index"], e["reason"], e["duplicate_of"]) for e in events] == [
        (1, "exact_duplicate", 0),
        (2, "semantic_duplicate", 0),
    ]


def test_redact_pii_flag(tmp_path):
    src = tmp_path / "in.jsonl"
    src.write_text(json.dumps({"text": "Mail me at someone@example.org about the order"}) + "\n")
    out = tmp_path / "out.jsonl"
    assert cli.main(["--input", str(src), "--output", str(out), "--min-length", "1"]) == 0
    assert "someone@example.org" in read_jsonl(out)[0]["text"]
    assert cli.main(["--input", str(src), "--output", str(out), "--min-length", "1",
                     "--redact-pii"]) == 0
    assert "[EMAIL_REMOVED]" in read_jsonl(out)[0]["text"]


def test_config_file_is_used_and_cli_overrides_it(tmp_path, data_file, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path(".entropyguardrc.json").write_text(json.dumps(
        {"text_column": "text", "min_length": 1000, "batch_size": 2, "index_type": "hnsw"}
    ))
    seen = {}
    original_run = Pipeline.run

    def spy(self, config):
        seen["config"] = config
        return original_run(self, config)

    monkeypatch.setattr(Pipeline, "run", spy)

    out = tmp_path / "out.jsonl"
    assert cli.main(["--input", str(data_file), "--output", str(out)]) == 0
    assert read_jsonl(out) == []  # min_length=1000 from the rc file drops everything
    assert seen["config"].batch_size == 2 and seen["config"].index_type == "hnsw"

    assert cli.main(["--input", str(data_file), "--output", str(out), "--min-length", "5"]) == 0
    assert len(read_jsonl(out)) == 2


def test_explicit_config_flag(tmp_path, data_file):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"text_column": "text", "min_length": 5, "dry_run": True}))
    out = tmp_path / "out.jsonl"
    assert cli.main(["--input", str(data_file), "--output", str(out), "--config", str(cfg)]) == 0
    assert not out.exists()


def test_unknown_config_key_is_rejected(tmp_path, data_file, capsys):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"text_column": "text", "no_such_option": 1}))
    code = cli.main(["--input", str(data_file), "--output", str(tmp_path / "o.jsonl"),
                     "--config", str(cfg)])
    assert code == 2
    assert "no_such_option" in capsys.readouterr().err


def test_checkpoint_flags(tmp_path, data_file):
    out = tmp_path / "out.jsonl"
    code = cli.main(["--input", str(data_file), "--output", str(out), "--text-column", "text",
                     "--min-length", "5", "--checkpoint-dir", str(tmp_path / "ck"), "--resume"])
    assert code == 0 and len(read_jsonl(out)) == 2


@pytest.mark.parametrize(
    "extra, expected_code",
    [
        (["--dedup-threshold", "1.5"], 2),
        (["--min-length", "-1"], 2),
        (["--chunk-size", "10", "--chunk-overlap", "20"], 2),
        (["--text-column", "missing"], 2),
        (["--required-columns", "text,nope"], 2),
    ],
)
def test_invalid_arguments(tmp_path, data_file, extra, expected_code, capsys):
    code = cli.main(["--input", str(data_file), "--output", str(tmp_path / "o.jsonl"), *extra])
    assert code == expected_code
    assert "Error:" in capsys.readouterr().err


def test_missing_input_file(tmp_path, capsys):
    code = cli.main(["--input", str(tmp_path / "nope.jsonl"), "--output", str(tmp_path / "o.jsonl"),
                     "--text-column", "text"])
    assert code == 2
    assert "not found" in capsys.readouterr().err.lower()


def test_quiet_prints_no_summary(tmp_path, data_file, capsys):
    out = tmp_path / "out.jsonl"
    assert cli.main(["--input", str(data_file), "--output", str(out), "--text-column", "text",
                     "--quiet"]) == 0
    assert "Summary:" not in capsys.readouterr().err


def test_help(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "--dedup-threshold" in capsys.readouterr().out
