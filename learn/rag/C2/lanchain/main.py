from dotenv import load_dotenv
from langchain.text_splitter import CharacterTextSplitter, RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_experimental.text_splitter import SemanticChunker
from pathlib import Path

# from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
script_path = Path(__file__).resolve()
env_path = script_path.parents[3] / ".env"
load_dotenv(env_path)

loader = TextLoader(script_path.parent.parent / "txt" / "蜂医.txt", encoding="utf-8")
docs = loader.load()

def print_chunks(chunks):
    print(f"文本被切分为 {len(chunks)} 个块。\n")
    print("--- 前5个块内容示例 ---")
    for i, chunk in enumerate(chunks[:5]):
        print("=" * 60)
        # chunk 是一个 Document 对象，需要访问它的 .page_content 属性来获取文本
        print(f'块 {i + 1} (长度: {len(chunk.page_content)}): "{chunk.page_content}"')
print(docs)

"""固定块大小分块"""
text_splitter = CharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=10,
)

print("+++++++++++++++++++++++++++++固定块分块++++++++++++++++++++++++++++++++++++++")
print_chunks(text_splitter.split_documents(docs))



"""递归字符分块"""
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=10,
    separators=["\n\n", "\n", "。", "，", " ", ""],  # 分隔符优先级
)

# # 针对代码文档的优化分隔符
# splitter = RecursiveCharacterTextSplitter.from_language(
#     language=Language.PYTHON,  # 支持Python、Java、C++等
#     chunk_size=500,
#     chunk_overlap=50
# )
print("+++++++++++++++++++++++++++++递归字符分块++++++++++++++++++++++++++++++++++++++")
print_chunks(text_splitter.split_documents(docs))


"""语义分块"""
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-zh-v1.5",
    cache_folder=r"../../../huggingface",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)
"""
percentile -- 百分位断点识别方法
standard_deviation  -- 标准差法
interquartile  -- 四分位距法
gradient  -- 梯度法
"""
text_splitter = SemanticChunker(
    embeddings=embeddings,
    breakpoint_threshold_type="percentile" # 断点识别方法
)
print("+++++++++++++++++++++++++++++语义分块++++++++++++++++++++++++++++++++++++++")
print_chunks(text_splitter.split_documents(docs))