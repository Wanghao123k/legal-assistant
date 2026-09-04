"""无第三方依赖的中文 BM25 索引。"""

import json
import math
import re
from collections import Counter
from pathlib import Path

from knowledge import LegalChunk, SearchResult


class BM25Store:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.chunks: list[LegalChunk] = []
        self.documents: list[list[str]] = []
        self.document_frequency: Counter[str] = Counter()
        self.average_length = 0.0

    @staticmethod
    def _chinese_number_to_int(value: str) -> int:
        digits = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
                  "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
        units = {"十": 10, "百": 100, "千": 1000}
        result = current = 0
        for character in value:
            if character in digits:
                current = digits[character]
            elif character in units:
                result += (current or 1) * units[character]
                current = 0
        return result + current

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """用汉字单字+二元组兼顾召回，用英文/数字词保留精确匹配。"""
        normalized = re.sub(r"\s+", "", text.lower())
        article_tokens = [
            f"article_{BM25Store._chinese_number_to_int(value)}"
            for value in re.findall(r"第([零一二三四五六七八九十百千]+)条", normalized)
        ]
        article_tokens.extend(
            f"article_{value}" for value in re.findall(r"第?(\d+)条", normalized)
        )
        chinese = re.findall(r"[\u4e00-\u9fff]+", normalized)
        tokens = article_tokens + re.findall(r"[a-z]+|\d+", normalized)
        for sequence in chinese:
            tokens.extend(sequence)
            tokens.extend(sequence[index:index + 2] for index in range(len(sequence) - 1))
        return tokens

    def build(self, chunks: list[LegalChunk]) -> None:
        self.chunks = chunks
        self.documents = [self.tokenize(chunk.retrieval_text or chunk.content) for chunk in chunks]
        self.document_frequency = Counter()
        for document in self.documents:
            self.document_frequency.update(set(document))
        self.average_length = (
            sum(map(len, self.documents)) / len(self.documents) if self.documents else 0.0
        )

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        if not self.documents:
            raise RuntimeError("BM25 index has not been built or loaded")
        query_terms = Counter(self.tokenize(query))
        total = len(self.documents)
        scored: list[tuple[float, int]] = []
        for index, document in enumerate(self.documents):
            frequencies = Counter(document)
            length_normalizer = 1 - self.b + self.b * len(document) / self.average_length
            score = 0.0
            for term, query_frequency in query_terms.items():
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                document_frequency = self.document_frequency[term]
                idf = math.log(1 + (total - document_frequency + 0.5) /
                               (document_frequency + 0.5))
                score += query_frequency * idf * (
                    frequency * (self.k1 + 1)
                    / (frequency + self.k1 * length_normalizer)
                )
            if score > 0:
                scored.append((score, index))
        scored.sort(reverse=True)
        return [
            SearchResult(self.chunks[index], score, ["bm25"])
            for score, index in scored[:top_k]
        ]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "k1": self.k1,
            "b": self.b,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def load(self, path: Path) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.k1 = payload["k1"]
        self.b = payload["b"]
        self.build([LegalChunk.from_dict(item) for item in payload["chunks"]])
