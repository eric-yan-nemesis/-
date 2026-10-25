"use strict";

const $ = (id) => document.getElementById(id);
const sampleText = "Meticulous researchers scrutinized the pervasive problem. Their candid report revealed the inherent complexity.\n\nA plausible plan could alleviate the detrimental effects and help resilient communities. The committee concurred, although its enthusiasm was ephemeral. Further scrutiny could alleviate the risks.";
const state = { analysis: null, filter: "all", selected: null, busy: false, stale: false, aiConfigured: false };

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function message(text, isError = false) {
  $("message").textContent = text;
  $("message").className = `message${isError ? " error" : ""}`;
  $("message").hidden = !text;
}

function warnings(items = []) {
  $("warnings").replaceChildren(...items.map((text) => element("p", "", text)));
  $("warnings").hidden = items.length === 0;
}

function updateCounts() {
  const text = $("text-input").value;
  $("word-count").textContent = (text.match(/[A-Za-z]+(?:['’-][A-Za-z]+)*/g) || []).length.toLocaleString();
  $("character-count").textContent = Array.from(text).length.toLocaleString();
  state.stale = Boolean(state.analysis && state.analysis.text !== text);
  if (state.analysis) $("result-status").textContent = state.stale ? "TEXT CHANGED · REANALYZE" : (state.analysis.ai_used ? "CONTEXT ENRICHED" : "READING NOTES READY");
  document.querySelectorAll(".export-button").forEach((button) => { button.disabled = state.busy || !state.analysis || state.stale; });
}

function updateBusy(busy, label = "正在理解你的文本…") {
  state.busy = busy;
  $("analyze-button").disabled = busy;
  $("analyze-button").classList.toggle("is-loading", busy);
  $("analyze-button-label").textContent = busy ? label : "发现进阶词汇";
  ["sample-button", "clear-button", "file-input", "text-input", "estimate-toggle", "text-tab", "file-tab"].forEach((id) => { $(id).disabled = busy; });
  $("ai-toggle").disabled = busy || !state.aiConfigured;
  document.querySelectorAll(".export-button").forEach((button) => { button.disabled = busy || !state.analysis || state.stale; });
  $("workspace").setAttribute("aria-busy", String(busy));
}

async function request(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = "请求未完成，请稍后再试。";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((entry) => entry.msg || "输入无效").join("；");
    } catch (_) { if (response.status === 413) detail = "文件过大，请使用不超过 10 MB 的文档。"; }
    throw new Error(detail);
  }
  return response;
}

function referenceLink(source, label) {
  if (!source || !source.url) return null;
  let parsed;
  try { parsed = new URL(source.url); } catch (_) { return null; }
  if (!["https:", "http:"].includes(parsed.protocol)) return null;
  const link = element("a", "source-link", label || source.name || "查看参考来源 ↗");
  link.href = parsed.href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

function candidateLevels(item) {
  const levels = [...new Set((item.level_candidates || []).filter((level) => ["C1", "C2"].includes(level)))].sort();
  return levels.length ? levels : [item.level];
}

function levelLabel(item) {
  const levels = candidateLevels(item);
  return levels.length > 1 ? `${levels.join(" / ")} · 义项待核` : levels[0];
}

function levelBadge(item) {
  return element("span", `level-badge ${item.level === "C2" ? "c2" : "c1"}`, levelLabel(item));
}

function contextUncertain(item) {
  return Boolean(state.analysis && state.analysis.occurrences.some((occurrence) => occurrence.item_id === item.id && occurrence.uncertain));
}

function dictionarySenses(senses = []) {
  const container = element("div", "dictionary-senses");
  if (!senses.length) container.append(element("p", "item-notes", "Wordset 暂无匹配义项或用例。"));
  senses.forEach((sense, index) => {
    const details = element("details", "dictionary-sense");
    details.open = index === 0;
    details.append(element("summary", "", `${sense.pos || "词性待核"} · ${sense.definition || "暂无定义"}`));
    const examples = Array.isArray(sense.examples) ? sense.examples : [];
    if (examples.length) {
      const list = element("ul", "dictionary-examples");
      examples.forEach((example) => list.append(element("li", "", example)));
      details.append(list);
    } else details.append(element("p", "item-notes", "Wordset 暂无用例"));
    container.append(details);
  });
  return container;
}

function aiAssistance(item) {
  const container = element("div", "ai-assistance");
  if (item.ai_definition) container.append(element("p", "", `AI 辅助定义 · 待核：${item.ai_definition}`));
  if (item.ai_example) container.append(element("p", "", `AI 生成例句 · 待核：${item.ai_example}`));
  return container;
}

function selectWord(id, scroll = false) {
  if (!state.analysis) return;
  const item = state.analysis.items.find((entry) => entry.id === id);
  if (!item) return;
  state.selected = id;
  document.querySelectorAll(".word-highlight").forEach((node) => {
    const selected = node.dataset.itemId === id;
    node.classList.toggle("is-selected", selected);
    node.setAttribute("aria-pressed", String(selected));
  });
  document.querySelectorAll("#vocabulary-body tr").forEach((row) => { row.classList.toggle("is-active-row", row.dataset.itemId === id); });
  const card = $("selected-word");
  const heading = element("div", "selected-word-heading");
  heading.append(element("strong", "", item.lemma), levelBadge(item), element("span", "status-badge", item.status === "reference" ? "有来源支持" : "等级估计"));
  const details = [heading, element("p", "", `${item.pos || ""} · ${item.chinese || "暂无中文释义"}`), element("p", "item-notes", `中文来源：${item.chinese_source || "中文学习注释／AI 辅助，非两份原词典内容"}`)];
  if (Array.isArray(item.dictionary_senses)) {
    details.push(dictionarySenses(item.dictionary_senses), aiAssistance(item));
    const usageSource = referenceLink(item.example_source || item.definition_source, "英文义项与用例：Wordset Dictionary ↗");
    if (usageSource) details.push(usageSource);
  } else details.push(element("p", "selected-definition", item.definition || ""));
  if (contextUncertain(item)) details.push(element("p", "item-notes", "语境待核：参考词表中的等级，不代表当前词义已确认。"));
  if (item.notes) details.push(element("p", "item-notes", item.notes));
  const link = referenceLink(item.source);
  if (link) details.push(link);
  card.replaceChildren(...details);
  card.hidden = false;
  if (scroll) card.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderHighlights() {
  const result = state.analysis;
  const container = $("highlighted-text");
  container.replaceChildren();
  const chars = Array.from(result.text);
  const items = new Map(result.items.map((item) => [item.id, item]));
  let cursor = 0;
  const occurrences = [...result.occurrences].sort((a, b) => a.start - b.start || b.end - a.end);
  for (const occurrence of occurrences) {
    const item = items.get(occurrence.item_id);
    if (!item || !Number.isInteger(occurrence.start) || !Number.isInteger(occurrence.end) || occurrence.start < cursor || occurrence.end <= occurrence.start || occurrence.end > chars.length) continue;
    container.append(document.createTextNode(chars.slice(cursor, occurrence.start).join("")));
    const unresolved = candidateLevels(item).length > 1;
    const highlight = element("button", `word-highlight level-${item.level.toLowerCase()}${unresolved ? " level-unresolved" : ""}${item.status !== "reference" || occurrence.uncertain || unresolved ? " is-estimate" : ""}`, chars.slice(occurrence.start, occurrence.end).join(""));
    highlight.type = "button";
    highlight.dataset.itemId = item.id;
    highlight.setAttribute("aria-pressed", "false");
    highlight.setAttribute("aria-label", `${occurrence.surface || item.lemma}，${levelLabel(item)}，${item.status === "reference" ? "有来源支持" : "估计"}。查看释义`);
    highlight.title = `${item.chinese || item.lemma} · ${levelLabel(item)}${item.status === "reference" ? " · 有来源支持" : " · 估计"}`;
    highlight.addEventListener("click", () => selectWord(item.id));
    container.append(highlight);
    cursor = occurrence.end;
  }
  container.append(document.createTextNode(chars.slice(cursor).join("")));
  $("preview-empty").hidden = true;
  container.hidden = false;
}

function renderTable() {
  const allItems = state.analysis ? state.analysis.items : [];
  const query = $("search-input").value.trim().toLocaleLowerCase();
  const items = allItems.filter((item) => {
    const matchesFilter = state.filter === "all" || candidateLevels(item).includes(state.filter) || (state.filter === "reference" && item.status === "reference");
    const matchesQuery = !query || [item.lemma, item.chinese, item.definition, ...(item.forms || [])].some((value) => String(value || "").toLocaleLowerCase().includes(query));
    return matchesFilter && matchesQuery;
  });
  const rows = items.map((item) => {
    const row = element("tr", state.selected === item.id ? "is-active-row" : "");
    row.dataset.itemId = item.id;
    const wordCell = element("td");
    wordCell.append(element("strong", "", item.lemma), element("span", "pos", item.pos || "—"));
    if (item.forms && item.forms.length) wordCell.append(element("div", "word-forms", `原文：${item.forms.join(" / ")}`));
    const levelCell = element("td");
    levelCell.append(levelBadge(item), element("span", `status-badge${item.status === "reference" ? " reference" : ""}`, item.status === "reference" ? "有来源支持" : "估计 · 未验证"));
    const source = referenceLink(item.source);
    if (source) levelCell.append(source);
    if (contextUncertain(item)) levelCell.append(element("span", "status-badge", "语境待核"));
    const definitionCell = element("td");
    definitionCell.append(element("p", "chinese-meaning", item.chinese || "—"), element("p", "item-notes", item.chinese_source || "中文学习注释／AI 辅助"), element("p", "english-definition", item.definition || "Wordset 暂无匹配定义"));
    const exampleCell = element("td");
    exampleCell.append(element("p", "example-sentence", item.example || "Wordset 暂无用例"));
    const exampleSource = referenceLink(item.example_source || item.definition_source, "Wordset 义项／用例 ↗");
    if (exampleSource) exampleCell.append(exampleSource);
    if (Array.isArray(item.dictionary_senses) && item.dictionary_senses.length) {
      const more = element("details", "table-senses");
      const count = item.dictionary_senses.reduce((sum, sense) => sum + (sense.examples || []).length, 0);
      more.append(element("summary", "", `${item.dictionary_senses.length} 个义项 · ${count} 条用例`), dictionarySenses(item.dictionary_senses));
      exampleCell.append(more);
    }
    if (item.ai_example || item.ai_definition) exampleCell.append(aiAssistance(item));
    if (item.notes) exampleCell.append(element("p", "item-notes", item.notes));
    row.append(wordCell, levelCell, definitionCell, exampleCell, element("td", "word-count-cell", item.count || 0));
    return row;
  });
  $("vocabulary-body").replaceChildren(...rows);
  $("table-empty").hidden = items.length > 0;
  if (!items.length && state.analysis) {
    $("table-empty").replaceChildren(element("span", "", "⌁"), element("p", "", allItems.length ? "没有符合筛选条件的词汇。" : "这段文本中没有匹配到当前词库的词汇。"), element("span", "", allItems.length ? "试试其他等级或搜索词。" : "这不代表文本没有进阶词汇；可开启估计，或添加更完整的合法参考词库。"));
  }
  $("table-count").textContent = state.analysis ? `显示 ${items.length} / ${allItems.length} 个词汇` : "尚无词汇";
}

function renderAnalysis() {
  const result = state.analysis;
  state.stale = false;
  const unresolvedCount = result.items.filter((item) => candidateLevels(item).length > 1).length;
  $("c1-count").textContent = result.items.filter((item) => candidateLevels(item).length === 1 && candidateLevels(item)[0] === "C1").length;
  $("c2-count").textContent = result.items.filter((item) => candidateLevels(item).length === 1 && candidateLevels(item)[0] === "C2").length;
  $("occurrence-count").textContent = `${result.occurrences.length} 处匹配${unresolvedCount ? ` · ${unresolvedCount} 词待核` : ""}`;
  $("occurrence-count").title = unresolvedCount ? "C1 / C2 义项待核的词汇未计入单一等级统计。" : "原文中的词汇匹配总次数。";
  $("vocabulary-count").textContent = result.items.length;
  $("result-status").textContent = result.ai_used ? "CONTEXT ENRICHED" : "READING NOTES READY";
  $("selected-word").hidden = true;
  state.selected = null;
  renderHighlights();
  renderTable();
  warnings(result.warnings || []);
}

async function analyze() {
  if (state.busy) return;
  const text = $("text-input").value;
  if (!text.trim()) { message("先粘贴一段英文，或上传一份文档。", true); $("text-input").focus(); return; }
  if (Array.from(text).length > 100000) { message("文本过长，请将内容控制在 100,000 个字符以内。", true); return; }
  message("");
  updateBusy(true);
  try {
    const response = await request("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, use_ai: $("ai-toggle").checked, include_estimates: $("estimate-toggle").checked }) });
    state.analysis = await response.json();
    renderAnalysis();
  } catch (error) { message(error.message || "分析失败，请检查服务后重试。", true); }
  finally { updateBusy(false); }
}

function switchTab(tab) {
  const upload = tab === "file";
  $("text-tab").classList.toggle("active", !upload);
  $("file-tab").classList.toggle("active", upload);
  $("text-tab").setAttribute("aria-selected", String(!upload));
  $("file-tab").setAttribute("aria-selected", String(upload));
  $("file-input-panel").hidden = !upload;
  // Extracted text remains editable in document mode.
  $("text-input-panel").hidden = false;
}

async function uploadFile(file) {
  if (!file || state.busy) return;
  const extension = file.name.split(".").pop().toLowerCase();
  if (!["docx", "pdf"].includes(extension)) { message("请选择 DOCX 或 PDF 文件。", true); return; }
  if (file.size > 10 * 1024 * 1024) { message("文件超过 10 MB 限制，请选择更小的文件。", true); return; }
  switchTab("file");
  message("");
  $("file-status").textContent = `正在提取 ${file.name} 中的文本…`;
  updateBusy(true, "正在读取文档…");
  const data = new FormData();
  data.append("file", file);
  data.append("ocr", String($("ocr-toggle").checked));
  try {
    const response = await request("/api/documents", { method: "POST", body: data });
    const result = await response.json();
    $("text-input").value = result.text;
    updateCounts();
    $("file-status").textContent = `已读取 ${file.name} · 请检查提取结果，然后开始分析。`;
    warnings(result.warnings || []);
    $("text-input").focus();
  } catch (error) { $("file-status").textContent = ""; message(error.message || "文档读取失败。", true); }
  finally { updateBusy(false); $("file-input").value = ""; }
}

async function exportFile(format) {
  if (!state.analysis || state.busy || state.stale) return;
  message("");
  updateBusy(true, "正在整理阅读笔记…");
  try {
    const response = await request(`/api/export/${format}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ analysis: state.analysis }) });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = element("a");
    anchor.href = url;
    anchor.download = `LexiScope-reading-notes.${format}`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    message(format === "csv" ? "词汇列表已导出为 CSV，可用 Excel 打开。" : "注释笔记已导出，包含重新排版的原文和词汇表。");
  } catch (error) { message(error.message || "导出失败，请稍后重试。", true); }
  finally { updateBusy(false); }
}

$("text-input").addEventListener("input", updateCounts);
$("sample-button").addEventListener("click", () => { $("text-input").value = sampleText; updateCounts(); $("text-input").focus(); message(""); });
$("clear-button").addEventListener("click", () => { $("text-input").value = ""; updateCounts(); $("text-input").focus(); });
$("analyze-button").addEventListener("click", analyze);
$("text-input").addEventListener("keydown", (event) => { if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); analyze(); } });
$("text-tab").addEventListener("click", () => switchTab("text"));
$("file-tab").addEventListener("click", () => switchTab("file"));
$("file-input").addEventListener("change", (event) => uploadFile(event.target.files[0]));
$("dropzone").addEventListener("dragover", (event) => { event.preventDefault(); if (!state.busy) $("dropzone").classList.add("drag-over"); });
$("dropzone").addEventListener("dragleave", () => $("dropzone").classList.remove("drag-over"));
$("dropzone").addEventListener("drop", (event) => { event.preventDefault(); $("dropzone").classList.remove("drag-over"); uploadFile(event.dataTransfer.files[0]); });
$("ai-toggle").addEventListener("change", () => { $("ai-disclosure").hidden = !$("ai-toggle").checked; });
$("search-input").addEventListener("input", renderTable);
document.querySelectorAll(".filter-button").forEach((button) => { button.addEventListener("click", () => { state.filter = button.dataset.filter; document.querySelectorAll(".filter-button").forEach((entry) => { entry.classList.toggle("active", entry === button); entry.setAttribute("aria-pressed", String(entry === button)); }); renderTable(); }); });
document.querySelectorAll(".export-button").forEach((button) => button.addEventListener("click", () => exportFile(button.dataset.format)));
$("about-button").addEventListener("click", () => $("about-dialog").showModal());
$("close-dialog").addEventListener("click", () => $("about-dialog").close());
$("acknowledge-dialog").addEventListener("click", () => $("about-dialog").close());
$("about-dialog").addEventListener("click", (event) => { if (event.target === $("about-dialog")) { const bounds = event.target.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) event.target.close(); } });

async function initialize() {
  updateCounts();
  try {
    const response = await request("/api/health");
    const health = await response.json();
    state.aiConfigured = Boolean(health.ai_configured);
    $("ai-toggle").disabled = !state.aiConfigured;
    $("ai-status").textContent = state.aiConfigured ? "已配置" : "未配置";
    $("ai-status").title = state.aiConfigured ? "启用后原文将发送至配置的 AI 服务。" : "在服务器设置 AI_API_KEY 等配置后可使用；基础分析无需密钥。";
    $("ocr-status").textContent = health.ocr_available ? "（可用）" : "（服务器尚未启用）";
  } catch (_) {
    $("ai-toggle").disabled = true;
    $("ai-status").textContent = "服务未连接";
    message("暂时无法连接分析服务。请确认后端已启动后刷新页面。", true);
  }
}

async function loadPersonalDictionary() {
  try {
    const response = await request("/api/dictionary");
    const data = await response.json();
    const labels = {
      headwords: "词头", unique_headwords: "词头", entries: "词条", total_entries: "词条",
      matched_wordset_headwords: "匹配 Wordset 的词头", wordset_matched_headwords: "匹配 Wordset 的词头",
      headwords_with_examples: "有用例的词头", words_with_examples: "有用例的词头",
      senses: "英文义项", wordset_senses: "英文义项", examples: "原始用例", example_count: "原始用例"
    };
    const stats = Object.entries(data.coverage || {}).filter(([key, value]) => labels[key] && typeof value === "number");
    $("dictionary-coverage").replaceChildren(...stats.map(([key, value]) => element("span", "coverage-stat", `${labels[key]}：${value.toLocaleString()}`)));
    if (!stats.length) $("dictionary-coverage").textContent = data.name || "本地组合词典已就绪";
    const links = Object.values(data.sources || {}).map((source) => referenceLink(source)).filter(Boolean);
    $("dictionary-sources").replaceChildren(...links);
  } catch (_) { $("dictionary-coverage").textContent = "词典尚未连接，请确认后端与组合词典数据已安装。"; }
}

$("dictionary-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const word = $("dictionary-query").value.trim();
  if (!word) return;
  $("dictionary-search").disabled = true;
  $("dictionary-message").textContent = "正在查询…";
  $("dictionary-result").hidden = true;
  try {
    const response = await request(`/api/dictionary/lookup?word=${encodeURIComponent(word)}`);
    const entry = await response.json();
    const result = $("dictionary-result");
    result.replaceChildren(element("h3", "", entry.word), element("p", "", (entry.cefr || []).map((record) => `${record.pos || "词性待核"} · ${record.level}${record.notes ? ` · ${record.notes}` : ""}`).join("；")), element("p", "item-notes", "等级：Octanove；英文定义和用例：Wordset。义项与等级对应仍需核对。"), dictionarySenses(entry.senses || []));
    result.hidden = false;
    $("dictionary-message").textContent = "";
  } catch (error) { $("dictionary-message").textContent = error.message || "词典中没有找到此词条。"; }
  finally { $("dictionary-search").disabled = false; }
});

initialize();
loadPersonalDictionary();
