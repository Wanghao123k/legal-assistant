from dotenv import load_dotenv

load_dotenv("../../../.env")

from pathlib import Path
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
import logging

logger = logging.getLogger(__name__)

class IndexConstructionModule:
    """索引构建模块  - 负责向量化和索引构建"""

    def __init__(
            self,
            model_name: str = "BAAI/bge-small-zh-v1.5",
            index_save_path: str = "./vector_index"
    ):
        self.model_name = model_name
        self.index_save_path = index_save_path
        self.embeddings = None
        self.vectorstore = None
        self.setup_embeddings()


    def setup_embeddings(self):
        """初始化嵌入模型"""
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.model_name,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True},
            cache_folder=str(Path(__file__).resolve().parents[2] / "huggingface"),
        )

    def build_vector_index(self, chunks: List[Document]) -> FAISS:
        """构建向量索引"""
        if not chunks:
            raise ValueError("文档块列表不能为空")

        # 提取文本内容
        texts = [chunk.page_content for chunk in chunks]
        meta_datas = [chunk.metadata for chunk in chunks]

        self.vectorstore = FAISS.from_texts(
            texts=texts,
            metadatas=meta_datas,
            embedding=self.embeddings,
        )
        return self.vectorstore

    def save_index(self):
        """保存向量索引到配置的路径"""
        if not self.vectorstore:
            raise ValueError("请先构建向量索引")

        # 确保保存目录在
        Path(self.index_save_path).mkdir(parents=True, exist_ok=True)

        self.vectorstore.save_local(self.index_save_path)

    def load_index(self):
        """从配置的路径加载向量索引"""
        if not self.embeddings:
            self.setup_embeddings()

        if not Path(self.index_save_path).exists():
            return None

        self.vectorstore = FAISS.load_local(
            self.index_save_path,
            self.embeddings,
            # 允许使用 Python 的 pickle 加载之前保存的对象。
            allow_dangerous_deserialization=True,
        )
        return self.vectorstore

    def add_documents(self, new_chunks: List[Document]):
        """
        向现有索引添加新文档
        """

        if not self.vectorstore:
            raise ValueError("请先构建向量索引")

        logger.info(f"正在添加{len(new_chunks)}个新文档到索引")
        self.vectorstore.add_documents(new_chunks)
        logger.info("添加新文档完成")

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        """
        相似度搜索

        Args:
            query: 查询文本
            k: 返回结果数量

        Returns:
            相似文档列表
        """
        if not self.vectorstore:
            raise ValueError("请先构建或加载索引")

        return self.vectorstore.similarity_search(query, k=k)