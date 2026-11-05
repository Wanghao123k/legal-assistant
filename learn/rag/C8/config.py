"""
RAG系统配置文件
"""

from dataclasses import asdict, dataclass
from typing import Dict, Any

# 这个装饰器是自动生成一写通用的类方法
"""
加上 @dataclass 后，主要会自动生成：
- __init__()：创建对象时，为字段赋值。
- __repr__()：打印对象时，展示字段名称和值。
- __eq__()：用 == 比较两个同类对象的字段值。
"""
@dataclass
class RAGConfig:
    """RAG系统配置类"""

    # 路径配置
    data_path: str = "../data/cook/"
    index_save_path: str = "./vector_index"

    # 模型配置
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    llm_model: str = "deepseek-v4-pro"

    # 检索配置
    top_k: int = 3

    # 生成配置
    temperature: float = 0.1
    max_tokens: int = 2048

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'RAGConfig':
        """从字典创建配置对象"""
        return cls(**config_dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

# 默认配置实例
DEFAULT_CONFIG = RAGConfig()