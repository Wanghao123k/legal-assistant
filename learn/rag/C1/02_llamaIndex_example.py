import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# 必须在导入 LlamaIndex / Hugging Face 之前设置，模型从国内镜像下载。
# hf-mirror.com 是第三方公益镜像，不是 Hugging Face 官方站点。
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from llama_index.core import Settings, SimpleDirectoryReader, VectorStoreIndex
from llama_index.llms.openai_like import OpenAILike
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# DeepSeek 兼容 OpenAI 协议，但不属于 OpenAI 的模型名称列表。
Settings.llm = OpenAILike(
    model="deepseek-v4-flash",
    temperature=0.7,
    max_tokens=4096,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    api_base="https://api.deepseek.com",
    is_chat_model=True,
    is_function_calling_model=False,
    # 本示例保守使用 32K 上下文预算，并非模型的最大上下文长度。
    context_window=32768,
)

# 首次从国内镜像下载模型，之后复用缓存；向量计算在本机 CPU 上执行。
# 固定到 learn/huggingface，避免 IDE 的工作目录改变缓存位置。
Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-small-zh-v1.5",
    cache_folder=str(Path(__file__).resolve().parents[2] / "huggingface"),
    device="cpu",
    normalize=True,
)

# 读取指定的 Markdown 文件，转换成 LlamaIndex 的 Document 对象列表
docs = SimpleDirectoryReader(input_files=["markdown/easy-rl-chapter1.md"]).load_data()

index = VectorStoreIndex.from_documents(docs)

query_engine = index.as_query_engine()

print(query_engine.get_prompts())

print(query_engine.query("文中举了哪些例子?"))
