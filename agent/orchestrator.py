"""最小 RAG 编排：检索一次，再依据证据生成。"""

import os
from pathlib import Path

from agent.generator import AnswerGenerator
from knowledge.models import SearchResult
from knowledge.retrieval import HybridRetriever

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LegalRAG:
    """把检索器和生成器串成最小 RAG，不包含复杂的多轮 Agent。"""

    def __init__(self, index_dir: Path = Path("data/processed/indexes")) -> None:
        if not index_dir.is_absolute():
            index_dir = PROJECT_ROOT / index_dir
        self.retriever = HybridRetriever(index_dir)
        self.generator = AnswerGenerator()
        self.top_k = int(os.getenv("RETRIEVAL_TOP_K", "5"))

    def retrieve(self, question: str) -> list[SearchResult]:
        """第一阶段 Retrieval：从知识库找出 top-k 法条证据。"""
        return self.retriever.search(question, self.top_k)

    def answer(self, question: str) -> tuple[str, list[SearchResult]]:
        """第二阶段 Augmented Generation：带着证据调用大模型。"""
        results = self.retrieve(question)
        if not results:
            return "没有检索到足够的民法典依据。", []
        return self.generator.generate(question, results), results
