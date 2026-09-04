"""从完整《民法典》PDF 构建 BM25 与 Chroma 向量索引。

运行方式：uv run python -m knowledge.indexing.build
数据流：PDF -> LegalChunk -> BM25 / Embedding -> Chroma。
"""

import argparse
import json
from pathlib import Path

from knowledge.indexing import BM25Store, EmbeddingService, VectorStore
from knowledge.ingestion import extract_civil_code

# build.py 位于“项目根目录/knowledge/indexing/”下，因此向上两级就是项目根目录。
# 后续所有相对路径都以这里为基准，不再依赖程序启动时的当前工作目录。
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def project_path(path: Path) -> Path:
    """把用户传入的相对路径解析为相对于项目根目录的绝对路径。"""
    return path if path.is_absolute() else PROJECT_ROOT / path


def build_indexes(pdf_path: Path, output_dir: Path, skip_vectors: bool = False) -> None:
    """一次性构建运行 RAG 所需的全部离线索引。"""
    # 即使调用者从其他目录启动程序，也固定读取本项目内的 data 目录。
    pdf_path = project_path(pdf_path)
    output_dir = project_path(output_dir)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"没有找到民法典 PDF：{pdf_path}")

    # 第一步：严格按“条”抽取完整民法典，共应得到 1260 个 chunk。
    chunks = extract_civil_code(pdf_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存标准化数据，便于人工检查，也方便未来重建其他类型的索引。
    chunks_path = output_dir / "civil_code_chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8", newline="\n") as stream:
        for chunk in chunks:
            stream.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")

    # 第二步：建立关键词索引。BM25 不使用 Embedding，适合条号和术语查询。
    bm25 = BM25Store()
    bm25.build(chunks)
    bm25.save(output_dir / "bm25_index.json")

    if not skip_vectors:
        # 第三步：使用同一个 Embedding 模型把法条转为向量并写入 Chroma。
        # 分批写入的好处是中途失败后重新执行时 upsert 不会产生重复数据。
        embedding = EmbeddingService()
        vector_store = VectorStore(output_dir / "chroma")
        batch_size = embedding.batch_size
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            vectors = embedding.embed_documents(
                [chunk.retrieval_text for chunk in batch]
            )
            vector_store.upsert(batch, vectors)
            print(f"向量入库：{min(start + len(batch), len(chunks))}/{len(chunks)}")

    print(f"成功处理 {len(chunks)} 条法条")
    print(f"BM25 索引：{output_dir / 'bm25_index.json'}")
    print("Chroma 向量库：" + (
        str(output_dir / "chroma") if not skip_vectors else "已跳过"
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description="构建完整民法典 RAG 索引")
    # 这里写项目相对路径；build_indexes 会将它拼接到 PROJECT_ROOT。
    parser.add_argument("--pdf", type=Path, default=Path("data/民法典.pdf"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/indexes")
    )
    parser.add_argument("--skip-vectors", action="store_true")
    args = parser.parse_args()
    build_indexes(args.pdf, args.output, args.skip_vectors)


if __name__ == "__main__":
    main()
