from dataclasses import asdict, dataclass, field


# 法条分块
@dataclass
class LegalChunk:
    chunk_id: str
    law_name: str
    content: str
    article_number: int | None = None
    article_label: str = ""
    article_title: str = ""
    retrieval_text: str = ""
    source_file: str | None = None
    source_pages: list[int] = field(default_factory=list)
    source_url: str | None = None
    effective_date: str | None = None
    status: str = "现行有效"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LegalChunk":
        fields = cls.__dataclass_fields__
        return cls(**{key: value for key, value in data.items() if key in fields})



# 检索结果
@dataclass
class SearchResult:
    chunk: LegalChunk
    score: float
    retrieval_sources: list[str] = field(default_factory=list)
