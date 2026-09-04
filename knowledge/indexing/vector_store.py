"""Chroma 向量数据库适配器。

这个文件只负责“向量怎么存、怎么查”，不负责调用 Embedding 模型。
这样以后更换向量数据库时，上层检索和 Agent 代码不需要跟着修改。
"""

import json
from pathlib import Path

import chromadb

from knowledge.models import LegalChunk, SearchResult


class VectorStore:
    """把法条、向量和元数据持久化到本地 Chroma。"""

    def __init__(
        self,
        persist_directory: Path,
        collection_name: str = "civil_code",
    ) -> None:
        # PersistentClient 会把数据库文件写入指定目录；程序重启后仍可查询。
        persist_directory.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(persist_directory))

        # cosine 表示使用余弦距离，适合比较文本 Embedding 的方向相似度。
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def _metadata(chunk: LegalChunk) -> dict[str, str | int]:
        """把 LegalChunk 转成 Chroma 支持的基础类型元数据。"""
        return {
            "law_name": chunk.law_name,
            "article_number": chunk.article_number or 0,
            "article_label": chunk.article_label,
            "article_title": chunk.article_title,
            "content": chunk.content,
            "source_file": chunk.source_file or "",
            # Chroma 元数据不直接支持 list/dict，因此序列化成 JSON 字符串。
            "source_pages": json.dumps(chunk.source_pages, ensure_ascii=False),
            "source_url": chunk.source_url or "",
            "effective_date": chunk.effective_date or "",
            "status": chunk.status,
            "extra_metadata": json.dumps(chunk.metadata, ensure_ascii=False),
        }

    @staticmethod
    def _chunk(chunk_id: str, document: str, metadata: dict) -> LegalChunk:
        """把 Chroma 查询结果恢复成项目统一的 LegalChunk。"""
        return LegalChunk(
            chunk_id=chunk_id,
            law_name=str(metadata.get("law_name", "")),
            article_number=int(metadata.get("article_number", 0)) or None,
            article_label=str(metadata.get("article_label", "")),
            article_title=str(metadata.get("article_title", "")),
            content=str(metadata.get("content", "")),
            retrieval_text=document,
            source_file=str(metadata.get("source_file", "")) or None,
            source_pages=json.loads(str(metadata.get("source_pages", "[]"))),
            source_url=str(metadata.get("source_url", "")) or None,
            effective_date=str(metadata.get("effective_date", "")) or None,
            status=str(metadata.get("status", "现行有效")),
            metadata=json.loads(str(metadata.get("extra_metadata", "{}"))),
        )

    def upsert(self, chunks: list[LegalChunk], vectors: list[list[float]]) -> None:
        """新增或更新一批法条；相同 chunk_id 会被覆盖，不会重复。"""
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        if not chunks:
            return

        self.collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=vectors,
            documents=[chunk.retrieval_text or chunk.content for chunk in chunks],
            metadatas=[self._metadata(chunk) for chunk in chunks],
        )

    def search(self, query_vector: list[float], top_k: int = 10) -> list[SearchResult]:
        """用问题向量查询最接近的法条。"""
        record_count = self.count()
        if record_count == 0:
            return []
        response = self.collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, record_count),
            include=["documents", "metadatas", "distances"],
        )
        if not response["ids"] or not response["ids"][0]:
            return []

        results: list[SearchResult] = []
        for chunk_id, document, metadata, distance in zip(
            response["ids"][0],
            response["documents"][0],
            response["metadatas"][0],
            response["distances"][0],
        ):
            # cosine distance 越小越相似；转成“越大越相似”的分数便于观察。
            results.append(SearchResult(
                chunk=self._chunk(chunk_id, document, metadata),
                score=1.0 - float(distance),
                retrieval_sources=["vector"],
            ))
        return results

    def count(self) -> int:
        """返回数据库中法条数量，用于启动检查和测试。"""
        return self.collection.count()
