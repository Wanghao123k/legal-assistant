import logging
from typing import List

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

load_dotenv()

logger = logging.getLogger(__name__)

from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings

class IndexConstructionModule:
    """索引构建模块 - 负责向量化和索引构建"""
    def __init__(
        self,
        model_name: str = "BAAI/bge-base-zh-v1.5",
        index_save_path: str = "./vector_index",
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
            cache_folder=str(Path(__file__).resolve().parents[0] / "huggingface"),
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

from rag.data_preparation import DataPreparationModule
from config import DEFAULT_CONFIG
index = IndexConstructionModule(index_save_path=DEFAULT_CONFIG.index_save_path)
data = DataPreparationModule(data_path=DEFAULT_CONFIG.data_path)

data.load_pdfs()
for data_i in data.chunk_pdf_documents():
    print(data_i)
    print("=========")


index.build_vector_index(chunks=data.chunks)
index.save_index()
for index_i in index.similarity_search("第三十七条法规"):
    print(index_i)