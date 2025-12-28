import json
import logging

from lattice.documents.models import DocumentChunk, ImplicitLink
from lattice.infrastructure.qdrant import CollectionName, QdrantManager
from lattice.prompts import get_prompt
from lattice.infrastructure.llm import BaseEmbeddingProvider, get_llm_provider
from lattice.shared.config.loader import LinkFinderConfig

logger = logging.getLogger(__name__)


class AILinkFinder:
    def __init__(
        self,
        qdrant: QdrantManager,
        embedder: BaseEmbeddingProvider,
    ):
        self.qdrant = qdrant
        self.embedder = embedder
        self._llm = get_llm_provider()

    async def find_links(
        self,
        chunk: DocumentChunk,
        candidate_limit: int = LinkFinderConfig.candidate_limit,
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
                            "content_preview": r["payload"].get("content", "")[:LinkFinderConfig.content_preview_length],
                            "score": r["score"],
                        }
                    )

            if not candidates:
                return []

            entity_list = "\n".join(
                f"- {c['qualified_name']} ({c['entity_type']}) in {c['file_path']}\n"
                f"  Preview: {c['content_preview'][:200]}..."
                for c in candidates[:LinkFinderConfig.entity_list_limit]
            )

            prompt = get_prompt(
                "documents", "link_finder",
                heading_path=" > ".join(chunk.heading_path),
                doc_content=chunk.content[:LinkFinderConfig.doc_content_max],
                entity_list=entity_list,
            )

            response = await self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=LinkFinderConfig.max_tokens,
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
        return {
            "high": LinkFinderConfig.relevance_high,
            "medium": LinkFinderConfig.relevance_medium,
            "low": LinkFinderConfig.relevance_low,
        }.get(relevance.lower(), LinkFinderConfig.relevance_low)
