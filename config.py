from dataclasses import dataclass
from pathlib import Path


_CONFIG_DIR = Path(__file__).resolve().parent


@dataclass
class RAGConfig:
    """RAG系统配置类"""
    def __init__(
        self,
        data_path: str = "./data",
        index_save_path: str = "./rag/vector_index",
        embedding_model: str = "BAAI/bge-base-zh-v1.5",
        llm_model: str = "deepseek-v4-pro",
        top_k: int = 3,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> None:
        self.data_path = data_path
        self.index_save_path = index_save_path
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self.top_k = top_k
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.__post_init__()

    def __post_init__(self) -> None:
        self.data_path = self.to_absolute_path(self.data_path)
        self.index_save_path = self.to_absolute_path(self.index_save_path)

    @staticmethod
    def to_absolute_path(path: str) -> str:
        """以本配置文件所在目录为基准解析路径，返回绝对路径字符串。"""
        return str((_CONFIG_DIR / path).resolve())


# 默认配置实例
DEFAULT_CONFIG = RAGConfig()