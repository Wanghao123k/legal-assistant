"""Reciprocal Rank Fusion 排名融合。"""

from knowledge.models import SearchResult


def reciprocal_rank_fusion(
    result_groups: list[list[SearchResult]], top_k: int, rank_constant: int = 60
) -> list[SearchResult]:
    """融合多路排名。

    RRF 不直接比较 BM25 分数和余弦分数，因为两者量纲完全不同；它只看
    每条结果在各自列表中的名次。某法条同时被两路排在前面时，融合分更高。
    """
    scores: dict[str, float] = {}
    results: dict[str, SearchResult] = {}
    sources: dict[str, set[str]] = {}
    for group in result_groups:
        for rank, result in enumerate(group, start=1):
            chunk_id = result.chunk.chunk_id
            # 标准 RRF 公式：1 / (k + rank)。rank 越小，贡献越大。
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (rank_constant + rank)
            results[chunk_id] = result
            sources.setdefault(chunk_id, set()).update(result.retrieval_sources)

    ordered = sorted(scores, key=scores.get, reverse=True)[:top_k]
    return [
        SearchResult(
            chunk=results[chunk_id].chunk,
            score=scores[chunk_id],
            retrieval_sources=sorted(sources[chunk_id]),
        )
        for chunk_id in ordered
    ]
