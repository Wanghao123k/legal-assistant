# `06_struct_index.py` 代码解读

## 1. 这段代码解决什么问题

这段代码实现了一个面向多工作表 Excel 的两级查询系统：

1. 第一层通过向量检索，从所有工作表的摘要中判断应该查询哪张表。
2. 第二层把用户的原始问题交给该工作表对应的 `PandasQueryEngine`，由它生成 Pandas 表达式并查询真实数据。

需要特别注意：程序没有把 Excel 的每一行都存入向量索引。向量索引中只有每张工作表的文字摘要，真正的电影数据仍保存在各个 `DataFrame` 中。

可以把它理解成“总接待台 + 多个专业部门”：

```text
用户问题
“1994年评分人数最少的电影是哪一部？”
             │
             ▼
┌──────────────────────────────┐
│ 顶层向量检索器                │
│ 只检索每张工作表的文字摘要     │
└──────────────────────────────┘
             │
             │ 找到最匹配的摘要
             ▼
IndexNode(
    index_id="年份_1994",
    text="这个表格包含年份为1994的电影信息……"
)
             │
             │ 使用 index_id 查字典
             ▼
df_query_engines["年份_1994"]
             │
             ▼
┌──────────────────────────────┐
│ 1994 年 DataFrame 对应的       │
│ PandasQueryEngine             │
└──────────────────────────────┘
             │
             │ LLM 生成并执行 Pandas 表达式
             ▼
        查询出“燃情岁月”
             │
             ▼
       外层 LLM 整理最终回答
```

## 2. Excel 的实际组织方式

程序读取：

```python
excel_file = "./excel/movie.xlsx"
xls = pd.ExcelFile(excel_file)
```

`movie.xlsx` 中包含多张按年份划分的工作表，例如：

```text
movie.xlsx
├── 年份_1988
├── 年份_1991
├── 年份_1993
├── 年份_1994
├── 年份_1995
└── ……
```

每张表只保存对应年份的电影，列包括：

```text
编号、电影名称、导演、主演、年份、国家、分类、评分人数
```

因此 Excel 已经按照年份完成物理分组。程序需要解决的是：收到问题后，应该进入哪一张工作表查询。

## 3. 两种模型的职责

### 3.1 DeepSeek 大语言模型

```python
Settings.llm = DeepSeek(
    model="deepseek-v4-flash",
    temperature=0.1,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
)
```

大语言模型主要负责：

- 理解自然语言问题并生成 Pandas 查询表达式；
- 根据查询结果组织最终的自然语言回答。

例如，对于“评分人数最少的电影是哪一部”，模型可能生成：

```python
df.loc[df["评分人数"].idxmin(), "电影名称"]
```

### 3.2 BGE 嵌入模型

```python
Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-small-zh-v1.5",
    cache_folder=str(Path(__file__).resolve().parents[2] / "huggingface"),
    device="cpu",
    normalize=True,
)
```

嵌入模型负责把用户问题和工作表摘要转换成向量，然后计算语义相似度。它只负责检索和匹配，不直接生成答案。

## 4. 循环中建立的两套核心结构

程序首先创建两个容器：

```python
df_query_engines = {}
all_nodes = []
```

然后遍历每一张工作表：

```python
for sheet_name in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name=sheet_name)
```

循环同时建立两套结构。

### 4.1 `all_nodes`：用于选择工作表

每张表都会生成一个摘要节点：

```python
year = sheet_name.replace("年份_", "")
summary = (
    f"这个表格包含了年份为 {year} 的电影信息，"
    "可以用来回答关于这一年电影的具体问题。"
)
node = IndexNode(index_id=sheet_name, text=summary)
all_nodes.append(node)
```

循环结束后，其结构大致如下：

```python
all_nodes = [
    IndexNode(
        index_id="年份_1988",
        text="这个表格包含了年份为 1988 的电影信息……",
    ),
    IndexNode(
        index_id="年份_1991",
        text="这个表格包含了年份为 1991 的电影信息……",
    ),
    IndexNode(
        index_id="年份_1994",
        text="这个表格包含了年份为 1994 的电影信息……",
    ),
]
```

这些节点不保存具体电影数据，只保存用于检索的摘要和指向下一层对象的 ID。

### 4.2 `df_query_engines`：用于查询真实数据

每张表还会创建一个单独的查询引擎：

```python
query_engine = PandasQueryEngine(
    df=df,
    llm=Settings.llm,
    verbose=True,
)

df_query_engines[sheet_name] = query_engine
```

循环结束后，其结构大致如下：

```python
df_query_engines = {
    "年份_1988": PandasQueryEngine(df=df_1988),
    "年份_1991": PandasQueryEngine(df=df_1991),
    "年份_1994": PandasQueryEngine(df=df_1994),
}
```

两套结构的职责对比如下：

| 结构 | 保存的内容 | 主要职责 |
| --- | --- | --- |
| `all_nodes` | 工作表摘要节点 | 判断应该选择哪张表 |
| `df_query_engines` | 各工作表的查询引擎 | 查询对应表中的真实数据 |

## 5. 两套结构如何关联

关联由同一个 `sheet_name` 字符串完成：

```python
node = IndexNode(index_id=sheet_name, text=summary)
df_query_engines[sheet_name] = query_engine
```

假设当前处理的是 `年份_1994`，程序会同时建立：

```python
IndexNode(
    index_id="年份_1994",
    text="这个表格包含了年份为 1994 的电影信息……",
)
```

以及：

```python
df_query_engines["年份_1994"] = query_engine_1994
```

于是形成以下关联：

```text
IndexNode.index_id
        │
        │ 值为 "年份_1994"
        ▼
df_query_engines["年份_1994"]
        │
        ▼
1994 年 DataFrame 的 PandasQueryEngine
```

这很像数据库中的外键关系。`IndexNode` 并没有直接持有 `PandasQueryEngine`，而是通过 `index_id` 去另一个字典中查找。

因此必须满足：

```python
node.index_id == df_query_engines 中的某个键
```

如果节点使用 `index_id="1994"`，而字典键是 `"年份_1994"`，递归检索器就无法找到下一层对象。

## 6. `IndexNode` 为什么重要

`IndexNode` 同时包含两个关键信息：

- `text`：提供给向量索引，用于语义检索；
- `index_id`：告诉递归检索器下一步应该进入哪个对象。

可以把它理解为一张带地址的索引卡：

```text
卡片内容：这里保存的是 1994 年电影
卡片地址：年份_1994
```

普通 `TextNode` 被检索到后，通常直接作为上下文返回；`IndexNode` 被检索到后，递归检索器会沿着它的 `index_id` 继续查询下一层。

## 7. 顶层向量索引

```python
vector_index = VectorStoreIndex(all_nodes)
```

由于传入的是 `all_nodes`，向量索引中只有类似下面的摘要：

```text
这个表格包含了年份为 1988 的电影信息……
这个表格包含了年份为 1991 的电影信息……
这个表格包含了年份为 1994 的电影信息……
```

具体的电影名称、导演和评分人数没有进入这个向量索引。因此它本质上是一个“路由索引”，负责选择数据源，而不是直接保存完整知识。

```python
vector_retriever = vector_index.as_retriever(similarity_top_k=1)
```

`similarity_top_k=1` 表示只返回相似度最高的一个摘要节点，也就是只选择一张工作表。

## 8. `RecursiveRetriever` 的组装方式

```python
recursive_retriever = RecursiveRetriever(
    "vector",
    retriever_dict={"vector": vector_retriever},
    query_engine_dict=df_query_engines,
    verbose=True,
)
```

可以将其内部对象关系理解成：

| 对象 ID | 对应对象 |
| --- | --- |
| `vector` | 顶层向量检索器 |
| `年份_1988` | 1988 年工作表查询引擎 |
| `年份_1991` | 1991 年工作表查询引擎 |
| `年份_1994` | 1994 年工作表查询引擎 |
| …… | …… |

第一个参数 `"vector"` 是根 ID，表示递归查询从这里开始。

```python
retriever_dict={"vector": vector_retriever}
```

表示根 ID 对应顶层向量检索器。

```python
query_engine_dict=df_query_engines
```

表示工作表 ID 对应各自的 `PandasQueryEngine`。

## 9. 一次查询的完整调用链

最终的外层查询引擎由下面的代码创建：

```python
query_engine = RetrieverQueryEngine.from_args(recursive_retriever)
```

执行查询：

```python
query = "1994年评分人数最少的电影是哪一部？"
response = query_engine.query(query)
```

完整过程如下。

### 第一步：外层查询引擎调用递归检索器

`RetrieverQueryEngine` 先让 `RecursiveRetriever` 检索与问题有关的内容。

### 第二步：从根 ID `vector` 开始

递归检索器通过：

```python
retriever_dict["vector"]
```

取得顶层 `vector_retriever`。

### 第三步：从摘要中选择工作表

顶层检索器比较用户问题和所有工作表摘要的向量相似度。理想情况下，问题中的“1994年”会使下面的节点排在第一位：

```python
IndexNode(
    index_id="年份_1994",
    text="这个表格包含了年份为 1994 的电影信息……",
)
```

### 第四步：读取 `IndexNode.index_id`

递归检索器发现结果是 `IndexNode`，便读取：

```python
node.index_id
```

得到：

```text
年份_1994
```

### 第五步：找到 1994 年子查询引擎

递归检索器执行的核心逻辑相当于：

```python
sub_query_engine = query_engine_dict["年份_1994"]
```

这个查询引擎内部绑定的 `df` 只包含 1994 年电影。

### 第六步：传递原始问题

递归检索器会把完整问题继续传给子查询引擎：

```text
1994年评分人数最少的电影是哪一部？
```

### 第七步：生成并执行 Pandas 表达式

`PandasQueryEngine` 会让大语言模型生成类似下面的表达式：

```python
df.loc[df["评分人数"].idxmin(), "电影名称"]
```

其中：

```python
df["评分人数"].idxmin()
```

找到评分人数最小的行索引，然后：

```python
df.loc[行索引, "电影名称"]
```

取出该行的电影名称。

根据当前 Excel 中的实际数据，结果是：

```text
电影名称：燃情岁月
评分人数：176801
```

### 第八步：把子查询结果包装成文本

递归检索器把 Pandas 查询结果包装成普通文本节点，大致类似：

```text
Query: 1994年评分人数最少的电影是哪一部？
Response: 燃情岁月
```

此时已经得到普通文本，不再需要继续沿 `IndexNode` 递归。

### 第九步：生成最终答案

外层 `RetrieverQueryEngine` 再调用大语言模型，根据检索结果组织自然语言回答，例如：

```text
1994年评分人数最少的电影是《燃情岁月》，评分人数为176801。
```

所以一次完整查询通常包括：

1. 一次本地向量检索；
2. 一次 LLM 调用，将自然语言转换为 Pandas 表达式；
3. 一次 Pandas 表达式执行；
4. 一次 LLM 调用，整理最终回答。

## 10. 为什么叫“递归 RAG”

普通 RAG 的过程通常是：

```text
问题 → 检索文本片段 → LLM 回答
```

这段代码的过程是：

```text
问题
  → 检索工作表摘要
  → 摘要节点指向另一个查询引擎
  → 子查询引擎查询 DataFrame
  → 返回结果
  → LLM 回答
```

第一次检索得到的不是最终知识，而是下一层查询入口，这就是这里“递归”的含义。

当前代码只有两层，但同一种模式还可以继续扩展：

```text
业务领域索引
    ↓
年份索引
    ↓
数据库或工作表查询引擎
    ↓
具体记录
```

## 11. 容易产生误解的变量

### 11.1 `query_engine` 被重复用于不同对象

循环内部：

```python
query_engine = PandasQueryEngine(...)
```

它表示单张工作表的子查询引擎。

循环结束后：

```python
query_engine = RetrieverQueryEngine.from_args(...)
```

它又表示整个系统的外层查询引擎。

这不会导致功能错误，因为子查询引擎已经被保存在字典中，但会降低可读性。建议改名为：

```python
sheet_query_engine = PandasQueryEngine(...)
df_query_engines[sheet_name] = sheet_query_engine

final_query_engine = RetrieverQueryEngine.from_args(...)
```

### 11.2 循环中的 `df` 会不断被重新赋值

```python
df = pd.read_excel(...)
```

这也不会导致之前的查询引擎失效。每次创建 `PandasQueryEngine` 时，它都会保存当前 DataFrame 的引用：

```text
engine_1988 → df_1988
engine_1991 → df_1991
engine_1994 → df_1994
```

虽然变量名 `df` 在下一轮循环中指向了新对象，之前的查询引擎仍然持有各自的 DataFrame。

## 12. 当前设计的局限和风险

### 12.1 精确年份不适合完全依赖向量检索

所有摘要几乎相同，主要区别只是年份：

```text
这个表格包含了年份为 1993 的电影信息……
这个表格包含了年份为 1994 的电影信息……
这个表格包含了年份为 1995 的电影信息……
```

嵌入模型对数字的精确区分不一定像字符串匹配那样可靠。对于年份这种明确字段，更稳定的方式是先用正则表达式提取年份，然后直接访问：

```python
df_query_engines[f"年份_{year}"]
```

向量检索更适合含义模糊、不能通过精确字段直接定位的问题。

### 12.2 `similarity_top_k=1` 只能选择一张表

如果用户问：

```text
比较1994年和1995年评分人数最少的电影。
```

当前系统仍然只会选择一个工作表，因此无法完整回答。可以提高 `similarity_top_k`，或者先解析问题中出现的全部年份，再分别调用对应查询引擎。

### 12.3 相对路径依赖启动目录

下面两个路径都是相对于 Python 进程的当前工作目录，而不是相对于代码文件：

```python
load_dotenv("../../.env")
excel_file = "./excel/movie.xlsx"
```

如果从不同目录启动脚本，可能找不到文件。更稳妥的方式是以 `__file__` 为基准：

```python
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(PROJECT_ROOT / ".env")
excel_file = BASE_DIR / "excel" / "movie.xlsx"
```

### 12.4 `PandasQueryEngine` 存在代码执行风险

`PandasQueryEngine` 会执行大语言模型生成的 Pandas/Python 表达式，其内部涉及 `eval`，因此存在执行任意代码的风险。

它适合本地学习和可信环境，不适合直接暴露给不可信的公网用户。生产环境中应使用严格沙箱，或者自行实现只允许筛选、排序、聚合等有限操作的查询层。

### 12.5 未使用的导入

```python
from networkx.algorithms import similarity
```

该导入在代码中没有使用，可以删除。它与下面的参数没有关系：

```python
similarity_top_k=1
```

后者是 LlamaIndex 检索器自己的参数。

## 13. 一句话概括整个程序

整段程序可以简化成下面的伪代码：

```python
# 初始化阶段
for 每张工作表:
    创建该工作表的 Pandas 查询引擎
    创建带有工作表名称的摘要节点

# 查询阶段
摘要节点 = 向量检索最相关的工作表简介
工作表名称 = 摘要节点.index_id
子查询引擎 = df_query_engines[工作表名称]
表格结果 = 子查询引擎.query(原始问题)
最终回答 = LLM整理(表格结果)
```

最关键的关联是：

```python
IndexNode(index_id=sheet_name)
```

对应：

```python
df_query_engines[sheet_name]
```

`index_id` 是路标，字典中的 `PandasQueryEngine` 是被路由到的真正目的地。
