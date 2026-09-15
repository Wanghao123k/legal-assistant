from dotenv import load_dotenv

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

# 常规分块索引
base_parser = SentenceSplitter(chunk_size=512)
base_nodes = base_parser.get_nodes_from_documents(documents)
base_index = VectorStoreIndex(base_nodes)

# 构建查询引擎
sentence_query_engine = sentence_index.as_query_engine(
    # 控制检索阶段返回多少个相似节点
    similarity_top_k=2,
    # 后处理器，按顺序执行
    # MetadataReplacementPostProcessor  用元数据里的内容替换节点文本
    # SentenceEmbeddingOptimizer        只保留节点中与查询最相关的句子
    # SimilarityPostprocessor           按相似度阈值过滤掉低分节点
    # SentenceTransformerRerank         用 Cross-Encoder 对节点重新排序
    # LongContextReorder                重新排列节点顺序，缓解“迷失在中间”
    # KeywordNodePostprocessor          按关键词过滤节点
    node_postprocessors=[
        MetadataReplacementPostProcessor(target_metadata_key="window")
    ],
)
base_query_engine = base_index.as_query_engine(similarity_top_k=2)

# 4. 执行查询并对比结果
query = "What are the concerns surrounding the AMOC?"
print(f"查询: {query}\n")

print("--- 句子窗口检索结果 ---")
window_response = sentence_query_engine.query(query)
print(f"回答: {window_response}\n")

print("--- 常规检索结果 ---")
base_response = base_query_engine.query(query)
print(f"回答: {base_response}\n")