"""Pipeline stage definitions - re-exports from core.types."""

from lattice.core.types import PipelineStage
from lattice.pipeline.progress import StageProgress

__all__ = ["PipelineStage", "StageProgress"]
