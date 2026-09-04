"""OpenAI 兼容的 Embedding 服务。

Embedding 只负责把文字转换成向量，不保存数据；保存由 VectorStore 负责。
构建索引和查询必须使用同一个模型，否则两个向量不在同一空间中。
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


class EmbeddingService:
    """封装智谱 embedding-3 等 OpenAI 兼容接口。"""

    def __init__(self, batch_size: int = 64) -> None:
        project_root = Path(__file__).resolve().parents[2]
        load_dotenv(project_root / ".env")
        self.model = os.getenv("EMBEDDING_MODEL", "embedding-3")
        self.batch_size = batch_size
        self.client = OpenAI(
            api_key=os.getenv("EMBEDDING_API_KEY"),
            base_url=os.getenv("EMBEDDING_BASE_URL"),
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量生成知识库法条向量，避免逐条请求造成大量网络开销。"""
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            response = self.client.embeddings.create(
                model=self.model,
                input=texts[start:start + self.batch_size],
            )
            vectors.extend(item.embedding for item in response.data)
        return vectors

    def embed_query(self, query: str) -> list[float]:
        """用户每次查询时只需要生成一个问题向量。"""
        return self.embed_documents([query])[0]
