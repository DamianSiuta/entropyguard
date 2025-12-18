"""
Chunking utilities for splitting long texts into smaller fragments.

Design goals:
- No external NLP / LangChain dependencies
- Simple, predictable recursive splitting on delimiters:
  - First on double newlines (paragraphs)
  - Then on single newlines
  - Then on spaces
- Polars-native integration: chunking a DataFrame via explode() while
  preserving metadata columns such as IDs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

import polars as pl


@dataclass
class Chunker:
    """
    Lightweight text chunker for RAG-style pipelines.

    Splits text into overlapping character windows using a recursive,
    delimiter-aware strategy. Intended to approximate the behaviour of
    tools like RecursiveCharacterTextSplitter without any external deps.
    """

    chunk_size: int = 512
    chunk_overlap: int = 50

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be >= 0")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

    # ---- Core text API -------------------------------------------------

    def split_text(self, text: str) -> list[str]:
        """
        Split a single text into chunks with overlap.

        The algorithm:
        1. Recursively split on separators in order: ["\\n\\n", "\\n", " "].
        2. Build chunks of at most `chunk_size` chars by greedily concatenating segments.
        3. Apply a character-level overlap of `chunk_overlap` between consecutive chunks.
        """
        if not text:
            return []

        segments = self._split_recursively(text, separators=["\n\n", "\n", " "])
        return self._merge_segments(segments)

    # ---- Polars integration --------------------------------------------

    def chunk_dataframe(
        self,
        df: pl.DataFrame | pl.LazyFrame,
        text_col: str,
    ) -> pl.DataFrame | pl.LazyFrame:
        """
        Chunk a Polars DataFrame/LazyFrame by exploding a text column into chunks.

        Each input row becomes N rows (one per chunk) while all other columns,
        including IDs or original indexes, are preserved and duplicated as needed.
        """
        if text_col not in df.columns:  # type: ignore[attr-defined]
            raise ValueError(f"Text column '{text_col}' not found in DataFrame")

        def _split(value: str | None) -> list[str]:
            if value is None:
                return []
            return self.split_text(str(value))

        if isinstance(df, pl.LazyFrame):
            chunked = df.with_columns(
                pl.col(text_col).map_elements(
                    _split,
                    return_dtype=pl.List(pl.Utf8),
                )
            ).explode(text_col)
            return chunked

        # Eager DataFrame
        chunked_df = df.with_columns(
            pl.col(text_col).map_elements(
                _split,
                return_dtype=pl.List(pl.Utf8),
            )
        ).explode(text_col)

        return chunked_df

    # ---- Internal helpers ----------------------------------------------

    def _split_recursively(self, text: str, separators: Sequence[str]) -> list[str]:
        """
        Recursively split text by the provided separators, but only when needed.

        Large segments are broken down, while small ones are left intact so that
        semantic structure (paragraphs, lines, words) is preserved as much as possible.
        """
        segments: list[str] = [text]

        for sep in separators:
            next_segments: list[str] = []
            for segment in segments:
                if len(segment) <= self.chunk_size:
                    next_segments.append(segment)
                    continue

                parts = segment.split(sep)
                # If the separator is not present, keep the segment as-is
                if len(parts) == 1:
                    next_segments.append(segment)
                else:
                    for part in parts:
                        stripped = part.strip()
                        if stripped:
                            next_segments.append(stripped)

            segments = next_segments

        # As a final fallback, if any segment is still longer than chunk_size,
        # hard-split it into fixed windows.
        final_segments: list[str] = []
        for segment in segments:
            if len(segment) <= self.chunk_size:
                final_segments.append(segment)
            else:
                start = 0
                while start < len(segment):
                    final_segments.append(segment[start : start + self.chunk_size])
                    start += self.chunk_size

        return final_segments

    def _merge_segments(self, segments: Iterable[str]) -> list[str]:
        """
        Merge smaller segments into fixed-size overlapping chunks.
        """
        chunks: list[str] = []
        current = ""

        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue

            if not current:
                current = seg
                continue

            # If we can safely append this segment to the current chunk, do it
            if len(current) + 1 + len(seg) <= self.chunk_size:
                current = f"{current} {seg}"
            else:
                # Flush current chunk
                chunks.append(current)

                # Start new chunk with overlap from the end of the previous one
                if self.chunk_overlap > 0 and len(current) > self.chunk_overlap:
                    prefix = current[-self.chunk_overlap :]
                else:
                    prefix = ""

                combined = f"{prefix} {seg}".strip() if prefix else seg
                current = combined

        if current:
            chunks.append(current)

        return chunks


