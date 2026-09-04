# 最小 RAG 代码阅读指南

## 一次构建，反复查询

索引构建是离线流程，不应在每次用户提问时重新执行：

```text
data/民法典.pdf
  -> knowledge/ingestion/civil_code_pdf.py：抽取 1260 个 LegalChunk
  -> knowledge/indexing/bm25_store.py：分词并构建 BM25
  -> knowledge/indexing/embeddings.py：法条文字转向量
  -> knowledge/indexing/vector_store.py：向量写入 Chroma
```

运行命令：

```powershell
uv run python -m knowledge.indexing.build
```

## 每次提问

```text
用户问题
  -> HybridRetriever
      -> BM25Store.search：按关键词检索
      -> EmbeddingService.embed_query：问题转向量
      -> VectorStore.search：到 Chroma 做余弦检索
      -> reciprocal_rank_fusion：融合两路排名
  -> AnswerGenerator：法条作为证据交给大模型
  -> 引用白名单校验
  -> 返回回答
```

运行命令：

```powershell
uv run python main.py
```

## 为什么保留两种索引

- BM25 擅长“第 1064 条”“夫妻共同债务”等精确词语。
- Chroma 向量检索擅长“老公在外面欠的钱我要还吗”等口语语义。
- RRF 只融合排名，不直接比较两种不同量纲的分数。

## 重要文件

- `knowledge/models.py`：所有层共用的数据结构。
- `knowledge/ingestion/civil_code_pdf.py`：PDF 到法条。
- `knowledge/indexing/build.py`：离线索引构建总入口。
- `knowledge/retrieval/hybrid.py`：在线检索入口。
- `agent/orchestrator.py`：检索和生成的编排入口。
- `main.py`：供学习和调试的命令行界面。

## 生成文件

```text
data/processed/indexes/
├── civil_code_chunks.jsonl  # 清洗后的完整法条
├── bm25_index.json          # 关键词索引
└── chroma/                  # Chroma 持久化向量数据库
```

`chroma/` 是数据库文件，不要手工编辑。更换 Embedding 模型后应重新构建
整个向量库，因为不同模型产生的向量不能混合比较。
