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

## Docker 部署（当前聊天功能）

前后端共用根目录的一个 `Dockerfile`，构建为一个镜像、运行一个容器。后端同时提供首页 `/` 和聊天接口 `/api/chat`，无需单独启动前端。

1. 在项目根目录复制 `.env.example` 为 `.env`（已有则直接编辑），填写 `LLM_API_KEY`，按需设置 `LLM_BASE_URL` 和 `LLM_MODEL`。未设置模型时沿用 `config.py` 中的默认值；请确认模型名称在你的服务商账户中可用。
2. 启动 Docker（Windows 使用 Docker Desktop 的 Linux containers 模式），在项目根目录执行：

```sh
docker build -t legal-assistant:latest .
docker run -d --name legal-assistant --restart unless-stopped --env-file .env -p 8000:8000 legal-assistant:latest
```

本机访问 <http://localhost:8000>；服务器部署后访问 `http://服务器IP:8000`，并放行服务器的 TCP 8000 端口。宿主机端口可调整，例如 `-p 8080:8000`，此时访问 8080。

查看日志、健康状态和停止服务：

```sh
docker logs -f legal-assistant
docker inspect --format='{{.State.Health.Status}}' legal-assistant
docker stop legal-assistant
```

更新代码后重新构建镜像，再删除旧容器并按上面的 `docker run` 命令启动。修改 `.env` 后也需要重新创建容器，`docker restart` 不会重新读取 `--env-file`：

```sh
docker build -t legal-assistant:latest .
docker rm -f legal-assistant
docker run -d --name legal-assistant --restart unless-stopped --env-file .env -p 8000:8000 legal-assistant:latest
```

镜像只包含当前聊天功能需要的代码和 Python 依赖，不安装 RAG、训练或本地模型依赖。`.dockerignore` 排除密钥、本地虚拟环境、Git 历史及数据文件；`.env` 仅在启动容器时传入。健康检查访问首页，不调用模型；对话仅保存在当前浏览器页面中。

容器默认以普通用户运行，监听 `0.0.0.0:8000`。直接本地运行 `uv run python -m backend.main` 时仍默认监听 `127.0.0.1:8000`；可通过 `HOST`、`PORT` 环境变量覆盖。

现有 `docker-compose.yml` 用于独立的 Milvus 组件，当前聊天服务不依赖它，执行以上命令即可部署。
