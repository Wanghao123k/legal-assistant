# 法律助手（Legal Assistant）

> 面向**普通老百姓**的中文法律问答 Agent，基于 Agentic RAG + 知识图谱 + 分层记忆，答案强制引用溯源。

## 项目定位

| 维度 | 说明 |
|---|---|
| 目标用户 | 普通老百姓 |
| 任务 | 一期：法律问答 + 法规/案例检索归纳；二期：合同审查 |
| 法域 | 仅中国大陆现行有效法 |
| 核心能力 | Agentic RAG、混合检索（向量+BM25+图谱）、分层记忆 L0–L3 |
| 模型 | deepseek-v4-pro（主）、GLM-5.3（备）、flash（轻任务） |

## 技术栈

- **前端**：Next.js 16
- **网关**：FastAPI + WebSocket/SSE
- **Agent**：轻自研 ReAct 循环（基于《深入理解 AI Agent》）
- **工具**：MCP 协议（Python `mcp` SDK）
- **关系数据库**：SQLite（SQLAlchemy ORM 抽象，可无缝切 PostgreSQL）
- **向量数据库**：Chroma（本地嵌入式，经 `VectorStore` 接口隔离，可切 pgvector/Qdrant）
- **检索**：混合检索（向量 + BM25）+ LLM rerank
- **知识图谱**：Neo4j（自带可视化）
- **Embedding**：智谱 embedding-3
- **记忆**：分层记忆 L0–L3（mem0 思路 / 自建）
- **包管理**：uv

## 环境变量

复制 `.env.example` 为 `.env` 并填入真实值（详见该文件的注释）。

## 文档导航

| 文档 | 内容 |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | 整体架构设计（五层架构 + Agentic RAG + 技术选型 + 路线图） |
| [`docs/DIRECTORY.md`](docs/DIRECTORY.md) | 目录说明（每个目录的职责与依赖规则） |
| [`docs/RAG_CODE_GUIDE.md`](docs/RAG_CODE_GUIDE.md) | 最小 RAG 的代码调用链与阅读顺序 |

## 当前状态

- [x] 架构设计完成（`docs/architecture.md`）
- [x] 目录骨架搭建完成（本仓库）
- [ ] 一期开发：混合检索 + 单 agent 问答最小闭环
- [ ] 评测集构建（30 题起步）

## 快速开始

安装依赖：

```powershell
uv sync
```

从完整《民法典》PDF 抽取 1260 条法条，并构建 BM25 与向量索引：

```powershell
uv run python -m knowledge.indexing.build
```

如果 Embedding API 暂时不可用，可以先构建 BM25：

```powershell
uv run python -m knowledge.indexing.build --skip-vectors
```

启动最小 RAG 命令行：

```powershell
uv run python main.py
```

程序会自动检测 `data/processed/indexes/chroma/`。存在且包含数据时使用
BM25 + 向量 + RRF 混合检索；不存在时使用 BM25 检索。
