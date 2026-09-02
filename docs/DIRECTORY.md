# 项目目录说明（Directory Guide）

> 本文档说明 `legal-assistant` 项目的目录结构、每个目录的职责、模块归属与依赖规则。
> 配套文档：[`architecture.md`](architecture.md)（整体架构设计）。

---

## 一、一句话

本项目是**法律助手 Agent**，采用**五层架构**（前端 / 网关 / 推理 / 工具 / 知识）+ 评测与数据支撑，核心技术为 **Agentic RAG + 分层记忆 + MCP 工具 + 知识图谱可视化**。

---

## 二、目录树总览

```
legal-assistant/
├── frontend/                # ① 前端页面层
├── gateway/                 # ② 接入/网关层
├── agent/                   # ③ Agent 推理层（大脑）
│   ├── memory/              #    分层记忆 L0-L3
│   └── prompts/             #    提示词模板
├── mcp_tools/               # ④ 工具层（手，MCP 协议）
├── knowledge/               # ⑤ 知识/数据层（料，RAG 基础设施）
│   ├── ingestion/           #    采集 + 清洗 + 分块
│   ├── indexing/            #    向量 + BM25 + 图谱三索引
│   ├── retrieval/           #    混合检索 + RRF + rerank
│   ├── graph/               #    知识图谱（Neo4j schema + 查询）
│   └── update/              #    增量更新管道（RAG 更新）
├── evaluation/              # 横切：评测集与指标
│   ├── dataset/             #    评测数据（gold 标注）
│   └── metrics/             #    评测指标脚本
├── data/                    # 数据（不提交版本库）
│   ├── raw/                 #    原始数据（官方库下载）
│   └── processed/           #    构建好的知识库/索引产物
├── docs/                    # 项目文档
├── scripts/                 # 辅助脚本（数据下载、评测驱动等）
└── README.md                # 项目总览
```

---

## 三、各目录职责详解

### `frontend/` — ① 前端页面层（脸）
- **职责**：用户交互界面，流式对话展示、引用法条高亮、知识图谱可视化（"可查看"）。
- **技术**：Next.js 16。
- **不做什么**：不直接碰 LLM、不直接碰数据库，一切通过网关。

### `gateway/` — ② 接入/网关层（门）
- **职责**：WebSocket/SSE 流式通道、鉴权、会话管理、多 LLM 路由/容灾。
- **关键文件（规划）**：`ws.py`（流式）、`auth.py`（鉴权+会话）、`llm_router.py`（deepseek/GLM 路由）。
- **定位**：基础设施/横切层，不是业务模块。

### `agent/` — ③ Agent 推理层（大脑）
- **职责**：ReAct 主循环、Agentic RAG 编排、分层记忆装配。
- **关键文件（规划）**：`core.py`（主循环）、`orchestrator.py`（检索编排）、`rewriter.py`（query 改写）、`critic.py`（证据评估）、`generator.py`（生成+引用）。
- **子目录**：
  - `memory/`：分层记忆实现（`working.py` L0 / `episodic.py` L1 / `semantic.py` L2）。
  - `prompts/`：所有提示词模板集中管理。
- **为多 agent 预留**：`orchestrator.py` 将来可拆分为多个子 agent 的调度器。

### `mcp_tools/` — ④ 工具层（手）
- **职责**：通过 MCP 协议暴露工具，供 agent 调用。
- **关键文件（规划）**：`server.py`（MCP 入口）、`legal_search.py`（检索工具，向下调 `knowledge/`）。
- **后续扩展**：`legal_calculator.py`（法律计算器）、`web_law_lookup.py`（联网查最新法规）。
- **规则**：每个工具独立一个文件，可插拔、可复用。

### `knowledge/` — ⑤ 知识/数据层（料，RAG 基础设施）
- **职责**：法律知识库的构建、索引、检索与更新。**这是本项目的灵魂层。**
- **子目录分工**：
  - `ingestion/`：从官方库采集 → 清洗 → 按"条"分块。
  - `indexing/`：构建向量索引 + BM25 索引 + 知识图谱三套索引。
  - `retrieval/`：混合检索 + RRF 融合 + rerank 重排序。
  - `graph/`：Neo4j 图谱 schema 定义 + Local/Global 查询。
  - `update/`：增量更新管道（呼应"RAG 要能更新"）。
- **规则**：换 embedding、改分块、重建图谱都在本层内完成，上层无感。

### `evaluation/` — 横切：评测
- **职责**：评测集构建与指标计算。
- `dataset/`：评测数据（带 gold 法条引用 + 领域/难度/时效标签）。
- `metrics/`：recall@k、引用准确率、幻觉率等指标脚本。

### `data/` — 数据
- `raw/`：从官方库 / LawBench 下载的原始数据。
- `processed/`：分块、索引、图谱等构建产物。
- **注意**：本目录不应提交到版本库（加入 `.gitignore`）。

### `docs/` — 文档
- `architecture.md`：整体架构设计文档。
- `DIRECTORY.md`：本文档。

### `scripts/` — 辅助脚本
- 数据下载、评测驱动、一次性迁移等操作脚本，不属于运行时模块。

---

## 四、依赖方向（重要规则）

```
frontend → gateway → agent → mcp_tools → knowledge
```

- **单向依赖，禁止反向 import**（`knowledge` 不得 import `agent`）。
- `agent` 内部的 `memory/` 自洽，不依赖外层。
- `evaluation/` 和 `scripts/` 独立于运行时，可 import 任意层（只读用途）。

---

## 五、五层映射表

| 层 | 目录 | 记法 | 角色 |
|---|---|---|---|
| ① 前端 | `frontend/` | 脸 | 用户交互 |
| ② 网关 | `gateway/` | 门 | 进出通道 |
| ③ 推理 | `agent/` | 脑 | 编排 + 记忆 |
| ④ 工具 | `mcp_tools/` | 手 | MCP 工具 |
| ⑤ 知识 | `knowledge/` | 料 | RAG 基础设施 |

---

## 六、新增模块时放哪（扩展指南）

| 你想加什么 | 放哪个目录 |
|---|---|
| 一个新工具（如"诉讼时效计算器"） | `mcp_tools/` 下新建一个文件 |
| 一个新的检索方式（如 BM25 → Elasticsearch） | `knowledge/retrieval/` 或 `knowledge/indexing/` |
| 一个新的记忆类型 | `agent/memory/` 下新建文件 |
| 一段提示词 | `agent/prompts/` |
| 一批评测数据 | `evaluation/dataset/` |
| 一个一次性脚本 | `scripts/` |
