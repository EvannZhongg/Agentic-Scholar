(function () {
  const sampleResponses = {
    quick: {
      query: "multimodal retrieval for scientific papers",
      rewritten_query: "multimodal retrieval scientific literature",
      mode: "quick",
      used_sources: ["openalex", "semanticscholar", "core"],
      total_results: 3,
      raw_recall_count: 26,
      deduped_count: 18,
      finalized_count: 3,
      intent: {
        original_query: "multimodal retrieval for scientific papers",
        rewritten_query: "multimodal retrieval scientific literature",
        must_terms: ["multimodal retrieval", "scientific literature"],
        should_terms: ["cross-modal", "document understanding", "scholarly search"],
        exclude_terms: [],
        filters: {},
        logic: "AND",
        criteria: [],
        planner: "llm",
        reasoning: "The user wants broad recent work on multimodal retrieval in academic literature search."
      },
      query_bundle: [
        {
          label: "rewritten-main",
          query: "multimodal retrieval scientific literature",
          purpose: "Main academic-English query"
        }
      ],
      results: [
        {
          source: "semanticscholar",
          source_id: "S2:sample-1",
          title: "Multi-Modal Retrieval for Scientific Document Exploration",
          abstract: "This work studies how text, figures and citation metadata can be fused to improve scholarly search and literature exploration interfaces.",
          year: 2024,
          doi: null,
          url: "https://example.org/papers/mm-retrieval-science",
          pdf_url: "https://example.org/papers/mm-retrieval-science.pdf",
          is_oa: true,
          authors: ["A. Chen", "M. Lewis"],
          score: 0.91,
          scores: {
            hybrid: 0.91,
            lexical: 0.88,
            semantic: 0.94
          },
          decision: null,
          confidence: null,
          reason: "strong title/abstract overlap with multimodal retrieval and scientific search intent",
          matched_fields: ["title", "abstract"],
          criteria_coverage: null,
          criterion_judgments: [],
          retrieval_traces: [
            {
              mode: "quick",
              query_label: "rewritten-main",
              query: "multimodal retrieval scientific literature",
              rendered_query: "multimodal retrieval scientific literature",
              purpose: "Main academic-English query"
            }
          ],
          raw: {}
        },
        {
          source: "openalex",
          source_id: "OA:sample-2",
          title: "Cross-Modal Scholarly Search with Text, Figures and Citations",
          abstract: "A retrieval pipeline for scientific corpora that mixes textual relevance, visual cues from figures and graph signals from citations.",
          year: 2023,
          doi: "10.0000/example.2023.002",
          url: "https://example.org/papers/cross-modal-scholarly-search",
          pdf_url: null,
          is_oa: false,
          authors: ["L. Morgan", "Y. Wang", "S. Patel"],
          score: 0.86,
          scores: {
            hybrid: 0.86,
            lexical: 0.83,
            semantic: 0.88
          },
          decision: null,
          confidence: null,
          reason: "good semantic alignment with scholarly retrieval despite weaker lexical specificity",
          matched_fields: ["title", "abstract"],
          criteria_coverage: null,
          criterion_judgments: [],
          retrieval_traces: [
            {
              mode: "quick",
              query_label: "rewritten-main",
              query: "multimodal retrieval scientific literature",
              rendered_query: "multimodal retrieval scientific literature",
              purpose: "Main academic-English query"
            }
          ],
          raw: {}
        },
        {
          source: "core",
          source_id: "CORE:sample-3",
          title: "Scholarly Search Interfaces for Multimodal Evidence",
          abstract: "The paper presents a practical interface for navigating papers with text snippets, image panels and evidence cards across multiple retrieval channels.",
          year: 2022,
          doi: null,
          url: "https://example.org/papers/scholarly-search-interfaces",
          pdf_url: null,
          is_oa: true,
          authors: ["R. Diaz"],
          score: 0.8,
          scores: {
            hybrid: 0.8,
            lexical: 0.77,
            semantic: 0.82
          },
          decision: null,
          confidence: null,
          reason: "relevant interface-oriented result with clear multimodal search evidence",
          matched_fields: ["title"],
          criteria_coverage: null,
          criterion_judgments: [],
          retrieval_traces: [
            {
              mode: "quick",
              query_label: "rewritten-main",
              query: "multimodal retrieval scientific literature",
              rendered_query: "multimodal retrieval scientific literature",
              purpose: "Main academic-English query"
            }
          ],
          raw: {}
        }
      ]
    },
    deep: {
      query: "找一下超材料FSS的论文",
      rewritten_query: "metamaterial frequency selective surface (FSS) papers",
      mode: "deep",
      used_sources: ["openalex", "semanticscholar", "core", "arxiv", "ieee"],
      total_results: 3,
      raw_recall_count: 144,
      deduped_count: 125,
      finalized_count: 3,
      intent: {
        original_query: "找一下超材料FSS的论文",
        rewritten_query: "metamaterial frequency selective surface (FSS) papers",
        must_terms: ["metamaterial", "frequency selective surface", "FSS"],
        should_terms: ["metasurface", "angular stability", "reconfigurable", "tunable"],
        exclude_terms: [],
        filters: {},
        logic: "AND",
        criteria: [
          {
            id: "c1",
            description: "Works focused on metamaterials in electromagnetic design.",
            required: true,
            terms: ["metamaterial"],
            query_hints: ["metamaterial", "electromagnetic metamaterial"]
          },
          {
            id: "c2",
            description: "Works specifically about frequency selective surfaces (FSS).",
            required: true,
            terms: ["frequency selective surface", "FSS"],
            query_hints: ["frequency selective surface", "frequency selective surface fss"]
          },
          {
            id: "c3",
            description: "Works that combine metamaterial and FSS concepts.",
            required: false,
            terms: ["metamaterial FSS", "metasurface FSS"],
            query_hints: ["metamaterial fss", "metasurface fss"]
          }
        ],
        planner: "llm",
        reasoning: "The request asks for papers on metamaterial-based frequency selective surfaces without additional year or venue filters."
      },
      query_bundle: [
        {
          label: "rewritten-main",
          query: "metamaterial frequency selective surface (FSS) papers",
          purpose: "Main academic-English query"
        },
        {
          label: "criteria-and",
          query: "\"electromagnetic metamaterial\" AND frequency selective surface fss",
          purpose: "Strict conjunction across required criteria"
        },
        {
          label: "must-terms",
          query: "metamaterial frequency selective surface FSS",
          purpose: "Focused must-term fallback"
        }
      ],
      results: [
        {
          source: "openalex",
          source_id: "https://openalex.org/W4313407071",
          title: "Active Metamaterial Frequency Selective Surface (FSS) Based Tunable Radar Absorbing Structure (RAS)",
          abstract: "A tunable absorbing structure that combines active metamaterial behavior with frequency selective surface design for radar applications.",
          year: 2022,
          doi: "https://doi.org/10.1007/978-981-16-6441-0_5",
          url: "https://doi.org/10.1007/978-981-16-6441-0_5",
          pdf_url: null,
          is_oa: false,
          authors: ["Saptarshi Ghosh"],
          score: 0.9913,
          scores: {
            deep_heuristic: 0.9827,
            deep_required_coverage: 1,
            deep_llm: 0.9827,
            deep: 0.9913
          },
          decision: "keep",
          confidence: 0.9957,
          reason: "required coverage 2/2; supported criteria: c1, c2; matched 3/3 must terms",
          matched_fields: ["title"],
          criteria_coverage: 1,
          criterion_judgments: [
            {
              criterion_id: "c1",
              description: "Works focused on metamaterials in electromagnetic design.",
              required: true,
              supported: true,
              score: 1,
              confidence: 0.9,
              evidence: ["metamaterial"],
              reason: "criterion supported with exact term match"
            },
            {
              criterion_id: "c2",
              description: "Works specifically about frequency selective surfaces (FSS).",
              required: true,
              supported: true,
              score: 1,
              confidence: 0.9,
              evidence: ["frequency selective surface", "FSS"],
              reason: "criterion supported with direct title evidence"
            },
            {
              criterion_id: "c3",
              description: "Works that combine metamaterial and FSS concepts.",
              required: false,
              supported: true,
              score: 0.5,
              confidence: 0.62,
              evidence: ["metamaterial FSS"],
              reason: "criterion partially supported by combined title phrase"
            }
          ],
          retrieval_traces: [
            {
              mode: "deep",
              query_label: "must-terms",
              query: "metamaterial frequency selective surface FSS",
              rendered_query: "metamaterial frequency selective surface FSS",
              purpose: "Focused must-term fallback"
            }
          ],
          raw: {}
        },
        {
          source: "ieee",
          source_id: "IEEE:sample-2",
          title: "Reconfigurable Metasurface FSS with Wide-Angle Stability",
          abstract: "This paper describes a reconfigurable FSS architecture that uses metasurface principles to maintain stable behavior under varying incidence angles.",
          year: 2021,
          doi: "10.0000/example.2021.010",
          url: "https://example.org/papers/reconfigurable-metasurface-fss",
          pdf_url: null,
          is_oa: false,
          authors: ["H. Liu", "P. Roy"],
          score: 0.884,
          scores: {
            deep_heuristic: 0.81,
            deep_required_coverage: 1,
            deep_llm: 0.91,
            deep: 0.884
          },
          decision: "keep",
          confidence: 0.91,
          reason: "full required coverage with additional support for tunable and angular-stability related terms",
          matched_fields: ["title", "abstract"],
          criteria_coverage: 1,
          criterion_judgments: [
            {
              criterion_id: "c1",
              description: "Works focused on metamaterials in electromagnetic design.",
              required: true,
              supported: true,
              score: 0.82,
              confidence: 0.84,
              evidence: ["metasurface"],
              reason: "criterion supported by adjacent metamaterial vocabulary"
            },
            {
              criterion_id: "c2",
              description: "Works specifically about frequency selective surfaces (FSS).",
              required: true,
              supported: true,
              score: 1,
              confidence: 0.9,
              evidence: ["FSS"],
              reason: "criterion supported by direct acronym match"
            },
            {
              criterion_id: "c3",
              description: "Works that combine metamaterial and FSS concepts.",
              required: false,
              supported: true,
              score: 0.74,
              confidence: 0.8,
              evidence: ["metasurface FSS"],
              reason: "criterion supported by combined topic framing"
            }
          ],
          retrieval_traces: [
            {
              mode: "deep",
              query_label: "criteria-and",
              query: "\"electromagnetic metamaterial\" AND frequency selective surface fss",
              rendered_query: "\"electromagnetic metamaterial\" AND frequency selective surface fss",
              purpose: "Strict conjunction across required criteria"
            }
          ],
          raw: {}
        },
        {
          source: "arxiv",
          source_id: "arXiv:sample-3",
          title: "Compact Metamaterial Frequency Selective Surfaces for Low-Profile RF Filtering",
          abstract: "An arXiv preprint exploring compact unit-cell design choices for metamaterial-inspired frequency selective surfaces in low-profile RF filtering scenarios.",
          year: 2020,
          doi: null,
          url: "https://arxiv.org/abs/0000.00000",
          pdf_url: "https://arxiv.org/pdf/0000.00000.pdf",
          is_oa: true,
          authors: ["J. Rivera", "K. Ahmed", "X. Zhao"],
          score: 0.736,
          scores: {
            deep_heuristic: 0.71,
            deep_required_coverage: 1,
            deep_llm: 0.75,
            deep: 0.736
          },
          decision: "maybe",
          confidence: 0.78,
          reason: "strong coverage of required criteria with weaker evidence on optional tunable and hybrid design cues",
          matched_fields: ["title", "abstract"],
          criteria_coverage: 1,
          criterion_judgments: [
            {
              criterion_id: "c1",
              description: "Works focused on metamaterials in electromagnetic design.",
              required: true,
              supported: true,
              score: 0.91,
              confidence: 0.86,
              evidence: ["metamaterial"],
              reason: "criterion supported by exact match"
            },
            {
              criterion_id: "c2",
              description: "Works specifically about frequency selective surfaces (FSS).",
              required: true,
              supported: true,
              score: 1,
              confidence: 0.9,
              evidence: ["frequency selective surfaces"],
              reason: "criterion supported by title match"
            },
            {
              criterion_id: "c3",
              description: "Works that combine metamaterial and FSS concepts.",
              required: false,
              supported: false,
              score: 0.24,
              confidence: 0.45,
              evidence: [],
              reason: "combined concept is implied but not strongly stated"
            }
          ],
          retrieval_traces: [
            {
              mode: "deep",
              query_label: "rewritten-main",
              query: "metamaterial frequency selective surface (FSS) papers",
              rendered_query: "metamaterial frequency selective surface (FSS) papers",
              purpose: "Main academic-English query"
            }
          ],
          raw: {}
        }
      ]
    }
  };

  const state = {
    mode: "quick",
    busy: false,
    payload: null
  };

  const refs = {
    searchForm: document.getElementById("searchForm"),
    queryInput: document.getElementById("queryInput"),
    apiBaseInput: document.getElementById("apiBaseInput"),
    limitInput: document.getElementById("limitInput"),
    publicOnlyInput: document.getElementById("publicOnlyInput"),
    enableLlmInput: document.getElementById("enableLlmInput"),
    enablePlannerInput: document.getElementById("enablePlannerInput"),
    statusText: document.getElementById("statusText"),
    summaryPanel: document.getElementById("summaryPanel"),
    overviewPanel: document.getElementById("overviewPanel"),
    intentPanel: document.getElementById("intentPanel"),
    resultsPanel: document.getElementById("resultsPanel"),
    importButton: document.getElementById("importButton"),
    jsonFileInput: document.getElementById("jsonFileInput"),
    searchButton: document.getElementById("searchButton"),
    modeButtons: Array.from(document.querySelectorAll(".mode-button"))
  };

  function getDefaultApiBase() {
    if (window.location.protocol === "http:" || window.location.protocol === "https:") {
      return window.location.origin + "/api";
    }
    return "http://127.0.0.1:8080/api";
  }

  function normalizeApiBase(value) {
    return (value || "").trim().replace(/\/+$/, "");
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatScore(value) {
    return typeof value === "number" ? value.toFixed(3) : "--";
  }

  function normalizeLink(value, kind) {
    const raw = String(value || "").trim();
    if (!raw) {
      return "";
    }
    if (/^https?:\/\//i.test(raw)) {
      return raw;
    }
    if (kind === "doi" || /^10\./.test(raw)) {
      return `https://doi.org/${raw.replace(/^doi:\s*/i, "")}`;
    }
    if (raw.startsWith("//")) {
      return `https:${raw}`;
    }
    return raw;
  }

  function truncate(text, length) {
    if (!text) {
      return "";
    }
    return text.length > length ? text.slice(0, length).trim() + "..." : text;
  }

  function setMode(mode) {
    state.mode = mode;
    refs.modeButtons.forEach((button) => {
      const isActive = button.dataset.mode === mode;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", String(isActive));
    });
  }

  function setBusy(isBusy) {
    state.busy = isBusy;
    refs.searchButton.disabled = isBusy;
    refs.searchButton.textContent = isBusy ? "检索中..." : "开始检索";
    refs.importButton.disabled = isBusy;
  }

  function setStatus(kind, message) {
    refs.statusText.textContent = message;
  }

  function ensurePayloadShape(payload) {
    if (!payload || typeof payload !== "object" || !Array.isArray(payload.results)) {
      throw new Error("导入内容不是合法的 SearchResponse JSON。");
    }
  }

  function renderSummary(payload) {
    const sources = Array.isArray(payload?.used_sources) ? payload.used_sources : [];
    const keepCount = payload
      ? (payload.results || []).filter((item) => item?.decision === "keep").length
      : "--";
    const cards = [
      { label: "Mode", value: payload?.mode || state.mode },
      { label: "Keep", value: keepCount },
      { label: "Finalized", value: payload ? (payload.finalized_count ?? payload.results.length) : "--" },
      { label: "Recall", value: payload?.raw_recall_count ?? "--" },
      { label: "Sources", value: payload ? sources.length : "--" },
      { label: "Planner", value: payload?.intent?.planner || "--" }
    ];

    refs.summaryPanel.innerHTML = `
      <div class="summary-metrics">
        ${cards.map((item) => `
          <article class="summary-item">
            <p class="summary-label">${escapeHtml(item.label)}</p>
            <div class="summary-value">${escapeHtml(item.value)}</div>
          </article>
        `).join("")}
      </div>
      ${payload && sources.length ? `
        <div class="summary-sources">
          <div class="tags">
            ${sources.map((item) => `<span class="tag tag-source">${escapeHtml(item)}</span>`).join("")}
          </div>
        </div>
      ` : ""}
    `;
  }

  function renderOverview(payload) {
    if (!payload) {
      refs.overviewPanel.innerHTML = `
        <div class="empty-state">
          <p>这里会展示当前 query、重写结果、source 和 intent 摘要。</p>
        </div>
      `;
      return;
    }

    const sources = Array.isArray(payload.used_sources) ? payload.used_sources : [];
    const filters = payload.intent?.filters && Object.keys(payload.intent.filters).length
      ? JSON.stringify(payload.intent.filters)
      : "无显式过滤";

    refs.overviewPanel.innerHTML = `
      <section class="section-block">
        <p class="section-title">Query</p>
        <article class="mini-card">
          <h3>${escapeHtml(payload.query || "未提供 query")}</h3>
          <p class="muted">rewritten: ${escapeHtml(payload.rewritten_query || "-")}</p>
        </article>
      </section>

      <section class="section-block">
        <p class="section-title">Sources</p>
        <div class="tags">
          ${sources.length ? sources.map((item) => `<span class="tag tag-source">${escapeHtml(item)}</span>`).join("") : '<span class="tag">暂无 source</span>'}
        </div>
      </section>

      <section class="section-block">
        <p class="section-title">Intent Notes</p>
        <article class="mini-card">
          <p>${escapeHtml(payload.intent?.reasoning || "当前响应未提供 reasoning。")}</p>
          <p class="muted">logic: ${escapeHtml(payload.intent?.logic || "-")} | filters: ${escapeHtml(filters)}</p>
        </article>
      </section>

      <section class="section-block">
        <p class="section-title">Terms</p>
        <div class="tags">
          ${(payload.intent?.must_terms || []).map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("") || '<span class="tag">暂无 must terms</span>'}
        </div>
        <div class="tags">
          ${(payload.intent?.should_terms || []).map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("") || '<span class="tag">暂无 should terms</span>'}
        </div>
      </section>
    `;
  }

  function renderIntent(payload) {
    if (!payload) {
      refs.intentPanel.innerHTML = `
        <div class="empty-state">
          <p>执行 deep 检索或导入结果后，这里会显示 criteria 和 query bundle。</p>
        </div>
      `;
      return;
    }

    const criteria = payload.intent?.criteria || [];
    const bundle = payload.query_bundle || [];

    refs.intentPanel.innerHTML = `
      <section class="section-block">
        <p class="section-title">Criteria</p>
        ${criteria.length ? criteria.map((item) => `
          <article class="criterion-item">
            <h3>${escapeHtml(item.id || "criterion")} ${item.required ? '<span class="tag tag-keep">required</span>' : '<span class="tag tag-maybe">optional</span>'}</h3>
            <p>${escapeHtml(item.description || "-")}</p>
            <div class="tags">
              ${(item.terms || []).map((term) => `<span class="tag tag-criterion">${escapeHtml(term)}</span>`).join("") || '<span class="tag">无 terms</span>'}
            </div>
          </article>
        `).join("") : '<div class="empty-state"><p>当前模式没有额外 criteria，适合直接看 quick 结果排序。</p></div>'}
      </section>

      <section class="section-block">
        <p class="section-title">Query Bundle</p>
        ${bundle.length ? bundle.map((item) => `
          <article class="bundle-item">
            <h3>${escapeHtml(item.label || "query")}</h3>
            <p>${escapeHtml(item.query || "-")}</p>
            <p class="muted">${escapeHtml(item.purpose || "无 purpose")}</p>
          </article>
        `).join("") : '<div class="empty-state"><p>当前响应没有 query bundle。</p></div>'}
      </section>
    `;
  }

  function renderDetailRow(label, tagMarkup) {
    if (!tagMarkup) {
      return "";
    }

    return `
      <div class="result-detail-row">
        <div class="result-detail-label">${escapeHtml(label)}</div>
        <div class="result-detail-body">${tagMarkup}</div>
      </div>
    `;
  }

  function renderResults(payload) {
    const results = payload?.results || [];
    if (!results.length) {
      refs.resultsPanel.innerHTML = '<div class="empty-state"><p>当前没有论文结果。输入 query 开始检索，或导入历史 JSON 结果。</p></div>';
      return;
    }

    refs.resultsPanel.innerHTML = results.map((result, index) => {
      const title = escapeHtml(result.title || "Untitled");
      const paperUrl = normalizeLink(result.url);
      const pdfUrl = normalizeLink(result.pdf_url);
      const doiUrl = normalizeLink(result.doi, "doi");
      const titleHtml = paperUrl
        ? `<a href="${escapeHtml(paperUrl)}" target="_blank" rel="noreferrer">${title}</a>`
        : title;
      const authors = (result.authors || []).length ? escapeHtml(result.authors.join(", ")) : "作者信息缺失";
      const score = formatScore(result.score);
      const year = result.year || "--";
      const primaryTags = [
        `<span class="tag tag-source">${escapeHtml(result.source || "unknown")}</span>`,
        result.decision
          ? `<span class="tag ${result.decision === "keep" ? "tag-keep" : "tag-maybe"}">${escapeHtml(result.decision)}</span>`
          : "",
        result.is_oa === true ? '<span class="tag tag-open-access">Open Access</span>' : ""
      ].filter(Boolean).join("");
      const signalTags = [
        typeof result.criteria_coverage === "number" ? `<span class="tag tag-metric">coverage ${result.criteria_coverage.toFixed(2)}</span>` : "",
        typeof result.confidence === "number" ? `<span class="tag tag-metric">confidence ${result.confidence.toFixed(2)}</span>` : ""
      ].filter(Boolean).join("");
      const matchedFields = (result.matched_fields || []).map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("");
      const criterionTags = (result.criterion_judgments || []).map((item) => `
        <span class="tag tag-criterion">
          ${escapeHtml(item.criterion_id || "criterion")} ${item.supported ? "✓" : "×"} ${typeof item.score === "number" ? item.score.toFixed(2) : "--"}
        </span>
      `).join("");
      const traceTags = (result.retrieval_traces || []).map((item) => `
        <span class="tag tag-trace">${escapeHtml(item.query_label || "trace")}</span>
      `).join("");
      const detailRows = [
        renderDetailRow("Status", primaryTags),
        renderDetailRow("Signals", signalTags),
        renderDetailRow("Matched", matchedFields),
        renderDetailRow("Criteria", criterionTags),
        renderDetailRow("Trace", traceTags)
      ].filter(Boolean).join("");

      return `
        <article class="result-card">
          <div class="result-top">
            <div class="result-main">
              <p class="panel-kicker">#${index + 1} · ${escapeHtml(result.source || "unknown source")}</p>
              <h3 class="result-title">${titleHtml}</h3>
            </div>
            <div class="result-score">
              <div class="score-label">score</div>
              <div class="score-value">${escapeHtml(score)}</div>
            </div>
          </div>

          <p class="meta-line">${escapeHtml(String(year))} | ${authors}</p>

          <p class="result-abstract">${escapeHtml(truncate(result.abstract || "当前结果没有摘要信息。", 280))}</p>

          ${detailRows ? `<div class="result-detail-grid">${detailRows}</div>` : ""}

          ${result.reason ? `<p class="result-reason"><strong>Why it matched:</strong> ${escapeHtml(result.reason)}</p>` : ""}

          <div class="link-row">
            ${paperUrl ? `<a class="link-pill" href="${escapeHtml(paperUrl)}" target="_blank" rel="noreferrer">Paper Link</a>` : ""}
            ${pdfUrl ? `<a class="link-pill" href="${escapeHtml(pdfUrl)}" target="_blank" rel="noreferrer">PDF</a>` : ""}
            ${doiUrl ? `<a class="link-pill" href="${escapeHtml(doiUrl)}" target="_blank" rel="noreferrer">DOI</a>` : ""}
          </div>
        </article>
      `;
    }).join("");
  }

  function renderInitialState() {
    renderSummary(null);
    renderOverview(null);
    renderIntent(null);
    renderResults(null);
  }

  function applyPayload(payload) {
    ensurePayloadShape(payload);
    state.payload = payload;

    if (payload.mode === "quick" || payload.mode === "deep") {
      setMode(payload.mode);
    }
    if (payload.query) {
      refs.queryInput.value = payload.query;
    }

    renderSummary(payload);
    renderOverview(payload);
    renderIntent(payload);
    renderResults(payload);
  }

  function buildRequestPayload() {
    const payload = {
      query: refs.queryInput.value.trim(),
      public_only: refs.publicOnlyInput.checked,
      enable_llm: refs.enableLlmInput.checked,
      enable_intent_planner: refs.enablePlannerInput.checked
    };

    const limitValue = refs.limitInput.value.trim();
    if (limitValue) {
      payload.limit_per_source = Number(limitValue);
    }

    return payload;
  }

  function explainRequestFailure(error) {
    const message = String(error?.message || error || "Unknown error");
    if (/Failed to fetch/i.test(message) || /NetworkError/i.test(message)) {
      return "接口请求失败。若你是直接打开静态文件，请先运行 `python frontend/dev_server.py`，或者改用导入 JSON 的方式测试展示。";
    }
    return message;
  }

  async function runSearch(event) {
    event.preventDefault();
    const query = refs.queryInput.value.trim();
    if (!query) {
      setStatus("error", "请输入检索问题。");
      refs.queryInput.focus();
      return;
    }

    const apiBase = normalizeApiBase(refs.apiBaseInput.value);
    if (!apiBase) {
      setStatus("error", "请提供可用的 API Base URL。");
      refs.apiBaseInput.focus();
      return;
    }

    setBusy(true);
    setStatus("loading", `正在执行 ${state.mode} 检索...`);

    try {
      const response = await fetch(`${apiBase}/search/${state.mode}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(buildRequestPayload())
      });

      const rawText = await response.text();
      const payload = rawText ? JSON.parse(rawText) : {};
      if (!response.ok) {
        throw new Error(payload.detail || `HTTP ${response.status}`);
      }

      applyPayload(payload);
      setStatus("idle", "");
    } catch (error) {
      setStatus("error", explainRequestFailure(error));
    } finally {
      setBusy(false);
    }
  }

  function importJsonFile(file) {
    if (!file) {
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const payload = JSON.parse(String(reader.result || ""));
        applyPayload(payload);
        setStatus("success", `已导入 ${file.name}。`);
      } catch (error) {
        setStatus("error", explainRequestFailure(error));
      }
    };
    reader.onerror = () => {
      setStatus("error", "读取 JSON 文件失败。");
    };
    reader.readAsText(file, "utf-8");
  }

  function bindEvents() {
    refs.modeButtons.forEach((button) => {
      button.addEventListener("click", () => {
        setMode(button.dataset.mode);
        if (!state.busy && state.payload && state.payload.mode !== button.dataset.mode) {
          setStatus("idle", `已切换到 ${button.dataset.mode} 模式，当前列表仍是上一份结果；点击开始检索或导入 JSON 即可更新。`);
        }
      });
    });

    refs.searchForm.addEventListener("submit", runSearch);
    refs.importButton.addEventListener("click", () => refs.jsonFileInput.click());
    refs.jsonFileInput.addEventListener("change", (event) => {
      const file = event.target.files && event.target.files[0];
      importJsonFile(file);
      refs.jsonFileInput.value = "";
    });
  }

  function init() {
    refs.apiBaseInput.value = getDefaultApiBase();
    refs.queryInput.value = "";
    bindEvents();
    renderInitialState();
    setStatus("idle", "");
  }

  init();
})();
