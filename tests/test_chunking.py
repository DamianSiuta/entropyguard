import polars as pl

from entropyguard.chunking import Chunker


def test_split_text_respects_chunk_size_and_overlap() -> None:
    text = (
        "Paragraph one line one.\n"
        "Paragraph one line two.\n\n"
        "Paragraph two is a bit longer and should be split across multiple chunks "
        "so that we can verify the behaviour of the recursive splitter. "
        "It contains several sentences and line breaks.\n"
        "Final short line."
    )

    chunk_size = 100
    overlap = 20
    chunker = Chunker(chunk_size=chunk_size, chunk_overlap=overlap)

    chunks = chunker.split_text(text)

    # Should produce more than one chunk for this long text
    assert len(chunks) > 1

    # All chunks must be non-empty and respect the max length
    for c in chunks:
        assert isinstance(c, str)
        assert c.strip() != ""
        assert len(c) <= chunk_size

    # Overlap: the end of one chunk should appear at the start of the next at least partially
    if len(chunks) >= 2:
        tail = chunks[0][-overlap:]
        assert tail.strip() != ""
        assert tail.strip() in chunks[1]


def test_chunk_dataframe_explodes_rows_and_preserves_metadata() -> None:
    long_text = (
        "This is a very long text that should be split into multiple smaller chunks "
        "for embedding and retrieval-augmented generation. "
        "We add some newlines here.\nAnd here.\n\nAnd another paragraph."
    )
    df = pl.DataFrame({"id": [42], "text": [long_text]})

    chunker = Chunker(chunk_size=80, chunk_overlap=10)
    chunked_df = chunker.chunk_dataframe(df, text_col="text")

    # We should now have multiple rows for the same original id
    assert chunked_df.height > 1
    assert set(chunked_df["id"].unique().to_list()) == {42}

    # All text chunks should be within the configured size limit
    for value in chunked_df["text"]:
        assert isinstance(value, str)
        assert 0 < len(value) <= 80


