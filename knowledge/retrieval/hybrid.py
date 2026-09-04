"""BM25 + Chroma 向量检索 + RRF 融合。

BM25 负责精确关键词，向量检索负责口语化语义，两路互相补充。
"""

from pathlib import Path

from knowledge.indexing import BM25Store, EmbeddingService, VectorStore
from knowledge.models import SearchResult
from knowledge.retrieval.fusion import reciprocal_rank_fusion


class HybridRetriever:
    def __init__(self, index_dir: Path, require_vectors: bool = False) -> None:
        # BM25 索引直接从 JSON 恢复；不需要联网。
        self.bm25 = BM25Store()
        self.bm25.load(index_dir / "bm25_index.json")
        self.embedding: EmbeddingService | None = None
        self.vector_store: VectorStore | None = None

        chroma_path = index_dir / "chroma"
        if chroma_path.exists():
            # 查询向量必须由构建索引时的同一个模型生成。
            self.embedding = EmbeddingService()
            self.vector_store = VectorStore(chroma_path)
            if self.vector_store.count() == 0:
                self.vector_store = None
                self.embedding = None
        elif require_vectors:
            raise FileNotFoundError(f"缺少 Chroma 向量数据库：{chroma_path}")

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """分别多召回一些候选，再用 RRF 按排名融合并截取 top-k。"""
        candidate_count = max(top_k * 4, 20)
        groups = [self.bm25.search(query, candidate_count)]
        if self.embedding is not None and self.vector_store is not None:
            # 只有向量数据库已经构建时才请求查询向量。
            query_vector = self.embedding.embed_query(query)
            groups.append(self.vector_store.search(query_vector, candidate_count))
        return reciprocal_rank_fusion(groups, top_k)
