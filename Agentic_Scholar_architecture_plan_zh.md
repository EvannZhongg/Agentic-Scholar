# 论文检索 Agent 架构计划

更新日期：2026-04-03

## 1. 当前实现快照

截至 2026-04-03，当前仓库已经具备可运行的后端闭环：

- FastAPI 入口已经稳定
- `quick` / `deep` 两条检索链路都能返回真实结果
- Provider 注册、配置加载、敏感信息注入已打通
- 七个 connector 已接入统一搜索主链路
- LLM planner、Embedding rerank、Deep judge 都已有真实代码路径
- Redis 缓存、Provider 级请求控制、批处理策略已开始统一到运行时层
- 独立前端调试页和本地脚本已经能支撑日常联调

当前最准确的项目定位是：

`一个已经跑通主链路、但仍在继续收敛模块边界、排序质量、判定质量和运行时治理能力的论文检索后端 MVP。`

## 2. 当前代码结构

### 2.1 入口与 API 层

当前交付入口非常清晰：

- [app/main.py](app/main.py)
- [app/api/routes.py](app/api/routes.py)

已经提供的 API：

- `GET /v1/health`
- `GET /v1/providers`
- `GET /v1/providers/status`
- `POST /v1/search/quick`
- `POST /v1/search/deep`

尚未落地的 API：

- `POST /v1/search/fusion`
- `POST /v1/search/plan`
- `POST /v1/search/retrieve`
- `POST /v1/search/judge`
- `POST /v1/resolve/fulltext`

### 2.2 领域模型

当前统一 schema 位于 [app/domain/schemas.py](app/domain/schemas.py)。

已具备的核心结构：

- `SearchRequest`
- `SearchIntent`
- `SearchCriterion`
- `CriterionJudgment`
- `QueryBundleItem`
- `RetrievalTrace`
- `PaperResult`
- `SearchResponse`
- `ProbeResult`

当前这个模型层已经能支撑主流程，但仍偏“实用 MVP”而不是最终抽象：

- `PaperResult` 既承担标准化结果，也承担返回给 API 的展示结构
- `CriterionJudgment` 已够用，但还没有独立的 `JudgmentRecord`
- 还没有更完整的 `CanonicalPaper`

### 2.3 核心服务层

当前主干集中在：

- [app/services/search_service.py](app/services/search_service.py)
- [app/services/search_common.py](app/services/search_common.py)
- [app/services/quick_channel.py](app/services/quick_channel.py)
- [app/services/deep_channel.py](app/services/deep_channel.py)

职责分布大致是：

- `search_service.py`
  只做薄封装
- `search_common.py`
  承担 planner、query bundle、去重、共享召回、基础 relevance / criterion 评分
- `quick_channel.py`
  承担 Quick 的 hybrid rerank
- `deep_channel.py`
  承担 Deep 的 heuristic prefilter、LLM judge、动态送审窗口、最终 hard prune

这个结构已经比纯 MVP 更清晰，但共享层仍偏厚，`search_common.py` 还是下一轮最值得继续拆分的文件之一。

## 3. 当前已经落地的关键能力

### 3.1 Intent Planning

当前 `plan_search_intent()` 已支持两条路径：

- LLM planner
- heuristic fallback planner

对应特征：

- 当 `enable_intent_planner=false` 时，直接走 heuristic planner
- 当 `enable_llm=false` 或 LLM 未配置时，也会退回 heuristic planner
- LLM planner 会返回 `rewritten_query / must_terms / should_terms / exclude_terms / filters / logic / criteria / reasoning`
- prompt 已要求对非英文 query 尽量生成面向英文论文源的学术英文 `rewritten_query`
- prompt 已要求尽量保留 acronym、模型名、数据集名、作者名、会议名和领域术语
- prompt 已要求 `query_hints` 只保留 1-4 个词的 provider-friendly noun phrase

当前 heuristic planner 也补了两件重要工作：

- `normalize_text()` 已改成 Unicode-aware
- 已为 CJK 增加 fallback tokenization

这意味着多语言体验已经比最初的英文中心版本更好，但依然明显受限于是否存在可用的 LLM rewrite。

### 3.2 Quick Search

当前 Quick 已经不是“单纯多源召回 + 简单排序”，而是完整通道：

1. 规划 intent
2. 构造 query bundle
3. 多源召回
4. 去重
5. lexical / semantic / source prior / recency / OA 混合打分
6. 统一排序输出

几个真实实现细节：

- Quick 默认会构造 `rewritten-main`，并尝试加入 `original-query`
- 但默认配置 `retrieval.quick.max_query_variants=1`
- 因此当前默认实际只下发 `rewritten-main`
- Embedding 可用时，会调用 [app/llm/embedding_client.py](app/llm/embedding_client.py) 做语义相似度
- Embedding 不可用时，会自动退化为 lexical + source prior + recency + OA

Quick 的定位已经很明确：

- 更低延迟
- 更低成本
- 更适合广覆盖探索式检索

### 3.3 Deep Search

当前 Deep 已经是 criterion-aware 的独立链路，而不是 Quick 的简单后处理。

当前主路径：

1. 规划 intent
2. 生成面向复杂组合查询的 query bundle
3. 多源召回
4. criterion-level heuristic 预评分
5. 基础 hard filter
6. 按 source 执行可选 LLM judge
7. 去重、排序、最终 hard prune

当前已经落地的 Deep 关键能力：

- `criteria + logic + query bundle + criterion-level judge`
- provider-specific recall / query rendering
- `retrieval_traces`
- 动态送审窗口
- full-coverage 保底送审
- coverage band round-robin
- lane early-stop
- 最终 `keep + 高分 maybe` 收敛策略
- `raw_recall_count / deduped_count / finalized_count`

当前 hard filter 仍是第一版，主要依赖：

- `year_from`
- `year_to`
- `is_oa`

这些 filter 已有代码路径，但目前仍主要由 planner 的 `filters` 驱动，而不是已经暴露成更完整的外部 API 参数。

### 3.4 Query Bundle 与复杂组合查询

当前 query bundle 已不是单纯多发几条 query，而是开始承担“结构化召回策略”的角色。

Quick 侧：

- 默认只保留 `rewritten-main`

Deep 侧：

- `AND` 查询会优先构造 `criteria-and`
- 同时保留 `original-query`
- 可补 `must-terms`
- 再按 criterion 生成 focused query
- 最后补 `criteria-compact`

`OR` 查询也有分支逻辑，会优先构造 alternative-focused bundle。

当前值得注意的改进点：

- `query_hints` 已经过清洗，避免把 `search for`、`also try` 这类提示语直接送给 provider
- 组合条件 criterion 会保留独立 query 位
- 不同 provider 可通过自己的 `render_query_for_mode()` 继续做 source-aware 渲染

这块已经是当前项目最有价值的演进方向之一。

### 3.5 去重与结果合并

当前去重策略位于 [app/services/search_common.py](app/services/search_common.py)。

当前规则：

- 优先 DOI 标准化去重
- DOI 缺失时退化到 `title + year + first_author`
- 合并 `scores`
- 合并 `criterion_judgments`
- 合并 `retrieval_traces`
- 优先保留更完整的作者、摘要、标题和链接

这已经明显好于“按 source 直接拼接结果”，但仍然属于 MVP 级多源合并，而不是完整的 canonical merge。

### 3.6 Provider Runtime / Policy

当前运行时层已经不再是零散补丁，而是明确的架构部件。

代码位置：

- [app/services/provider_runtime.py](app/services/provider_runtime.py)
- [app/services/redis_runtime.py](app/services/redis_runtime.py)
- [app/connectors/base.py](app/connectors/base.py)

当前 `ProviderRuntimePolicy` 已覆盖：

- `batch_mode`
- `cache_backend`
- `cache_ttl_seconds`
- `rate_limit_backend`
- `min_interval_seconds`
- `serialize_requests`
- `lock_timeout_seconds`
- `blocking_timeout_seconds`
- `retry_on_statuses`
- `retry_backoff_seconds`

已经落地的工程收益：

- provider 的缓存与限流不再散落在 connector 里
- 多 query variant 的调度方式可以按 provider 配置
- arXiv、Crossref 这类更敏感的源，可以走严格串行和分布式锁
- Redis 不可用时，可退化到单进程本地请求控制

这层已经值得被视为“核心抽象”，不是临时措施。

### 3.7 Connector 接入现状

当前已接入主链路的 provider：

- OpenAlex
- Semantic Scholar
- CORE
- Crossref
- IEEE Xplore
- Unpaywall
- arXiv

当前配置里已预留但未启用：

- 万方
- CNKI

当前 provider 角色判断更适合这样理解：

- 主召回层：OpenAlex、Semantic Scholar、Crossref、arXiv、CORE
- 精准增强层：IEEE Xplore
- Resolver / enrichment 候选层：Unpaywall
- 受限预留层：万方、CNKI

### 3.8 LLM 与 Embedding 适配

当前适配层位于：

- [app/llm/client.py](app/llm/client.py)
- [app/llm/embedding_client.py](app/llm/embedding_client.py)
- [app/prompts.py](app/prompts.py)

当前实现方式：

- LLM 客户端兼容 `/responses` 与 `/chat/completions`
- Embedding 客户端直接调用 `/embeddings`
- 当前是 OpenAI 兼容 HTTP 调用方式，而不是依赖官方 SDK

这层已经足以支撑当前项目，但未来如果进入更稳定阶段，仍值得补齐：

- 更明确的错误处理
- 更细的接口选择日志
- 更强的响应校验

### 3.9 前端调试页

当前前端不应被理解为正式产品前端，而应被理解为联调沙盒。

代码位置：

- [frontend/index.html](frontend/index.html)
- [frontend/app.js](frontend/app.js)
- [frontend/dev_server.py](frontend/dev_server.py)

它已经能做：

- 直接调用现有 `/search/quick` 和 `/search/deep`
- 展示 `intent`、`criteria`、`query_bundle`
- 展示结果原因和 `retrieval_traces`
- 导入历史 JSON 做结果回放

它目前不承担：

- 核心检索逻辑
- API 凭证管理
- 正式产品交互流程

## 4. 当前仍存在的结构性缺口

### 4.1 共享层仍偏厚

`search_common.py` 目前仍同时承担：

- planner
- query bundle
- 文本规范化
- relevance 打分
- criterion 打分
- 去重
- 共享召回

这说明项目已经从“全堆一个服务文件”进化到了“共享核心尚未拆细”的阶段。

### 4.2 统一领域模型还不够丰富

当前已经够用，但还缺：

- `CanonicalPaper`
- `JudgmentRecord`
- 更完整的 metadata merge 策略

### 4.3 Quick 与 Deep 虽已分叉，但仍共享较厚的召回与规范化层

这是合理的，但后续需要继续明确边界：

- Quick 偏广覆盖与轻量排序
- Deep 偏强约束与强解释

如果边界继续模糊，未来做 `fusion` 时容易变成重复计算同一批候选。

### 4.4 多语言能力仍偏英文论文源

当前已经补上：

- 非英文 query 到学术英文 rewrite 的 prompt 约束
- Unicode-aware normalization
- CJK fallback tokenization

但仍未完全解决：

- bilingual lexical scoring
- provider 级 bilingual query policy
- 无 LLM 时的复杂中文 query rewrite

### 4.5 去重与 metadata 融合仍偏最小实现

当前已经不算“没有去重”，但也远未到完整 canonical merge：

- DOI 标准化已有
- 标题/年份/作者 fallback 已有
- citation、venue、publication type 等更深层字段尚未系统合并

### 4.6 运行时治理仍不够完整

当前 runtime 已有首版，但仍缺：

- 统一日志
- 更细的指标
- 更稳定的错误码
- probe 与正式链路更细的观测对齐

### 4.7 自动化测试缺位

当前项目仍主要依赖：

- provider probe
- 本地脚本
- 人工 smoke test

这足以支持 MVP 演进，但不足以支撑更高频重构。

## 5. 当前不建议继续重复投入的方向

为了精简历史包袱，这里把一些“不再值得重复展开”的结论统一写清楚：

- 不需要再把项目描述成“纯架构草图”，因为主链路已经真实存在
- 不建议优先做更多外层包装，而忽略核心检索质量
- 不建议把独立前端调试页误写成正式前端
- 不建议把 Unpaywall 继续当主召回源来描述
- 不建议在没有收敛去重、排序和 judge 之前提前扩大战线到更多交付形态

## 6. 下一阶段推荐路线

### 6.1 第一优先级：继续收敛核心检索质量

优先顺序建议是：

1. 继续补强 DOI 标准化和多源去重
2. 继续补强多语言 query planning 与 bilingual lexical policy
3. 继续收敛 Deep 的复杂组合查询链路
4. 继续增强 Quick 的 hybrid rerank
5. 继续增强 Deep 的 hard filters、criterion evidence 和 source-aware judge

### 6.2 第二优先级：把共享层进一步拆开

当前最自然的拆分方向：

- `planners/intent_planner.py`
- `orchestrators/retrieval_orchestrator.py`
- `normalization/deduper.py`
- `ranking/quick_ranker.py`
- `ranking/deep_ranker.py`
- `judge/llm_judge.py`

目标不是形式上的“拆文件”，而是让每层职责更明确，降低继续演进时的耦合成本。

### 6.3 第三优先级：补齐运行时治理与测试

推荐补的内容：

- 统一错误码
- provider 级指标
- 更细的 lane / query variant 观测
- 自动化测试

### 6.4 第四优先级：再补能力与交付形态

等核心收敛后，再做：

- `POST /v1/search/fusion`
- `POST /v1/resolve/fulltext`
- 正式前端页面
- Django 集成层
- skill 封装

## 7. 推荐的阶段判断

### Phase 1：后端 MVP 跑通

当前状态：已完成

已完成内容包括：

- 基础 API
- 七个 connector 首版接入
- Quick / Deep 双通道
- Redis runtime 首版
- LLM / Embedding 适配
- 调试脚本
- 独立前端调试页

### Phase 2：核心引擎收敛

当前状态：正在进行

当前最值得投入的工作包括：

- 继续强化去重
- 继续强化多语言检索质量
- 继续强化 Deep 复杂组合查询
- 继续拆薄共享层
- 继续增强 runtime 治理

### Phase 3：能力补齐与产品化

当前状态：尚未开始

对应内容包括：

- Fusion
- Fulltext Resolve
- 自动测试
- 正式前端
- Django / skill 封装

## 8. 一句话结论

当前项目已经跨过“纸面设计”阶段，核心问题不再是“要不要做多源论文检索后端”，而是“如何把已经跑通的 Quick / Deep 检索引擎继续收敛成更稳定、更可解释、更可治理的长期核心服务”。
