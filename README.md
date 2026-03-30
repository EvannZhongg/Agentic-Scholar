# Paper Search Agent

一个面向论文检索场景的独立后端服务原型。当前仓库已经完成多检索源接入、基础 API、配置加载、连通性探测与本地调试脚本，但整体仍处于 MVP 阶段，离“可长期演进的检索核心服务”还有一轮架构收敛。

当前项目优先作为：

- 独立后端接口服务
- 后续可被 Django 调用
- 后续可封装为 skill 给其他 agent 调用

## 当前状态

更新日期：2026-03-30

当前可以确认的进度：

- FastAPI 服务已可启动
- `quick` / `deep` 两条基础检索链路已可返回真实结果
- `quick` 已拆成独立检索通道，并接入 `hybrid rerank`
- `deep` 已拆成独立检索通道，并支持按检索源逐篇 `LLM judge`
- provider 配置、凭证注入、连通性探测脚本已具备
- 多个 connector 已完成首版接入
- 已落地首版 `provider runtime/policy` 层
- 已接入 Redis 配置化缓存与 provider 级请求控制
- 各检索源的批处理、缓存、限流策略已开始按 provider 解耦

当前阶段判断：

- 这是一个“后端原型已跑通”的项目，不再是纯设计稿
- 但还不是“架构计划 fully landed”的版本
- 当前更适合视为：`可运行 MVP + 待收敛的核心引擎`
- 当前文档说明已按 2026-03-30 的代码状态重新对齐

## 已完成内容

### 1. 配置体系

已完成：

- `config/config.yaml`
- `.env` / `.env.example`
- `config/settings.py`

当前配置方式：

- 非敏感配置放在 `config/config.yaml`
- API Key / Email 等敏感信息通过 `.env` 注入
- 支持通过 `*_env` 字段从环境变量映射到运行配置
- Redis 连接信息与 provider runtime 策略也统一在配置层声明

### 2. 后端 API MVP

当前已实现接口：

- `GET /v1/health`
- `GET /v1/providers`
- `GET /v1/providers/status`
- `POST /v1/search/quick`
- `POST /v1/search/deep`

当前尚未实现：

- `POST /v1/search/fusion`
- `POST /v1/search/plan`
- `POST /v1/search/retrieve`
- `POST /v1/search/judge`
- `POST /v1/resolve/fulltext`

### 3. 已接入的 connector

当前代码中已实现：

- OpenAlex
- Semantic Scholar
- CORE
- IEEE Xplore
- Unpaywall
- arXiv

当前配置中已预留但未实现运行接入：

- 万方
- CNKI

### 4. 调试与验证脚本

已提供脚本：

- `scripts/run_provider_probes.py`
- `scripts/run_quick_search.py`
- `scripts/run_search.py`

### 5. Prompt 与 LLM 适配

已完成：

- prompt 集中管理到 `app/prompts.py`
- LLM 客户端兼容 `responses` / `chat_completions`
- Embedding 客户端已接入
- 当前主路径优先依赖 LLM planner；不可用时回退到启发式 planner
- Deep Search 支持在有可用 LLM 配置时做结构化判定

### 6. Provider Runtime / Policy

已完成：

- 新增统一的 `provider runtime/policy` 层
- connector 的共享缓存、请求控制和批量调度已从具体 provider 逻辑中抽离
- Redis 已作为共享缓存和分布式请求控制后端接入
- `BaseSourceClient` 已统一承接标准化 query、批处理策略和 HTTP request 包装

当前策略现状：

- arXiv：`sequential batch + Redis cache + Redis 限流/锁 + 429 backoff`
- Semantic Scholar：`Redis cache + 保守请求控制`
- OpenAlex / CORE / IEEE / Unpaywall：已接入 Redis 热缓存

## 当前实际实现方式

### Quick Search

当前流程：

1. 对用户 query 做 intent planning
2. 当前优先使用 LLM planner 生成 `rewritten_query`、`must_terms`、`should_terms` 与 `filters`
3. 生成 Quick 通道专属 query variants
4. 把 query variants 下发给可用 source，并由各 provider 自己决定批处理策略
5. 对结果做统一去重和 DOI 标准化
6. 结合 lexical / semantic / source prior / recency / open access 做 `hybrid rerank`
7. 按 `quick score` 排序返回

注意：

- 当前 Quick Search 已不再只是启发式打分
- 在 embedding 可用时，会计算 query 与论文文档文本的语义相似度
- 若 embedding 不可用，会自动退化为 lexical + source prior + recency + OA 的混合排序
- provider 侧的缓存、限流和多 query variant 调度不再硬编码在共享召回层

### Deep Search

当前流程：

1. 对用户 query 做 intent planning
2. 当前优先使用 LLM planner 生成 `rewritten_query`、`must_terms`、`should_terms` 与 `filters`
3. 生成 Deep 通道专属 query variants
4. 做多源召回，并由各 provider runtime 控制 query variant 的批处理方式
5. 对每个 source 的候选结果先做启发式相关性判断
6. 再做基础硬过滤，例如 `year_from/year_to/is_oa`
7. 若 LLM 已配置且启用，则对每个检索源内的 Top-N 候选逐篇做结构化 `LLM judge`
8. 将 heuristic 分与 LLM relevance 融合成 `deep score`
9. 所有 source 结果再统一去重和排序返回

注意：

- Deep Search 现在已经是独立通道，不再只是 Quick 的后处理
- 当前 LLM judge 是“每个检索源内逐篇判断”，不是仅对全局结果做一次统一判定
- 当前硬过滤仍是第一版，主要支持 `year_from`、`year_to` 和 `is_oa`

### 当前数据模型

已经具备最小统一结构：

- `SearchIntent`
- `PaperResult`
- `SearchResponse`
- `ProbeResult`

但还未完全达到目标架构中的：

- 丰富版 `SearchIntent`
- 完整版 `CanonicalPaper`
- 独立版 `JudgmentRecord`

## 当前目录

```text
app/
  api/
  connectors/
  domain/
  llm/
  services/
config/
docs/
scripts/
```

关键文件：

- 后端入口：[app/main.py](app/main.py)
- 路由定义：[app/api/routes.py](app/api/routes.py)
- provider 注册：[app/services/provider_registry.py](app/services/provider_registry.py)
- 搜索主流程：[app/services/search_service.py](app/services/search_service.py)
- provider runtime：[app/services/provider_runtime.py](app/services/provider_runtime.py)
- Redis runtime：[app/services/redis_runtime.py](app/services/redis_runtime.py)
- prompt 集中管理：[app/prompts.py](app/prompts.py)
- LLM 客户端：[app/llm/client.py](app/llm/client.py)
- 配置文件：[config/config.yaml](config/config.yaml)
- 配置加载：[config/settings.py](config/settings.py)

## 当前架构判断

当前代码结构的优点：

- 已经形成统一入口和统一 schema
- connector 接口风格基本一致
- provider 开关、public 状态和 mode 能力已被纳入配置层
- 本地调试体验已经具备最小闭环
- provider 共享运行时策略已开始收口到统一层
- Redis 缓存和 provider 级请求控制已完成首版接入

当前仍存在的结构性缺口：

- `search_service.py` 已退化为薄封装，但共享逻辑仍集中在 `search_common.py`
- 还没有独立的 orchestrator、resolver、日志与指标模块
- 去重已补上 DOI 标准化，但仍属于 MVP 级多源合并
- 当前 Quick 的 semantic 分数仍是轻量 embedding rerank，不是成熟学习排序器
- provider runtime/policy 仍是第一版，日志、错误码、自动测试与更细粒度策略仍待补齐

## 当前稳定性与可用性说明

当前主链路实测可跑通的组合：

- OpenAlex
- Semantic Scholar
- arXiv（在 Redis 缓存与 provider 限流控制下可跑通，但需严格尊重公开配额）

其余源的现状：

- CORE：connector 已实现，可作为补充召回源继续验证稳定性
- IEEE Xplore：connector 已实现，但更适合在有明确需求或指定来源时启用
- Unpaywall：更适合作为 `OA/fulltext resolver`，不建议当主搜索源
- arXiv：已接入 Redis 队列、缓存和单连接控制，但热门 query 在公开配额下仍可能触发 `429`

## 已知问题

### 1. Quick / Deep 仍偏 MVP

当前 `quick` 和 `deep` 已可用，并且已经拆成两条独立通道，但整体仍然偏 MVP。

这意味着：

- Quick 已有 hybrid rerank，但排序策略仍较轻量
- Deep 已有按 source 逐篇 judge，但硬过滤条件仍较少
- 两条通道共享 planner 和基础召回层，后续还可继续向更强的 source-aware orchestration 演进

### 2. 去重仍不够强

当前去重逻辑主要依赖：

- DOI 标准化
- `title + year + first_author`

这会带来一个典型问题：

- 当前已经能处理 `doi.org/...` 与裸 DOI 的差异
- 但多源元数据融合仍不够丰富，例如 citation、venue、publication type 还没有完整合并策略

### 3. arXiv 限流严格

当前代码已落地首版 provider runtime 控制，并为 arXiv 接入：

- Redis 缓存
- Redis 分布式锁
- provider 级串行队列
- 最小请求间隔控制
- `429` 退避重试

但仍要注意：

- arXiv 公共接口额度非常紧
- 热门 query 在高频 smoke test 下仍可能返回 `429`
- 多实例部署时必须共用同一个 Redis，不能绕过官方限制

### 4. 多语言 query 规划与词法打分仍偏英文中心

当前主要问题：

- intent planner prompt 目前只要求 `rewritten_query` 保持 concise and searchable，还没有明确要求把中文或其他非英文 query 重写成适合英文论文源检索的学术英文，也没有强调保留 acronym、模型名、数据集名、作者名、会议名等实体
- `normalize_text()` 当前只提取 ASCII 字母和数字，中文、日文、韩文等文本进入词法链路后几乎会被直接丢掉
- 启发式 fallback planner 依赖 `normalize_text()`，因此在 LLM planner 不可用或失败时，多语言 query 的 `must_terms` / `should_terms` 会明显退化
- Quick / Deep 的 lexical 相关性与 Deep 的启发式预评分目前仍主要使用原始 `request.query` 做比较，`rewritten_query` 还没有完整贯穿到所有排序环节

这意味着：

- 仅仅在 prompt 里补一句“翻译成英文”还不够
- 对 OpenAlex、Semantic Scholar、arXiv、CORE 这类英文为主的数据源，英文 rewrite 会改善召回
- 但如果不同时补强 lexical normalization 和 bilingual query strategy，中文或其他非英文 query 在 rerank / judge 阶段仍会吃亏

建议方向：

- 保留原始 query，同时生成面向英文论文源的 `rewritten_query`
- 在 prompt 中明确保留术语实体，不要把 acronym、数据集、模型名和作者名翻坏
- 让 provider query policy 能按 source 选择 original-first、English-first 或 bilingual query variants
- 把 `normalize_text()` 和相关 lexical scoring 改成 Unicode-aware，或至少为 CJK 增加 fallback tokenization

### 5. Unpaywall 更适合作为 resolver

当前更推荐：

- 保留 Unpaywall probe
- 后续为 `resolve/fulltext` 接口服务

而不是把它当作常规 quick/deep 主召回源。

### 6. 暂无测试目录

当前仓库主要依赖：

- 本地脚本验证
- provider live probe
- 人工 smoke test

还没有系统化自动测试。

## 环境要求

建议：

- Python `3.10+`
- 已准备 `.env`
- 已安装 `requirements.txt`

安装依赖：

```bash
pip install -r requirements.txt
```

## 配置说明

1. 复制环境变量模板：

```bash
copy .env.example .env
```

2. 在 `.env` 中填入已有凭证：

- `OPENALEX_API_KEY`
- `SEMANTIC_SCHOLAR_API_KEY`
- `CORE_API_KEY`
- `UNPAYWALL_EMAIL`
- `IEEE_XPLORE_API_KEY`
- `REDIS_USERNAME`
- `REDIS_PASSWORD`
- `LLM_API_KEY`
- `EMBED_API_KEY`

3. 检查 `config/config.yaml` 中各 source 的开关：

- `enabled`
- `public_enabled`
- `supports_quick`
- `supports_deep`
- `supports_fusion`

4. 检查模型配置：

- `llm.provider`
- `llm.model`
- `llm.api_base`
- `llm.api_interface`
- `llm.api_interface_preference`
- `llm.temperature`
- `embedding.provider`
- `embedding.model`
- `embedding.api_base`
- `embedding.dim`
- `embedding.batch_size`

5. 检查 Redis 与 provider runtime 配置：

- `redis.host`
- `redis.port`
- `redis.db`
- `redis.key_prefix`
- `sources.<provider>.runtime.batch_mode`
- `sources.<provider>.runtime.cache_backend`
- `sources.<provider>.runtime.cache_ttl_seconds`
- `sources.<provider>.runtime.rate_limit_backend`
- `sources.<provider>.runtime.min_interval_seconds`
- `sources.<provider>.runtime.serialize_requests`

当前模型接口策略：

- `llm.api_interface=auto`
  - 运行时自动兼容 `responses` 和 `chat_completions`
- `llm.api_interface_preference=responses`
  - 在 `auto` 模式下优先尝试 `responses`

## 启动服务

开发模式启动：

```bash
uvicorn app.main:app --reload
```

说明：

- 默认配置按 `127.0.0.1:6379` 连接 Redis
- 若 Redis 不可用，部分 provider 会退化到本地请求控制，但无法提供跨进程共享缓存/限流

默认启动后可访问：

- `http://127.0.0.1:8000/v1/health`
- `http://127.0.0.1:8000/v1/providers`
- `http://127.0.0.1:8000/v1/providers/status`

## 调试脚本

### 1. 检查 provider 配置与 live probe

```bash
python scripts/run_provider_probes.py
```

### 2. 本地执行 quick search

```bash
python scripts/run_quick_search.py transformer
```

### 3. 用统一脚本测试 quick 或 deep

```bash
python scripts/run_search.py "transformer" --mode quick
python scripts/run_search.py "transformer" --mode deep
```

常用参数：

- `--mode quick|deep`
- `--limit-per-source 3`
- `--sources openalex,semanticscholar,core`
- `--public-only`
- `--disable-intent-planner`
- `--enable-llm`
- `--llm-top-n 8`
- `--raw`

如果不传 query，脚本会进入交互式输入：

```bash
python scripts/run_search.py --mode deep
```

## 下一步建议

建议按这个顺序继续推进：

1. 继续补强统一标准化与去重，形成更完整的 `CanonicalPaper`
2. 补强多语言 query planning 与 lexical normalization，形成“原始 query + 英文 rewrite + source-aware query policy”的统一策略
3. 把共享 planner / recall / dedup 继续从 `search_common.py` 中拆成更清晰的模块
4. 继续把 `provider runtime/policy` 扩展到更细粒度的 query policy、日志和观测指标
5. 继续增强 Quick Search 的 hybrid ranking
6. 继续增强 Deep Search 的硬规则过滤与更稳定的 per-source LLM judge 链路
7. 完成 `POST /v1/search/fusion`
8. 完成 `POST /v1/resolve/fulltext`
9. 增加统一日志、错误码和自动测试
10. 最后再做前端页面、Django 集成层和 skill 封装

## 相关文档

- 架构计划书：[paper_search_agent_architecture_plan_zh.md](paper_search_agent_architecture_plan_zh.md)
- OpenAlex 调研：[docs/openalex_api_research_zh.md](docs/openalex_api_research_zh.md)
- Semantic Scholar 调研：[docs/semanticscholar_api_research_zh.md](docs/semanticscholar_api_research_zh.md)
- CORE 调研：[docs/core_api_research_zh.md](docs/core_api_research_zh.md)
- IEEE 调研：[docs/ieee_xplore_api_research_zh.md](docs/ieee_xplore_api_research_zh.md)
- Unpaywall 调研：[docs/unpaywall_api_research_zh.md](docs/unpaywall_api_research_zh.md)
- arXiv 调研：[docs/arxiv_api_research_zh.md](docs/arxiv_api_research_zh.md)
