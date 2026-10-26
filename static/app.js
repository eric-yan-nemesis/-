"use strict";

const $ = (id) => document.getElementById(id);
const sampleText = "Meticulous researchers scrutinized the pervasive problem. Their candid report revealed the inherent complexity.\n\nA plausible plan could alleviate the detrimental effects and help resilient communities. The committee concurred, although its enthusiasm was ephemeral. Further scrutiny could alleviate the risks.";
const state = { analysis: null, filter: "all", selected: null, busy: false, stale: false, aiConfigured: false, inputMode: "text", readingText: "", translationText: "", translating: false, translationToken: 0, translationController: null, nativeTranslator: null, speaking: false, paused: false, speechSession: 0, utterance: null };
const speechEngine = window.speechSynthesis;

function activeText() {
  return state.inputMode === "file" ? $("document-text").value : $("text-input").value;
}

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
  const text = activeText();
  if (state.readingText !== text) invalidateReading(text);
  $("word-count").textContent = (text.match(/[A-Za-z]+(?:['’-][A-Za-z]+)*/g) || []).length.toLocaleString();
  $("character-count").textContent = Array.from(text).length.toLocaleString();
  $("document-stats").textContent = `${Array.from(text).length.toLocaleString()} 字符`;
  state.stale = Boolean(state.analysis && state.analysis.text !== text);
  if (state.analysis) $("result-status").textContent = state.stale ? "TEXT CHANGED · REANALYZE" : (state.analysis.ai_used ? "CONTEXT ENRICHED" : "READING NOTES READY");
  document.querySelectorAll(".export-button").forEach((button) => { button.disabled = state.busy || !state.analysis || state.stale; });
  updateReadingControls();
}

function updateBusy(busy, label = "正在理解你的文本…") {
  state.busy = busy;
  $("analyze-button").disabled = busy;
  $("analyze-button").classList.toggle("is-loading", busy);
  $("analyze-button-label").textContent = busy ? label : "发现进阶词汇";
  ["sample-button", "clear-button", "file-input", "text-input", "document-text", "estimate-toggle", "text-tab", "file-tab"].forEach((id) => { $(id).disabled = busy; });
  $("ai-toggle").disabled = busy || !state.aiConfigured;
  document.querySelectorAll(".export-button").forEach((button) => { button.disabled = busy || !state.analysis || state.stale; });
  $("workspace").setAttribute("aria-busy", String(busy));
  updateReadingControls();
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
    details.append(element("p", "sense-synonyms", (sense.synonyms || []).length ? `同义词参考：${sense.synonyms.join(" · ")}` : "Wordset 暂无本义项同义词"));
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
    const matchesQuery = !query || [item.lemma, item.chinese, item.definition, ...(item.forms || []), ...(item.dictionary_senses || []).flatMap((sense) => sense.synonyms || [])].some((value) => String(value || "").toLocaleLowerCase().includes(query));
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
    if ((item.synonyms || []).length) definitionCell.append(element("p", "sense-synonyms", `同义词参考：${item.synonyms.join(" · ")}（需核对语境）`));
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
  const text = activeText();
  if (!text.trim()) { message(state.inputMode === "file" ? "先选择一份 DOCX 或 PDF 文档。" : "先粘贴一段英文。", true); $(state.inputMode === "file" ? "file-input" : "text-input").focus(); return; }
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
  state.inputMode = upload ? "file" : "text";
  $("text-tab").classList.toggle("active", !upload);
  $("file-tab").classList.toggle("active", upload);
  $("text-tab").setAttribute("aria-selected", String(!upload));
  $("file-tab").setAttribute("aria-selected", String(upload));
  $("file-input-panel").hidden = !upload;
  $("text-input-panel").hidden = upload;
  updateCounts();
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
    $("document-text").value = result.text;
    $("document-preview").hidden = !result.text;
    $("document-preview").open = false;
    updateCounts();
    $("file-status").textContent = `已读取 ${file.name} · 可直接分析，或展开下方校正提取文本。`;
    warnings(result.warnings || []);
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
$("document-text").addEventListener("input", updateCounts);
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
    $("translation-ai-option").disabled = !state.aiConfigured;
    $("translation-ai-option").textContent = state.aiConfigured ? "AI 全文翻译（已配置）" : "AI 全文翻译（未配置密钥）";
    updateReadingControls();
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
      senses: "英文义项", wordset_senses: "英文义项", examples: "原始用例", example_count: "原始用例", headwords_with_synonyms: "有同义词的词头"
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

function updateReadingControls() {
  const hasText = Boolean(activeText().trim());
  const method = $("translation-method").value;
  $("translate-button").hidden = method === "web";
  $("translate-button").disabled = !hasText || (method === "ai" && !state.aiConfigured) || state.translating || state.busy;
  $("translate-button").textContent = state.translating ? "正在分段翻译…" : "翻译成中文";
  $("translation-web-panel").hidden = method !== "web";
  $("translation-disclosure").textContent = method === "browser" ? "使用 Chrome 本机英译中，首次可能需要下载语言模型；本网站不会把原文发送给 AI 接口。不支持时可选择 Google 官方网页翻译。" : method === "web" ? "点击下方链接，在新标签页使用 Google 官方翻译，无需 API 密钥。仅把当前所选段落发送给 Google；长文请逐段翻译。" : "点击翻译会将当前原文发送到后端配置的 AI 服务；需要 AI_API_KEY。译文请结合原文核对。";
  $("translation-web-link").hidden = !hasText;
  $("translated-speech-option").disabled = !state.translationText;
  const supported = Boolean(speechEngine && window.SpeechSynthesisUtterance);
  const speakText = $("speech-source").value === "translation" ? state.translationText : activeText();
  $("speech-start").disabled = !supported || !speakText.trim() || state.speaking || state.busy;
  $("speech-pause").disabled = !state.speaking;
  $("speech-pause").textContent = state.paused ? "继续" : "暂停";
  $("speech-stop").disabled = !state.speaking;
  ["speech-source", "speech-voice", "speech-rate"].forEach((id) => { $(id).disabled = state.speaking || !supported; });
  if (!supported) $("speech-status").textContent = "当前浏览器不支持系统朗读，请使用新版 Safari 或 Chrome。";
}

function stopSpeech(showStatus = true) {
  state.speechSession += 1;
  const wasSpeaking = state.speaking;
  state.speaking = false;
  state.paused = false;
  state.utterance = null;
  if (speechEngine && wasSpeaking) speechEngine.cancel();
  if (showStatus && wasSpeaking) $("speech-status").textContent = "朗读已停止。";
  updateReadingControls();
}

function invalidateReading(text) {
  state.readingText = text;
  state.translationToken += 1;
  if (state.translationController) state.translationController.abort();
  state.translationController = null;
  if (state.nativeTranslator) { try { state.nativeTranslator.destroy(); } catch (_) {} state.nativeTranslator = null; }
  state.translating = false;
  state.translationText = "";
  $("translation-output").textContent = "";
  $("translation-panel").hidden = true;
  $("translation-status").textContent = "";
  $("manual-translation").value = "";
  $("translation-segment").value = "0";
  updateWebTranslation();
  $("speech-source").value = "original";
  stopSpeech();
  loadVoices();
}

async function translateReading() {
  const text = activeText();
  const method = $("translation-method").value;
  if (!text.trim() || state.translating || state.busy || method === "web" || (method === "ai" && !state.aiConfigured)) return;
  const token = ++state.translationToken;
  const controller = new AbortController();
  state.translationController = controller;
  state.translating = true;
  $("translation-status").textContent = "正在翻译当前材料，较长文档会分段处理，请稍候。";
  updateReadingControls();
  try {
    let result;
    if (method === "browser") {
      result = { translation: await nativeTranslation(text, token, controller.signal) };
    } else {
      const response = await request("/api/translate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }), signal: controller.signal });
      result = await response.json();
    }
    if (token !== state.translationToken || text !== activeText()) return;
    if (typeof result.translation !== "string" || !result.translation.trim()) throw new Error("没有收到有效译文，请重试。");
    state.translationText = result.translation;
    $("translation-output").textContent = result.translation;
    $("translation-panel").hidden = false;
    $("translation-origin").textContent = method === "browser" ? "Chrome 本机翻译·待核对" : "AI 辅助·待核对";
    $("translation-status").textContent = "翻译完成。自动译文可能有误，请结合原文核对；可选择朗读中文译文。";
  } catch (error) {
    if (token === state.translationToken && error.name !== "AbortError") $("translation-status").textContent = error.message || "翻译失败，请重试。";
    if (token === state.translationToken && method === "browser" && error.name !== "AbortError") {
      $("translation-method").value = "web";
      $("translation-status").textContent += " 可点击下方链接改用 Google 官方翻译，无需密钥。";
      updateWebTranslation();
    }
  } finally {
    if (token === state.translationToken) {
      state.translating = false;
      state.translationController = null;
      updateReadingControls();
    }
  }
}

function readingSegments(text) {
  const chunks = [];
  while (text.length > 1500) {
    let end = text.lastIndexOf("\n", 1500);
    if (end < 750) end = text.lastIndexOf(" ", 1500);
    if (end < 750) end = 1500; else end += 1;
    // Preserve astral characters at a hard boundary.
    if (/[\uD800-\uDBFF]/u.test(text[end - 1])) end -= 1;
    chunks.push(text.slice(0, end)); text = text.slice(end);
  }
  if (text) chunks.push(text);
  return chunks;
}

function updateWebTranslation() {
  const chunks = readingSegments(activeText());
  const previous = Number($("translation-segment").value) || 0;
  const index = Math.min(previous, Math.max(chunks.length - 1, 0));
  $("translation-segment").replaceChildren(...chunks.map((_, i) => {
    const option = element("option", "", `第 ${i + 1} / ${chunks.length} 段`); option.value = String(i); return option;
  }));
  $("translation-segment").value = String(index);
  $("translation-segment-label").hidden = chunks.length <= 1;
  $("translation-segment-status").textContent = chunks.length ? `当前为第 ${index + 1} / ${chunks.length} 段。${chunks.length > 1 ? "请逐段打开，未自动翻译整篇。" : "将打开这段材料的中文翻译。"}` : "请先粘贴文本或上传文档。";
  $("translation-segment-preview").textContent = chunks[index] || "";
  $("translation-web-link").hidden = !activeText().trim();
  if (chunks[index]) {
    const url = new URL("https://translate.google.com/");
    url.search = new URLSearchParams({sl:"en",tl:"zh-CN",text:chunks[index],op:"translate"}).toString();
    $("translation-web-link").href = url.href;
    $("translation-web-link").textContent = chunks.length > 1 ? `打开 Google 翻译第 ${index + 1} 段 ↗` : "打开 Google 英译中 ↗";
  } else $("translation-web-link").removeAttribute("href");
}

async function nativeTranslation(text, token, signal) {
  if (!window.Translator) throw new Error("当前浏览器未提供本机翻译。");
  const options = {sourceLanguage:"en",targetLanguage:"zh"};
  const availability = await window.Translator.availability(options);
  if (availability === "unavailable") throw new Error("当前 Chrome 暂不支持本机英译中。");
  if (signal.aborted) throw new DOMException("已取消", "AbortError");
  const translator = await window.Translator.create({...options,signal,monitor(monitor) {
    monitor.addEventListener("downloadprogress", () => {
      if (token === state.translationToken) $("translation-status").textContent = "Chrome 正在下载本机翻译语言模型，请保持页面打开…";
    });
  }});
  try {
    if (signal.aborted || token !== state.translationToken) throw new DOMException("已取消", "AbortError");
    state.nativeTranslator = translator;
    const chunks = readingSegments(text), output = [];
    for (let i = 0; i < chunks.length; i += 1) {
      if (signal.aborted || token !== state.translationToken) throw new DOMException("已取消", "AbortError");
      $("translation-status").textContent = `正在本机翻译 · ${i + 1} / ${chunks.length}`;
      const translated = await translator.translate(chunks[i],{signal});
      if (typeof translated !== "string" || !translated.trim()) throw new Error("本机翻译没有返回有效内容。");
      output.push(translated);
    }
    return output.join("\n\n");
  } finally {
    try { translator.destroy(); } catch (_) {}
    if (state.nativeTranslator === translator) state.nativeTranslator = null;
  }
}

function loadVoices() {
  if (!speechEngine || state.speaking) return;
  const language = $("speech-source").value === "translation" ? "zh" : "en";
  const selected = $("speech-voice").value;
  const voices = speechEngine.getVoices().filter((voice) => voice.lang.toLowerCase().startsWith(language));
  voices.sort((a, b) => Number(b.localService) - Number(a.localService));
  const options = [element("option", "", `系统默认${language === "en" ? "英语" : "中文"}声音`)];
  options[0].value = "";
  for (const voice of voices) {
    const option = element("option", "", `${voice.name} · ${voice.lang}${voice.localService ? " · 本机" : " · 可能联网"}`);
    option.value = voice.voiceURI;
    options.push(option);
  }
  $("speech-voice").replaceChildren(...options);
  $("speech-voice").value = voices.some((voice) => voice.voiceURI === selected) ? selected : (voices.find((voice) => voice.localService)?.voiceURI || "");
}

function speechChunks(text) {
  const chars = Array.from(text.trim());
  const chunks = [];
  let offset = 0;
  while (offset < chars.length) {
    let size = Math.min(230, chars.length - offset);
    if (offset + size < chars.length) {
      let boundary = -1;
      for (let i = size - 1; i >= size / 2; i -= 1) {
        if (/[.!?。！？\n]/u.test(chars[offset + i])) { boundary = i + 1; break; }
      }
      const space = chars.slice(offset, offset + size).lastIndexOf(" ");
      if (boundary > 0) size = boundary;
      else if (space > size / 2) size = space + 1;
    }
    const chunk = chars.slice(offset, offset + size).join("").trim();
    if (chunk) chunks.push(chunk);
    offset += size;
  }
  return chunks;
}

function startSpeech() {
  if (!speechEngine || !window.SpeechSynthesisUtterance || state.speaking) return;
  const translated = $("speech-source").value === "translation";
  const chunks = speechChunks(translated ? state.translationText : activeText());
  if (!chunks.length) return;
  const session = ++state.speechSession;
  const voice = speechEngine.getVoices().find((entry) => entry.voiceURI === $("speech-voice").value);
  state.speaking = true;
  state.paused = false;
  updateReadingControls();
  const speak = (index) => {
    if (session !== state.speechSession) return;
    if (index >= chunks.length) {
      state.speaking = false;
      state.utterance = null;
      $("speech-status").textContent = "朗读完成。";
      updateReadingControls();
      return;
    }
    const utterance = new SpeechSynthesisUtterance(chunks[index]);
    utterance.lang = translated ? "zh-CN" : "en-US";
    if (voice) utterance.voice = voice;
    utterance.rate = Number($("speech-rate").value);
    utterance.onend = () => speak(index + 1);
    utterance.onerror = () => {
      if (session !== state.speechSession) return;
      stopSpeech(false);
      $("speech-status").textContent = "此声音暂时无法朗读，请换一个声音，或在系统设置中安装所需语言的语音。";
    };
    state.utterance = utterance;
    $("speech-status").textContent = `正在朗读${translated ? "中文译文" : "英文原文"} · ${index + 1} / ${chunks.length}`;
    try { speechEngine.speak(utterance); } catch (_) { utterance.onerror(); }
  };
  speak(0);
}

$("translate-button").addEventListener("click", translateReading);
$("translation-method").addEventListener("change", () => { invalidateReading(activeText()); updateReadingControls(); });
$("translation-segment").addEventListener("change", updateWebTranslation);
$("accept-translation").addEventListener("click", () => {
  const value = $("manual-translation").value.trim();
  if (!activeText().trim() || !value) { $("translation-status").textContent = "请先放入原文，再粘贴中文译文。"; return; }
  stopSpeech();
  state.translationText = value;
  $("translation-output").textContent = value;
  $("translation-origin").textContent = "手动导入·请核对";
  $("translation-panel").hidden = false;
  $("translation-status").textContent = "已载入你粘贴的译文；是否覆盖全部原文需要自行核对。现在可以朗读中文译文。";
  updateReadingControls();
});
$("speech-start").addEventListener("click", startSpeech);
$("speech-stop").addEventListener("click", () => stopSpeech());
$("speech-pause").addEventListener("click", () => {
  if (!state.speaking || !speechEngine) return;
  state.paused = !state.paused;
  if (state.paused) speechEngine.pause(); else speechEngine.resume();
  $("speech-status").textContent = state.paused ? "朗读已暂停，点击继续。" : "正在继续朗读…";
  updateReadingControls();
});
$("speech-source").addEventListener("change", () => { stopSpeech(); loadVoices(); updateReadingControls(); });
if (speechEngine) speechEngine.addEventListener("voiceschanged", loadVoices);
window.addEventListener("pagehide", () => { stopSpeech(false); if (state.translationController) state.translationController.abort(); });
const nativeSupported = Boolean(window.Translator && window.Translator.create && window.Translator.availability);
$("translation-native-option").disabled = !nativeSupported;
if (nativeSupported) $("translation-method").value = "browser";
updateWebTranslation();
loadVoices();
initialize();
loadPersonalDictionary();
