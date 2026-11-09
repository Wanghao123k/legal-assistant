import re
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()


import logging
from typing import List
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader

logger = logging.getLogger(__name__)
NUMBER = r"[零〇一二三四五六七八九十百千万两0-9０-９]+"
SPACE = r"[ \t\u3000]*"  # 水平空白，不包含换行
# 按法律条文分块，换行和 PDF 分页符均可作为标题边界
BOUNDARY_PATTERN = re.compile(
    rf"(?:^|\f){SPACE}(?:"
    # 法条标题，同时支持“第十条之一”
    rf"(?P<article>第{SPACE}{NUMBER}{SPACE}条"
    rf"(?:{SPACE}之{SPACE}{NUMBER})?)"
    # 编、章、节也作为边界，避免其标题混入上一条
    rf"|第{SPACE}{NUMBER}{SPACE}[编章节][^\n\f]*"
    rf")",
    re.MULTILINE,
)

class DataPreparationModule:
    """数据准备模块 - 负责数据加载， 清洗和预处理"""
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.raw_documents: List[Document] = []
        self.chunks: List[Document] = []


    def load_pdfs(self) -> List[Document]:
        """加载PDF文件"""
        logger.info("Loading PDFs...")

        documents = []
        data_path_obj = Path(self.data_path)
        for pdf_file in data_path_obj.rglob("*.pdf"):
            try:
                # 直接读取文件内容，保持
                doc = PyPDFLoader(pdf_file, mode="single").load()
                documents.append(doc[0])
            except Exception as e:
                logger.warning(f"读取文件 {pdf_file} 失败: {e}")
        self.raw_documents = documents
        return documents

    def chunk_pdf_documents(self) -> List[Document]:
        """
        pdf 分块
        """
        logger.info("Chunking PDFs...")

        if not self.raw_documents:
            raise ValueError("请先加载PDF法律文件")

        chunks = []
        for raw_document in self.raw_documents:
            text = raw_document.page_content.replace("\r\n", "\n").replace("\r", "\n")

            boundaries = list(BOUNDARY_PATTERN.finditer(text))

            if not any(m.group("article") for m in boundaries):
                raise ValueError("未找到条号，请检查提取文本的格式或是否需要 OCR")

            for i, match in enumerate(boundaries):
                article = match.group("article")

                # 编、章、节只作为边界，不单独生成法条块
                if article is None:
                    continue

                end = (
                    boundaries[i + 1].start()
                    if i + 1 < len(boundaries)
                    else len(text)
                )
                chunks.append(
                    Document(
                        page_content=text[match.start():end].strip(),
                        metadata={
                            # "source": pdf_path,
                            # "law_name": law_name,
                            "article": re.sub(r"[ \t\u3000]+", "", article),
                        },
                    )
                )
        self.chunks = chunks
        return chunks
