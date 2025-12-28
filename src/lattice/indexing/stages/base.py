from typing import Protocol

from lattice.indexing.context import PipelineContext


class PipelineStage(Protocol):
    name: str

    async def execute(self, ctx: PipelineContext) -> None: ...
