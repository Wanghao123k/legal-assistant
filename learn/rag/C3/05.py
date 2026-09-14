from dotenv import load_dotenv
from llama_index.core.node_parser.text import sentence

load_dotenv("../../.env")


import os
from pathlib import Path

from llama_index.core.node_parser import SentenceWindowNodeParser, SentenceSplitter
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.deepseek import DeepSeek
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.postprocessor import MetadataReplacementPostProcessor




Settings.llm = DeepSeek(model="deepseek-v4-flash", temperature=0.1, api_key=os.getenv("DEEPSEEK_API_KEY"))
Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-small-en",
    cache_folder=str(Path(__file__).resolve().parents[2] / "huggingface"),
    device="cpu",
    normalize=True,
)


# 加载文档
documents = SimpleDirectoryReader(
    input_files=["./pdf/IPCC_AR6_WGII_Chapter03.pdf"]
).load_data()


# 创建节点与构建索引
# 句子窗口索引
node_parser = SentenceWindowNodeParser.from_defaults(
    window_size=3,
    window_metadata_key="window",
    original_text_metadata_key="original_text",
)
sentence_nodes = node_parser.get_nodes_from_documents(documents)
sentence_index = VectorStoreIndex(sentence_nodes)

print(sentence_index)