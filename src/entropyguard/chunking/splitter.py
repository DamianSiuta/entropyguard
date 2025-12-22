"""
Advanced chunking utilities for splitting long texts into smaller fragments.

Design goals:
- No external NLP / LangChain dependencies
- Flexible recursive splitting with custom separators
- Hard fallback for CJK languages (Chinese, Japanese, Korean) and other languages without whitespace
- Polars-native integration: chunking a DataFrame via explode() while preserving metadata
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

import polars as pl


@dataclass
class Chunker:
    """
    Advanced recursive text chunker for RAG-style pipelines.

    Splits text into overlapping character windows using a recursive,
    delimiter-aware strategy with hard fallback for languages without whitespace.

    Features:
    - Custom separator hierarchy (default: paragraphs, lines, words, characters)
    - Recursive splitting: tries each separator level before falling back
    - Hard character-level splitting for CJK languages and continuous text
    - Configurable length function (default: len, can be extended to tokenizers)
    """

    chunk_size: int = 512
    chunk_overlap: int = 50
    separators: list[str] = field(default_factory=lambda: ["\n\n", "\n", " ", ""])
    length_function: Callable[[str], int] = field(default_factory=lambda: len)

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be >= 0")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if not self.separators:
            raise ValueError("separators list cannot be empty")

    # ---- Core text API -------------------------------------------------

    def split_text(self, text: str) -> list[str]:
        """
        Split a single text into chunks with overlap.

        Algorithm:
        1. Recursively split on separators in order (largest to smallest).
        2. If segments are still too large, try next separator level.
        3. Merge small segments back together up to chunk_size.
        4. Apply overlap between consecutive chunks.
        5. Hard fallback: if text still exceeds chunk_size (CJK, DNA, Base64),
           split character-by-character.

        Args:
            text: Input text to split

        Returns:
            List of text chunks, each <= chunk_size characters
        """
        if not text:
            return []

        # Step 1: Recursive splitting
        segments = self._split_recursively(text, self.separators)

        # Step 2: Merge segments with overlap
        chunks = self._merge_segments_with_overlap(segments)

        return chunks

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

        Args:
            df: Input DataFrame or LazyFrame
            text_col: Name of the text column to chunk

        Returns:
            Chunked DataFrame or LazyFrame with exploded text column
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

    def _split_recursively(
        self, text: str, separators: Sequence[str]
    ) -> list[str]:
        """
        Recursively split text by separators, trying each level in order.

        Large segments are broken down using the current separator.
        If segments are still too large, recursively try the next separator.
        Small segments are preserved to maintain semantic structure.

        Args:
            text: Text to split
            separators: List of separators to try (in order, largest to smallest)

        Returns:
            List of text segments, each <= chunk_size (or as small as possible)
        """
        # Base case: text is small enough
        if self.length_function(text) <= self.chunk_size:
            return [text.strip()] if text.strip() else []

        # Try each separator level
        for i, sep in enumerate(separators):
            # Hard fallback: empty separator means character-level splitting
            if sep == "":
                return self._hard_split(text)

            # Split by current separator
            parts = text.split(sep)

            # If separator not found, try next one
            if len(parts) == 1:
                continue

            # Recursively split each part that's still too large
            segments: list[str] = []
            for part in parts:
                part = part.strip()
                if not part:
                    continue

                if self.length_function(part) <= self.chunk_size:
                    segments.append(part)
                else:
                    # Recursively try remaining separators
                    remaining_seps = separators[i + 1 :]
                    if remaining_seps:
                        segments.extend(
                            self._split_recursively(part, remaining_seps)
                        )
                    else:
                        # No more separators, hard split
                        segments.extend(self._hard_split(part))

            # If we got good segments, return them
            if segments:
                return segments

        # Fallback: if all separators failed, hard split
        return self._hard_split(text)

    def _hard_split(self, text: str) -> list[str]:
        """
        Hard character-level split for CJK languages and continuous text.

        Used when:
        - No separators are available (empty separator list)
        - All separators failed to split the text (e.g., Chinese without spaces)
        - Text is continuous (DNA sequences, Base64, etc.)

        Args:
            text: Text to split character-by-character

        Returns:
            List of fixed-size chunks (exactly chunk_size, except possibly the last)
        """
        chunks: list[str] = []
        start = 0
        text_len = self.length_function(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk = text[start:end]
            if chunk.strip():  # Skip empty chunks
                chunks.append(chunk)
            start = end

        return chunks if chunks else [text]  # Ensure at least one chunk

    def _merge_segments_with_overlap(self, segments: Iterable[str]) -> list[str]:
        """
        Merge small segments into fixed-size overlapping chunks.

        Greedily combines segments up to chunk_size, then starts a new chunk
        with overlap from the previous one.

        Args:
            segments: Iterable of text segments to merge

        Returns:
            List of chunks with overlap
        """
        chunks: list[str] = []
        current_chunk = ""

        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue

            seg_len = self.length_function(seg)

            # If segment alone exceeds chunk_size, hard split it
            if seg_len > self.chunk_size:
                # Flush current chunk first
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""

                # Hard split the oversized segment
                hard_chunks = self._hard_split(seg)
                for i, hc in enumerate(hard_chunks):
                    if i == 0 and current_chunk:
                        # Try to merge first hard chunk with current
                        if (
                            self.length_function(current_chunk)
                            + self.length_function(hc)
                            <= self.chunk_size
                        ):
                            current_chunk = f"{current_chunk} {hc}".strip()
                            continue
                    chunks.append(hc)
                continue

            # Try to add segment to current chunk
            current_len = self.length_function(current_chunk)
            separator_len = 1 if current_chunk else 0
            combined_len = current_len + separator_len + seg_len

            if combined_len <= self.chunk_size:
                # Can fit, add to current chunk
                if current_chunk:
                    current_chunk = f"{current_chunk} {seg}".strip()
                else:
                    current_chunk = seg
            else:
                # Doesn't fit, start new chunk with overlap
                if current_chunk:
                    chunks.append(current_chunk)

                    # Calculate overlap prefix (character-level, no separator added)
                    if self.chunk_overlap > 0 and current_len > self.chunk_overlap:
                        overlap_prefix = current_chunk[-self.chunk_overlap :]
                        # Merge overlap with new segment (no separator, direct concatenation)
                        overlap_with_seg = f"{overlap_prefix}{seg}".strip()
                        if self.length_function(overlap_with_seg) <= self.chunk_size:
                            current_chunk = overlap_with_seg
                        else:
                            # Overlap + segment too large, just use segment
                            current_chunk = seg
                    else:
                        current_chunk = seg
                else:
                    current_chunk = seg

        # Flush remaining chunk
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    @staticmethod
    def decode_separator(sep: str) -> str:
        """
        Decode separator string from CLI (handles escape sequences like \\n).

        Args:
            sep: Separator string from command line (may contain \\n, \\t, etc.)

        Returns:
            Decoded separator string
        """
        try:
            # Try to decode escape sequences
            return codecs.decode(sep, "unicode_escape")
        except (UnicodeDecodeError, ValueError):
            # If decoding fails, return as-is
            return sep
