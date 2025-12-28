import json
import logging

from lattice.documents.models import DocumentChunk, ImplicitLink
from lattice.embeddings.client import CollectionName, QdrantManager
from lattice.embeddings.embedder import Embedder
from lattice.providers import get_llm_provider

logger = logging.getLogger(__name__)


LINK_FINDER_PROMPT = """You are analyzing documentation to identify which code entities it describes or relates to.

## Documentation Section
Heading Path: {heading_path}
Content:
{doc_content}

## Candidate Code Entities (found via semantic similarity)
{entity_list}

## Task
Identify which code entities this documentation section describes, explains, or is relevant to.

For each relevant entity, provide:
1. The entity's qualified name (exactly as shown)
2. Relevance level: "high" (directly documents this entity), "medium" (discusses related behavior), "low" (tangentially related)
3. Brief reasoning (1 sentence)

Respond in JSON format:
{{
    "links": [
        {{
            "entity_qualified_name": "exact.qualified.name",
            "entity_type": "Function|Class|Method",
            "relevance": "high|medium|low",
            "reasoning": "Why this doc relates to this code"
        }}
    ]
}}

Only include entities that are genuinely relevant. Return empty links array if none are relevant."""


class AILinkFinder:
    def __init__(
        self,
        qdrant: QdrantManager,
        embedder: Embedder,
    ):
        self.qdrant = qdrant
        self.embedder = embedder
        self._llm = get_llm_provider()

    async def find_links(
        self,
        chunk: DocumentChunk,
        candidate_limit: int = 20,
    ) -> list[ImplicitLink]:
        try:
            embedding = await self.embedder.embed(chunk.content)

            results = await self.qdrant.search(
                collection=CollectionName.CODE_CHUNKS.value,
                query_vector=embedding,
                limit=candidate_limit,
                filters={"project_name": chunk.project_name},
            )

            if not results:
                return []

            candidates = []
            seen_entities = set()
            for r in results:
                entity_name = r["payload"].get("graph_node_id") or r["payload"].get(
                    "entity_name"
                )
                if entity_name and entity_name not in seen_entities:
                    seen_entities.add(entity_name)
                    candidates.append(
                        {
                            "qualified_name": entity_name,
                            "entity_type": r["payload"].get("entity_type", "unknown"),
                            "file_path": r["payload"].get("file_path", ""),
                            "content_preview": r["payload"].get("content", "")[:300],
                            "score": r["score"],
                        }
                    )

            if not candidates:
                return []

            entity_list = "\n".join(
                f"- {c['qualified_name']} ({c['entity_type']}) in {c['file_path']}\n"
                f"  Preview: {c['content_preview'][:200]}..."
                for c in candidates[:15]
            )

            prompt = LINK_FINDER_PROMPT.format(
                heading_path=" > ".join(chunk.heading_path),
                doc_content=chunk.content[:2500],
                entity_list=entity_list,
            )

            response = await self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
            )

            try:
                json_str = response
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    json_str = response.split("```")[1].split("```")[0]

                data = json.loads(json_str)

                return [
                    ImplicitLink(
                        entity_qualified_name=link["entity_qualified_name"],
                        entity_type=link.get("entity_type", "unknown"),
                        confidence=self._relevance_to_confidence(link["relevance"]),
                        reasoning=link["reasoning"],
                    )
                    for link in data.get("links", [])
                    if link["entity_qualified_name"] in seen_entities
                ]
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse link finder response: {e}")
                return []

        except Exception as e:
            logger.error(f"Link finding failed: {e}")
            return []

    def _relevance_to_confidence(self, relevance: str) -> float:
        return {"high": 0.90, "medium": 0.70, "low": 0.50}.get(relevance.lower(), 0.50)
