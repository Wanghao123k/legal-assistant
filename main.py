"""完整民法典最小 RAG 命令行入口。"""

from agent import LegalRAG


def main() -> None:
    rag = LegalRAG()
    print("民法典最小 RAG（输入 q 退出）")
    while True:
        try:
            question = input("\n问题 > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in {"q", "quit", "exit"}:
            break
        if not question:
            continue

        answer, results = rag.answer(question)
        print("\n检索结果：")
        for result in results:
            print(
                f"- {result.chunk.article_label} {result.chunk.article_title} "
                f"[{'+'.join(result.retrieval_sources)}]"
            )
        print(f"\n回答：\n{answer}")


if __name__ == "__main__":
    main()
