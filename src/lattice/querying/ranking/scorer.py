from lattice.querying.ranking.models import RankedResult, RankingConfig, RankingSignal
from lattice.shared.config import ScorerConfig
from lattice.shared.types import ResultSource


class ResultScorer:
    def __init__(self, config: RankingConfig):
        self.config = config
        self._scorer_config = ScorerConfig

    def score_graph_result(
        self,
        result: RankedResult,
        weights: dict[str, float],
        centrality_scores: dict[str, dict[str, int]],
        query_entities: set[str],
        is_primary: bool = False,
        is_caller: bool = False,
        is_callee: bool = False,
    ) -> None:
        signals = {}
        sc = self._scorer_config

        base_score = 1.0
        if is_primary:
            base_score = 1.0
        elif is_caller or is_callee:
            depth = result.depth_from_query or 1
            base_score = max(sc.min_depth_score, 1.0 - (depth - 1) * sc.depth_decay_rate)

        signals[RankingSignal.GRAPH_MATCH.value] = base_score

        entity_match = 0.0
        if result.entity_name.lower() in query_entities:
            entity_match = 1.0
        elif any(qe in result.entity_name.lower() for qe in query_entities):
            entity_match = sc.partial_entity_match_score
        signals[RankingSignal.QUERY_ENTITY_MATCH.value] = entity_match

        rel_score = 0.0
        if is_primary:
            rel_score = sc.relationship_score_primary
        elif is_caller:
            rel_score = sc.relationship_score_caller
        elif is_callee:
            rel_score = sc.relationship_score_callee
        else:
            rel_score = sc.relationship_score_default
        signals[RankingSignal.RELATIONSHIP_RELEVANCE.value] = rel_score

        centrality_score = 0.0
        entity_key = result.qualified_name or result.entity_name
        if entity_key in centrality_scores:
            scores = centrality_scores[entity_key]
            total_degree = scores.get("total_degree", 0)
            centrality_score = min(1.0, total_degree / sc.centrality_normalization_factor)
        signals[RankingSignal.CENTRALITY.value] = centrality_score

        context_score = 0.0
        if result.summary:
            context_score += sc.context_score_summary
        if result.docstring:
            context_score += sc.context_score_docstring
        if result.signature:
            context_score += sc.context_score_signature
        if result.content:
            context_score += sc.context_score_content
        signals[RankingSignal.CONTEXT_RICHNESS.value] = context_score

        final_score = (
            signals[RankingSignal.GRAPH_MATCH.value] * weights["graph_weight"]
            + signals.get(RankingSignal.QUERY_ENTITY_MATCH.value, 0)
            * self.config.entity_match_bonus
            + signals.get(RankingSignal.RELATIONSHIP_RELEVANCE.value, 0)
            * self.config.relationship_bonus
            + signals.get(RankingSignal.CENTRALITY.value, 0) * weights["centrality_weight"]
            + signals.get(RankingSignal.CONTEXT_RICHNESS.value, 0) * weights["context_weight"]
        )

        result.final_score = final_score
        result.signal_scores = signals
        result.source = ResultSource.GRAPH.value

    def score_vector_result(
        self,
        result: RankedResult,
        vector_score: float,
        weights: dict[str, float],
        centrality_scores: dict[str, dict[str, int]],
        query_entities: set[str],
    ) -> None:
        signals = {}
        sc = self._scorer_config

        signals[RankingSignal.VECTOR_SIMILARITY.value] = vector_score

        entity_match = 0.0
        if result.entity_name.lower() in query_entities:
            entity_match = 1.0
        elif any(qe in result.entity_name.lower() for qe in query_entities):
            entity_match = sc.partial_entity_match_score
        signals[RankingSignal.QUERY_ENTITY_MATCH.value] = entity_match

        centrality_score = 0.0
        entity_key = result.qualified_name or result.entity_name
        if entity_key in centrality_scores:
            scores = centrality_scores[entity_key]
            total_degree = scores.get("total_degree", 0)
            centrality_score = min(1.0, total_degree / sc.centrality_normalization_factor)
        signals[RankingSignal.CENTRALITY.value] = centrality_score

        quality_score = 0.0
        if result.content:
            content_len = len(result.content)
            if sc.quality_optimal_min_chars < content_len < sc.quality_optimal_max_chars:
                quality_score = sc.quality_score_optimal
            elif sc.quality_acceptable_min_chars < content_len < sc.quality_acceptable_max_chars:
                quality_score = sc.quality_score_acceptable
            else:
                quality_score = sc.quality_score_poor
        signals[RankingSignal.CODE_QUALITY.value] = quality_score

        final_score = (
            signals[RankingSignal.VECTOR_SIMILARITY.value] * weights["vector_weight"]
            + signals.get(RankingSignal.QUERY_ENTITY_MATCH.value, 0)
            * self.config.entity_match_bonus
            + signals.get(RankingSignal.CENTRALITY.value, 0) * weights["centrality_weight"]
            + signals.get(RankingSignal.CODE_QUALITY.value, 0) * sc.code_quality_weight
        )

        result.final_score = final_score
        result.signal_scores = signals
        result.source = ResultSource.VECTOR.value
