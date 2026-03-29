# 论文检索 Agent 架构计划

更新日期：2026-03-29

这份计划文档面向你的当前目标：

- 构建一个可复用的论文检索 agent
- 同时支持两种筛选路径
  - 路径 A：向量化快速筛选 / 召回
  - 路径 B：LLM 基于标题、摘要和更多元数据做逐篇判断
- 后续最好能以 API 或 Docker 服务方式供其他项目调用

本文会结合你当前已经调研的数据源文档，给出推荐的系统设计，而不是只讨论某一个接口怎么调。

## 1. 先给结论

如果你的目标是做一个可长期演进、可部署、可复用的论文检索服务，推荐采用：

`统一查询规划 + 多数据源 connector + 标准化去重 + 双阶段重排 + 可配置输出`

不建议直接把“用户意图拆成一堆关键词，然后全部 function call 并发打到所有数据库”作为主方案。

更不建议把“每个数据库做成一个 skill”当成运行时主架构。

更好的方案是：

1. 先把用户问题解析成一个统一的 `SearchIntent`
2. 再由各数据库 connector 把 `SearchIntent` 编译成各自的查询参数
3. 先做广召回
4. 对召回结果统一标准化、去重、补齐 metadata
5. 先用 embedding 做快速筛选
6. 再只对 Top-N 候选调用 LLM 做逐篇判断
7. 输出结果时保留“命中原因”和“证据字段”

这样做的好处是：

- 对外只有一个统一 API，不会把上层业务绑死在某个数据库语法上
- 后续增加 OpenAlex、Semantic Scholar、CORE、arXiv、万方、IEEE 等数据源时，改动集中在 connector 层
- LLM 成本可控，因为它只处理 Top-N 候选，而不是全量召回结果
- 可以同时支持“极速模式”和“高精度模式”

## 2. 推荐的数据源角色分层

基于你当前 docs 中各接口能力，建议把数据源分成四层，而不是平铺使用。

### 2.1 主召回层

优先作为第一阶段召回源：

- OpenAlex
- Semantic Scholar
- CORE
- arXiv

原因：

- 都能做论文元数据检索
- 能较稳定返回标题、摘要、作者、年份、DOI 等基础字段
- 比较适合作为通用论文搜索的基础数据面

建议分工：

- OpenAlex：通用 works 检索、过滤、beta 语义检索、OA 与 citation 维度较好
- Semantic Scholar：相关性搜索、bulk 检索、snippet、推荐链路较强
- CORE：OA/仓储覆盖补充，适合补全文链接和更多来源记录
- arXiv：预印本强覆盖，但要单独限流处理

### 2.2 精准增强层

用于特定来源增强，不一定参与所有请求：

- IEEE Xplore
- 万方

原因：

- 字段能力强，但通常有鉴权、使用条款、配额、语料边界或部署复杂度
- 更适合在用户显式要求“限定来源”或“需要特定库权威结果”时启用

### 2.3 解析与全文入口层

不作为主召回，而是作为 enrich / resolve：

- Unpaywall
- CORE discover

适合承担：

- DOI -> OA 状态
- DOI -> PDF / landing page
- 全文可得性判断

### 2.4 受限接入层

- CNKI

建议：

- 当前先不要把 CNKI 放进自动化生产主链路
- 可以在架构里预留 connector interface
- 待拿到明确授权、API 文档和合规边界后再接

## 3. 不推荐的设计方式

### 3.1 不推荐“把用户问题拆成所有关键词后全部并发下发”

例如把：

`找近五年用于医学影像分割的小样本学习论文，优先综述和开放获取`

拆成：

- 医学影像
- 分割
- 小样本学习
- 综述
- 开放获取
- 近五年

然后把这些词做所有排列组合，再对所有数据库并发搜索。

这个方案的问题是：

- 查询爆炸，成本和延迟都失控
- 高噪声，容易召回只命中单个词的弱相关论文
- 很难保持数据库间结果一致性
- 后续难做调试，不知道哪种拆词策略真的有效

### 3.2 不推荐把“每个数据库”做成 runtime skill

如果你的目标是生产 API / Docker 服务，运行时核心抽象不应该是 skill，而应该是：

- `connector`
- `retriever`
- `reranker`
- `resolver`
- `planner`

skill 更适合：

- 开发期辅助工作流
- 内部 prompt 封装
- 某些手工调研或半自动流程

不适合作为长期稳定的服务端运行时协议。

## 4. 推荐的核心抽象

推荐把系统内部统一成下面几个对象。

### 4.1 SearchIntent

用户问题先被解析成统一意图，而不是直接生成某个数据库专属查询语法。

建议字段：

```json
{
  "user_query": "找近五年用于医学影像分割的小样本学习论文，优先综述和开放获取",
  "topic": "few-shot learning for medical image segmentation",
  "must_terms": ["few-shot learning", "medical image segmentation"],
  "should_terms": ["review", "survey"],
  "exclude_terms": [],
  "filters": {
    "year_from": 2021,
    "year_to": 2026,
    "is_oa": true,
    "publication_types": ["review", "survey", "article"],
    "language": ["en", "zh"]
  },
  "source_preferences": {
    "preferred_sources": [],
    "required_sources": [],
    "excluded_sources": []
  },
  "retrieval_mode": "quick",
  "answer_mode": "precise"
}
```

### 4.2 CanonicalPaper

所有数据库返回结果都先映射到统一论文结构。

建议字段：

```json
{
  "paper_id": "internal_uuid",
  "source": "openalex",
  "source_id": "W123456",
  "title": "",
  "abstract": "",
  "authors": [],
  "year": 2024,
  "venue": "",
  "doi": "",
  "url": "",
  "pdf_url": "",
  "is_oa": true,
  "citations": 0,
  "keywords": [],
  "fields_of_study": [],
  "language": "",
  "publication_type": "",
  "snippet": "",
  "raw": {}
}
```

### 4.3 JudgmentRecord

无论是向量筛选还是 LLM 判断，都把结果收敛成统一评分结构。

```json
{
  "paper_id": "internal_uuid",
  "vector_score": 0.83,
  "keyword_score": 0.62,
  "llm_relevance": 0.91,
  "llm_decision": "keep",
  "reasons": [
    "主题明确匹配 few-shot medical image segmentation",
    "文献类型接近 review/survey",
    "摘要中出现方法和应用场景"
  ],
  "evidence": {
    "matched_terms": ["few-shot", "segmentation"],
    "fields_used": ["title", "abstract", "keywords"]
  }
}
```

## 5. 推荐的整体检索流程

建议改成：

`共享 Query Planning 层 + 独立 Quick Search / Deep Search 检索层 + 可选 Fusion 总通道`

也就是说，两种检索方式面向用户时是两套独立方案，不再默认串联；但它们共享同一个查询理解层和 connector 层。

### 5.1 共享层：Query Planning

输入：用户自然语言问题

输出：`SearchIntent`

这里可以使用 LLM，但 LLM 的职责仍然是“解析与约束抽取”，不是直接控制所有下游接口。

LLM 在这一层主要完成：

- 识别主题
- 抽取硬约束
- 抽取软偏好
- 判断是否需要中文库、英文库、OA 优先、近年优先、高被引优先
- 生成少量 query rewrite

建议只生成 `1~3` 个查询变体：

- `broad_query`
- `precise_query`
- `synonym_query`

而不是无限拆词。

### 5.2 共享层：Source Planning + Query Compilation

由 `Retrieval Orchestrator` 按策略调度多个 connector。

建议策略：

- 默认只启用主召回层
  - OpenAlex
  - Semantic Scholar
  - CORE
  - arXiv
- 用户指定来源时，再启用 IEEE / 万方
- 对高成本源设置 budget
  - 最大页数
  - 最大候选数
  - 最大超时时间

每个 connector 接受统一输入：

```python
search(intent: SearchIntent, query_variant: str, limit: int) -> list[CanonicalPaper]
```

每个 connector 内部负责：

- 把统一意图编译成源特定查询语法
- 控制分页
- 控制速率
- 返回统一结构

### 5.3 通道 A：Quick Search

这是面向用户的“快速检索”方案，目标是：

- 延迟低
- 成本低
- 结果足够相关
- 适合探索式搜索

流程建议：

1. 执行多源召回
2. 统一标准化与去重
3. 进行向量 + 关键词混合重排
4. 直接返回 Top-K 结果
5. 按需补充 OA / PDF 链接

Quick Search 的核心不是“只做向量”，而是“以向量检索为主、规则和关键词为辅”的快速排序通道。

建议做法：

- 对 `title + abstract + keywords + venue` 生成文档 embedding
- 对用户 query 或 `SearchIntent.topic` 生成 query embedding
- 做余弦相似度检索或向量重排

推荐不要只依赖向量分数，而是做混合分：

`quick_score = a * vector_score + b * keyword_score + c * source_prior + d * citation_prior + e * recency_prior`

这样可以避免：

- 纯 embedding 把主题相关但任务不匹配的论文排太前
- 纯关键词把同义表达漏掉

这个通道的目标通常是把候选集从例如 `200~500` 缩到 `20~50`，并直接向用户展示。

### 5.4 通道 B：Deep Search

这是面向用户的“高精度检索”方案，目标是：

- 判断论文是否真正满足用户问题
- 更好处理复杂约束
- 给出更强的命中理由和排除理由

流程建议：

1. 执行多源召回
2. 统一标准化与去重
3. 先执行硬规则过滤
4. 对候选论文逐篇执行 `LLM Precision Judge`
5. 根据 judgment 结果排序和返回
6. 对保留结果做增强补齐

这里不要求必须经过 Quick Search 的 Top-N 结果；Deep Search 可以直接基于共享召回层拿到候选集合后单独判断。

只对候选集中的可疑或较优结果调用，建议：

- 默认候选判断上限 `N = 30`
- 高精度模式可到 `50`
- 对明显不满足硬约束的记录直接跳过

输入建议：

- 用户原问题
- 结构化 `SearchIntent`
- 论文标题
- 摘要
- 关键词
- 年份
- venue
- citation count
- source

输出不要只要 yes/no，建议输出结构化 judgment：

```json
{
  "decision": "keep",
  "relevance": 0.92,
  "confidence": 0.85,
  "reason": "论文聚焦 few-shot 医学图像分割，并在摘要中明确给出任务场景和方法框架",
  "missing_constraints": [],
  "hard_constraint_failed": false
}
```

建议加入一个硬规则过滤器，先于 LLM 执行：

- 年份不满足
- 指定语言不满足
- 必须 OA 但无 OA
- 必须 review 但 publication type 明显不匹配

这样可以减少不必要的 LLM 调用。

### 5.5 通道 C：Fusion 总通道

这是额外设计的一条总通道，用于：

- 同时运行 Quick Search 和 Deep Search
- 对两路结果做统一召回、去重、融合
- 适合结果质量优先的场景

推荐流程：

1. 共享 Query Planning
2. 向共享 connector 层下发召回任务
3. Quick Search 产出 `quick_results`
4. Deep Search 产出 `deep_results`
5. 对两路结果做去重合并
6. 生成统一的 `fusion_score`
7. 返回融合后的结果

融合时建议保留来源标记：

- `hit_by_quick`
- `hit_by_deep`
- `quick_score`
- `deep_score`
- `fusion_score`

推荐融合逻辑：

- 两路都命中：优先级最高
- 仅 Deep 命中：高精度补充项
- 仅 Quick 命中：探索性补充项

### 5.6 共享层：Normalize + Deduplicate

无论是 Quick、Deep 还是 Fusion，都必须做统一归一化和去重。

建议去重优先级：

1. DOI 精确去重
2. arXiv ID / PMID / Semantic Scholar Paper ID 等外部 ID 映射
3. 标题标准化后近似匹配
4. `title + year + first_author` 联合近似匹配

合并时保留多源信息：

- 最优标题
- 最长摘要
- 最可信年份
- 所有来源 URL
- OA / PDF 链接
- 引文数最大值或来源加权值

### 5.7 共享层：Enrichment + Answer Assembly

对最终保留的论文做增强补齐：

- Unpaywall：补 OA / PDF / landing page
- CORE discover：补 full text link
- Semantic Scholar：补 snippet / citation / recommendation
- OpenAlex：补 concepts / related metadata

最终不要只返回“论文列表”，而要返回：

- 命中论文
- 通道来源
- 排名分数
- 命中原因
- 关键元数据
- 可访问链接
- 如果需要，还可以附带“为什么没选入”的排除原因

这会让 agent 可解释性明显更好。

## 6. 关于“意图分解”的推荐方案

你的问题核心之一是：

`用户提问后利用 llm 意图分解，是将意图关键词之间分解做一个 function call 全部查询下发，还是为每个数据库设计一个 skills 或是单独的 function 调用？`

我的推荐答案是：

`都不要直接这么做，应该做“统一意图对象 + 源特定 connector 编译”`

### 6.1 推荐结构

外层只有一个检索入口：

```text
search_papers(query, options)
```

内部流程：

1. `plan_query(query) -> SearchIntent`
2. `select_sources(intent) -> SourcePlan`
3. `compile_query(intent, source) -> SourceQuery`
4. `run_connector(source_query) -> papers`
5. `route_by_mode(mode)`
6. `run_quick_search(...) | run_deep_search(...) | run_fusion_search(...)`

### 6.2 为什么不建议“把所有关键词拆成 function call”

因为真实效果通常会遇到这些问题：

- 召回量太大，噪声多
- 不同数据库语法差异太大，很难统一
- 很多关键词是约束，不是主题
- 用户问题中的“优先、最好、近五年、综述、开放获取”不应该和主题词同等拆分

### 6.3 正确的意图分解方向

应该把 query 分成四类信息：

- 主题语义
- 硬过滤条件
- 软偏好
- 输出要求

例如：

`找近五年关于 RAG 在医学问答上的综述，优先开放获取`

应拆成：

- 主题：RAG for medical question answering
- 硬过滤：近五年
- 软偏好：review/survey、open access
- 输出偏好：高相关优先

而不是拆成五六个孤立关键词去穷举搜索。

## 7. 关于“skills”与“functions”的建议

### 7.1 生产系统推荐

生产系统里建议：

- 每个数据库是一个 `connector`
- 每个 connector 暴露统一函数接口
- 所有 connector 由一个 `orchestrator` 调度

也就是：

```text
OpenAlexConnector.search(...)
SemanticScholarConnector.search(...)
CoreConnector.search(...)
ArxivConnector.search(...)
WanfangConnector.search(...)
```

### 7.2 什么时候可以用 skill

如果你在某个 agent 框架里需要：

- 给不同数据源配置不同 prompt
- 给不同场景配置不同工作流
- 做半自动研究助手

那么 skill 可以作为“上层能力封装”存在。

但它不应取代服务端 connector。

### 7.3 最佳实践

建议分两层：

- 服务端运行时：`connector + planner + reranker + resolver`
- agent 编排层：可选地封装成 tools / skills

这样你未来无论接 LangGraph、AutoGen、OpenAI tool calling、还是自己写 API，都不会被绑定死。

## 8. 推荐的系统模块划分

如果你准备做成一个可复用服务，建议拆成下面这些模块。

### 8.1 API Gateway

负责：

- 接收请求
- 鉴权
- 参数校验
- 同步 / 异步任务分发

建议技术：

- FastAPI

### 8.2 Query Planner

负责：

- 用户 query 解析
- 生成 `SearchIntent`
- 生成 query rewrites
- 生成 source plan

### 8.3 Retrieval Orchestrator

负责：

- 选择要调用的 sources
- 并发调度 connector
- 控制每个源的超时、预算、限流

### 8.4 Connectors

一个数据源一个 connector。

建议首批：

- `openalex_connector`
- `semanticscholar_connector`
- `core_connector`
- `arxiv_connector`
- `unpaywall_resolver`

二期：

- `ieee_connector`
- `wanfang_connector`

### 8.5 Normalizer / Deduper

负责：

- 字段标准化
- DOI 标准化
- 标题清洗
- 多源合并

### 8.6 Embedding Service

负责：

- 文本 embedding
- 缓存 embedding
- 向量索引检索或重排

### 8.7 LLM Judge Service

负责：

- 对 Top-N 候选做结构化判别
- 输出理由、置信度、是否满足硬约束

### 8.8 Fulltext Resolver

负责：

- OA 解析
- PDF 链接获取
- 可读全文发现

### 8.9 Storage

建议至少准备三类存储：

- PostgreSQL：任务、结果、标准化 metadata
- Redis：缓存、限流、短期任务状态
- Vector DB / pgvector：embedding 与相似检索

如果你想先简单起步，也可以第一版只用：

- PostgreSQL + pgvector
- Redis

## 9. 推荐的 API 设计

如果希望能被其他项目直接调用，建议优先做 HTTP API，而不是先做 GUI。

### 9.1 核心接口

#### `POST /v1/search`

统一检索入口。

请求示例：

```json
{
  "query": "找近五年关于 RAG 在医学问答上的综述，优先开放获取",
  "mode": "quick",
  "top_k_recall": 200,
  "top_k_rerank": 30,
  "sources": ["openalex", "semanticscholar", "core", "arxiv"],
  "filters": {
    "is_oa": true
  },
  "include_explanations": true
}
```

返回示例：

```json
{
  "intent": {},
  "results": [],
  "debug": {
    "used_sources": [],
    "dropped_by_rules": 0,
    "dropped_by_vector": 0,
    "judged_by_llm": 0
  }
}
```

#### `POST /v1/search/plan`

只做 query planning，不执行检索。

适合：

- 调试 prompt
- 观察意图拆解是否正确

#### `POST /v1/search/retrieve`

只做共享召回层，不进入 Quick / Deep 排序层。

适合：

- 调试 connector
- 批量离线评估

#### `POST /v1/search/judge`

对传入候选列表做二次判别。

适合：

- 上游系统自己召回，你这里只负责高精度筛选

#### `POST /v1/search/quick`

明确走 Quick Search 通道。

适合：

- 低延迟搜索
- 探索式找论文
- 成本敏感场景

#### `POST /v1/search/deep`

明确走 Deep Search 通道。

适合：

- 复杂问题
- 需要高精度筛选
- 需要更强解释性

#### `POST /v1/search/fusion`

同时运行 Quick Search 和 Deep Search，再做融合去重。

适合：

- 质量优先
- 结果需要兼顾覆盖率与精度
- 可接受更高延迟和成本

#### `POST /v1/resolve/fulltext`

根据 DOI 或 paper record 补齐：

- OA
- PDF
- landing page

### 9.2 模式建议

建议对外暴露三种模式：

- `quick`
  - 多源召回 + 去重 + 向量/关键词混合重排
  - 默认不进入 LLM judge
- `deep`
  - 多源召回 + 去重 + 规则过滤 + LLM Precision Judge
  - 结果以精度优先
- `fusion`
  - Quick 和 Deep 并行运行
  - 融合召回、去重和排序

## 10. 推荐的 Docker 打包方式

建议第一版先做“单服务容器化”，不要一开始就拆太多微服务。

### 10.1 第一版推荐

- `app`
  - FastAPI 服务
  - 包含 planner / orchestrator / connectors / reranker
- `postgres`
  - metadata + pgvector
- `redis`
  - cache + task state

这个组合已经足够支撑 MVP。

### 10.2 docker-compose 建议

建议包含：

- `paper-search-api`
- `postgres`
- `redis`

如果后续 embedding 压力变大，再增加：

- `worker`
- `queue`

### 10.3 配置项建议

通过环境变量控制：

- `OPENALEX_BASE_URL`
- `SEMANTIC_SCHOLAR_API_KEY`
- `CORE_API_KEY`
- `IEEE_API_KEY`
- `WANFANG_APP_KEY`
- `WANFANG_APP_SECRET`
- `WANFANG_APPCODE`
- `UNPAYWALL_EMAIL`
- `LLM_MODEL`
- `EMBEDDING_MODEL`
- `DATABASE_URL`
- `REDIS_URL`

## 11. 推荐的目录结构

如果你打算开始落代码，建议结构类似：

```text
paper_search_agent/
  app/
    api/
      routes_search.py
      routes_resolve.py
    domain/
      models.py
      schemas.py
    planners/
      intent_planner.py
      query_rewriter.py
    orchestrators/
      retrieval_orchestrator.py
    connectors/
      base.py
      openalex_connector.py
      semanticscholar_connector.py
      core_connector.py
      arxiv_connector.py
      ieee_connector.py
      wanfang_connector.py
      unpaywall_resolver.py
    ranking/
      lexical_ranker.py
      vector_ranker.py
      quick_ranker.py
      fusion_ranker.py
      llm_judge.py
    normalization/
      canonicalizer.py
      deduper.py
    storage/
      postgres.py
      cache.py
      vector_store.py
    workers/
      tasks.py
    config.py
    main.py
  docs/
  tests/
  docker-compose.yml
  Dockerfile
  pyproject.toml
```

### 11.1 面向多种交付形态的目录扩展建议

如果你已经明确后续会同时支持：

- 独立后端接口服务
- 独立前端页面
- 给其他 agent 调用的 skill 封装

那么建议把目录进一步扩成“核心能力 + 多种适配层”的结构。

推荐思路是：

- 核心检索能力只写一份
- API 只是其中一个适配层
- 前端只是调用 API 的一个展示层
- skill 只是另一个调用入口，而不是重新实现一套检索逻辑

更适合长期演进的结构大致是：

```text
paper_search_agent/
  app/
    domain/
    planners/
    orchestrators/
    connectors/
    ranking/
    normalization/
    storage/
    services/
      search_service.py
      resolve_service.py
  interfaces/
    api/
      fastapi_app/
    frontend/
      webapp/
    skill/
      paper-search-skill/
  config/
  docs/
  tests/
```

其中职责建议是：

- `app/`
  - 放真正的核心能力
  - 不依赖 Django，不依赖某个前端框架，也不依赖 skill 运行时
- `interfaces/api/`
  - 负责 HTTP 路由、序列化、鉴权、限流、任务入口
- `interfaces/frontend/`
  - 负责用户页面、交互、结果展示
- `interfaces/skill/`
  - 负责把现有后端或 SDK 封装成 skill，让其他 agent 能调用

## 12. 多交付形态开发建议

你当前的方向本质上不是“做一个页面”或“做一个 skill”，而是做一个：

`可复用的论文检索核心能力`

然后再给它包上不同的使用入口。

这三个入口建议明确拆开设计。

### 12.1 形态一：独立后端接口服务

这是最优先的主线。

建议定位：

- 它是整个系统的唯一事实来源
- 其他入口都尽量调用它，而不是重复实现

建议职责：

- 暴露统一检索 API
- 暴露全文解析 / OA 解析 API
- 承担 query planning、source orchestration、dedup、quick/deep/fusion
- 统一记录日志、指标、缓存和错误码

建议形式：

- 用 FastAPI 独立部署
- 暂时不要直接嵌进 Django 项目
- Django 后续作为“调用方”接这个服务即可

这样做的好处是：

- 核心服务和业务站点解耦
- 后续你换 Django、Flask、Node、内部平台都还能复用
- skill 也可以直接调用同一个服务

### 12.2 形态二：独立前端页面

这个前端页面建议被视为“后端 API 的官方客户端”，而不是另一个业务核心。

建议页面能力先做最小闭环：

- 一个查询输入框
- Quick / Deep / Fusion 模式切换
- 可选 sources 多选
- 结果列表
- 论文详情抽屉或侧栏
- OA / PDF / 引用 / 参考文献入口展示
- 命中理由与排除理由展示

建议前端不要做的事情：

- 不要把 query planning 放在前端
- 不要把 connector 调用散落在浏览器端
- 不要在前端直接管理各源 API key

也就是说，前端只负责：

- 输入 query
- 调用统一后端 API
- 展示结构化结果

### 12.3 形态三：给其他 agent 调用的 skill

这部分建议你把 skill 当成“调用入口封装”，不是系统主架构。

推荐方式：

1. 先把后端 API 做稳定
2. 再提供一个轻量 SDK 或 skill
3. skill 内部优先调用统一 API
4. 只有在必须本地运行时，才让 skill 直接调底层 connector

原因是：

- skill 更适合复用稳定能力
- 不适合承载复杂 provider 配置、限流、缓存和状态管理
- 如果 skill 直接耦合所有 source 细节，后期维护会很重

skill 更适合承担的内容：

- 调用统一检索接口
- 帮 agent 选择 `quick/deep/fusion`
- 约束输入输出 schema
- 提供标准 prompt / tool 使用说明

不建议 skill 承担的内容：

- 管理所有 source 的鉴权和签名
- 实现复杂的去重与重排
- 保存缓存、向量索引和数据库状态

### 12.4 推荐的分层原则

建议明确遵守下面这条原则：

`核心检索逻辑只存在一份，接口层和 skill 层都只是薄封装`

推荐分层如下：

1. `Core Engine`
   - SearchIntent
   - Connector
   - Planner
   - Ranker
   - Judge
   - Resolver
2. `Service Layer`
   - SearchService
   - ResolveService
   - SourceAvailabilityService
3. `Delivery Layer`
   - HTTP API
   - Frontend Web UI
   - Skill / Tool Wrapper

这样可以避免这些常见问题：

- 前端和后端各维护一套 source 选择逻辑
- skill 和 API 各维护一套 quick/deep/fusion 行为
- Django 集成时把检索核心写死进业务站点

### 12.5 如果后续接 Django，推荐怎么接

你已经提到“作为单独的后端接口供 Django 调用”，这个方向是对的。

推荐做法：

- 当前项目先作为独立检索服务开发
- Django 项目后续通过 HTTP 或内部 SDK 调这个服务
- Django 只处理：
  - 用户体系
  - 权限
  - 业务页面
  - 搜索历史
  - 收藏、导出、任务编排

检索服务自己处理：

- 检索源配置
- source 开关
- 查询编排
- 去重重排
- LLM judge
- 全文解析

不要一开始就把这些能力塞进 Django app 里，否则后续 skill 复用和独立部署都会变难。

### 12.6 source 开放状态应该放在哪里

既然你后续既有前端、又有 Django、又有 skill，这里建议把 source 状态拆成两层。

第一层：静态配置

- 写在 `config.yaml`
- 表示“系统层面是否支持这个源”
- 例如：
  - `enabled`
  - `public_enabled`
  - `supports_quick`
  - `supports_deep`
  - `supports_fusion`

第二层：运行时状态

- 建议后续放数据库或管理后台
- 表示“当前实例是否真的开放这个源”
- 例如：
  - 是否已配置可用 key
  - 是否通过健康检查
  - 是否因配额耗尽被临时关闭
  - 是否仅管理员可用

这样你的前端页面、Django 站点和 skill 都可以读取同一个“当前可用 source 列表”。

### 12.7 推荐的开发顺序

建议不要三条线同时铺开，而是按下面顺序做。

#### Step 1：先完成核心后端 API

目标：

- 把检索核心跑通
- 把 `quick / deep / fusion` API 稳定下来

优先实现：

- `POST /v1/search/quick`
- `POST /v1/search/deep`
- `POST /v1/search/fusion`
- `POST /v1/search/plan`
- `POST /v1/resolve/fulltext`

#### Step 2：再做独立前端页面

目标：

- 验证用户实际使用流程
- 验证结果展示、解释性和交互方式

这一层重点不是炫技，而是帮助你尽快发现：

- Quick 和 Deep 结果差异是否符合预期
- 用户是否真的会手动切换 sources
- 参考文献 / PDF / OA 链接如何展示最顺手

#### Step 3：最后做 skill 封装

目标：

- 让别的 agent 可直接复用你的检索能力

建议 skill 第一版不要直接连接所有底层 source，而是：

- 直接调用你自己的统一后端 API
- 暴露统一输入：
  - query
  - mode
  - sources
  - filters
- 暴露统一输出：
  - results
  - reasons
  - source metadata

这样 skill 会非常轻，也更稳定。

### 12.8 什么时候再考虑 SDK

如果后续你发现下面两个场景都成立：

- Django 服务端需要高频内调
- skill 或其他 Python 项目也想直接复用

那时再补一个 Python SDK 会很合适。

推荐形态：

- `client.search_quick(...)`
- `client.search_deep(...)`
- `client.search_fusion(...)`
- `client.resolve_fulltext(...)`

这样就会形成：

- 核心能力
- HTTP API
- Python SDK
- Skill Wrapper

这四层体系，复用性会很好。

## 13. 推荐的实施顺序

建议分四个阶段做，不要一上来把所有数据库全部接完。

### Phase 1：MVP 后端核心

目标：

- 先把统一流程跑通

只接：

- OpenAlex
- Semantic Scholar
- Unpaywall

功能：

- `SearchIntent`
- 多源召回
- 标准化去重
- Quick Search 通道
- Deep Search 通道
- 统一 API

为什么这样选：

- 英文论文检索已经能形成基本闭环
- OpenAlex + Semantic Scholar 足够验证召回质量
- Unpaywall 能补全文入口

### Phase 2：前端与交互验证

增加：

- 独立前端页面
- Quick / Deep / Fusion 交互切换
- 结果详情页
- source 可用性展示

收益：

- 能更早验证真实用户体验
- 能发现结果解释与展示层的问题
- 能为 Django 集成提供现成页面原型

### Phase 3：补齐广覆盖

增加：

- CORE
- arXiv

收益：

- OA 覆盖更强
- 预印本更全
- 适合 AI 方向论文检索

### Phase 4：专项数据源

增加：

- IEEE
- 万方

条件：

- 已拿到可用 key / 鉴权信息
- 已确认合规边界

### Phase 5：skill / SDK / 离线索引

增加：

- skill 封装
- 可选 Python SDK
- 本地 metadata cache
- embedding cache
- 定时更新任务
- 评估集与监控

收益：

- 能被其他 agent 稳定调用
- 能被 Django 或其他 Python 服务复用
- 才真正具备跨项目复用能力

## 14. 两种检索方式怎么搭配最好

你当前设想的两种方式本身是对的，但按产品设计更适合把它们做成两条独立面向用户的检索方案，而不是默认串联。

### 方案一：Quick Search

`共享查询层 -> 多源召回 -> 去重 -> 向量/关键词混合快速筛选 -> 返回结果`

适合：

- 用户只是想快速找一批相近论文
- 批量离线处理
- 成本敏感
- 对解释性要求不高
- 交互式搜索框默认模式

特点：

- 延迟低
- 结果覆盖广
- 适合先看候选集合

### 方案二：Deep Search

`共享查询层 -> 多源召回 -> 去重 -> 规则过滤 -> LLM Precision Judge -> 返回结果`

适合：

- 用户问题包含复杂约束
- 需要区分“方法相关”和“任务真正匹配”
- 需要判断“是否为综述”“是否比较研究”“是否针对某人群/场景”
- 需要更强解释性和命中理由

这是纯关键词或纯 embedding 很难稳定做好的部分。

特点：

- 精度高
- 成本高
- 延迟高于 Quick Search

### 方案三：Fusion 总通道

`共享查询层 -> Quick Search 与 Deep Search 并行 -> 结果融合去重 -> 返回结果`

适合：

- 既想保留广覆盖，又想补上高精度判断
- 结果数量不大但质量要求高
- 允许更高延迟

推荐作为：

- 专家模式
- 后台批处理模式
- 高价值查询模式

## 15. LLM 提示词与输出控制建议

为了让 LLM judge 稳定，建议不要让它自由回答，而要用严格 JSON schema。

推荐评价维度：

- 主题匹配度
- 硬约束是否满足
- 软偏好是否满足
- 是否值得保留
- 保留原因
- 不确定性

还建议加入：

- `insufficient_metadata`
- `needs_fulltext`

这样当标题+摘要不够判断时，系统可以进入“按需拉更详细 metadata 或全文”的分支。

## 16. 评估指标建议

如果你想把这个系统做成真正可复用的服务，建议尽早准备评估集。

至少评估：

- Recall@K
- Precision@K
- MRR / nDCG
- LLM judge 命中率
- 平均响应时间
- 单请求平均成本
- 各数据源命中贡献率

同时记录：

- 哪些结果是被规则过滤掉的
- 哪些结果是被向量层保留的
- 哪些结果是被 LLM 改判的

这样你后面才能知道究竟该优化 query planning、connector 还是 rerank。

## 17. 最终推荐方案

如果让我给你一个当前最值得落地的方案，我会建议：

### 技术路线

- 后端：Python + FastAPI
- 前端：独立 Web 前端，作为 API 官方客户端
- 存储：PostgreSQL + pgvector + Redis
- 首批数据源：OpenAlex + Semantic Scholar + Unpaywall
- 第二批：CORE + arXiv
- 第三批：IEEE + 万方

### 流程路线

1. 用户 query -> LLM 解析成 `SearchIntent`
2. 生成 `1~3` 个 query rewrite
3. 多源 connector 并发召回
4. 标准化 + DOI/title 去重
5. 按 `mode` 路由到 `quick`、`deep` 或 `fusion`
6. Quick 通道做向量 + 关键词混合重排
7. Deep 通道做规则过滤 + `LLM Precision Judge`
8. Fusion 通道做双路并行与融合去重
9. 用 Unpaywall / CORE discover 补全全文入口
10. 返回带解释的结果

### 交付路线

- 第一交付物：独立检索后端 API
- 第二交付物：独立前端页面
- 第三交付物：skill 封装
- Django 后续作为调用方接入，而不是承载核心检索实现

### 抽象路线

- 不要把主架构建立在 Django 或 skill 上
- 不要把主逻辑建立在“关键词穷举 fan-out”上
- 要把主架构建立在：
  - `SearchIntent`
  - `Connector`
  - `CanonicalPaper`
  - `HybridRanker`
  - `LLMJudge`
  - `FulltextResolver`

## 18. 下一步建议

建议你接下来直接做这三件事：

1. 先定义统一的 `SearchIntent` 和 `CanonicalPaper` schema
2. 先实现 `OpenAlex + Semantic Scholar + Unpaywall` 三个 connector
3. 先把独立后端 API 的 `POST /v1/search/quick` 跑通，再实现 `POST /v1/search/deep`

等 Quick 和 Deep 两条通道都稳定后，再补 `POST /v1/search/fusion`，然后做独立前端页面，最后再把这套能力封装成 skill，会比一开始把所有入口一起铺开稳很多。
