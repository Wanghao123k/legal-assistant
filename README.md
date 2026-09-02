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

## 当前状态

- [x] 架构设计完成（`docs/architecture.md`）
- [x] 目录骨架搭建完成（本仓库）
- [ ] 一期开发：混合检索 + 单 agent 问答最小闭环
- [ ] 评测集构建（30 题起步）

## 快速开始

> 待开发阶段补充。一期目标是跑通「混合检索 + 单 agent 问答」最小闭环。
