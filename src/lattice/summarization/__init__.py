"""Summarization module for AI-generated code summaries."""

from lattice.summarization.prompts import (
    CLASS_CODE_MAX_CHARS,
    FILE_CODE_MAX_CHARS,
    FUNCTION_CODE_MAX_CHARS,
    SummaryPrompts,
)
from lattice.summarization.summarizer import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    SYSTEM_MESSAGE,
    CodeSummarizer,
)

__all__ = [
    "CLASS_CODE_MAX_CHARS",
    "CodeSummarizer",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TEMPERATURE",
    "FILE_CODE_MAX_CHARS",
    "FUNCTION_CODE_MAX_CHARS",
    "SummaryPrompts",
    "SYSTEM_MESSAGE",
]
