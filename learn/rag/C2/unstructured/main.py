"""使用 Unstructured 官方 Partition API 按语义相似度分块。"""

import os
from pathlib import Path

from dotenv import load_dotenv
from unstructured_client import UnstructuredClient
from unstructured_client.models import operations, shared


def main():
    script_path = Path(__file__).resolve()
    env_path = script_path.parents[3] / ".env"
    load_dotenv(env_path)

    api_key = os.getenv("UNSTRUCTURED_API_KEY")
    if not api_key:
        raise ValueError(f"请在环境变量或 {env_path} 中配置 UNSTRUCTURED_API_KEY")

    pdf_path = script_path.parent.parent / "pdf" / "rag.pdf"
    client = UnstructuredClient(api_key_auth=api_key)

    # 服务端完成 PDF 分区和语义分块，无需先在本地调用 partition。
    with pdf_path.open("rb") as pdf_file:
        request = operations.PartitionRequest(
            partition_parameters=shared.PartitionParameters(
                files=shared.Files(content=pdf_file.read(), file_name=pdf_path.name),
                strategy=shared.Strategy.AUTO,
                languages=["chi_sim", "eng"],
                chunking_strategy="by_similarity",
                similarity_threshold=0.5,
                max_characters=1000,
                # 整份 PDF 一次提交，避免客户端分批分页造成分块边界。
                split_pdf_page=False,
            )
        )
        response = client.general.partition(request=request)

    chunks = response.elements or []
    print(f"分块数量：{len(chunks)}")
    for i, chunk in enumerate(chunks, start=1):
        text = chunk.get("text", "")
        print(f"\n--- 第 {i} 块 | {chunk.get('type', '')} | {len(text)} 字符 ---")
        print(text)


if __name__ == "__main__":
    main()
