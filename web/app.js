const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const titles = {
  inbox: "PR Inbox",
  review: "New Review",
  workspace: "Review Workspace",
  packs: "Review Packs",
  benchmark: "Benchmark Lab",
};
const stateLabels = {
  PENDING: "等待中", PLANNING: "范围分析", EXECUTING: "验证中",
  REVIEWING: "汇总中", SUCCESS: "已完成", FAILED: "失败", CANCELLED: "已取消",
};
const feedbackLabels = { false_positive: "误报", missed_issue: "漏报", bad_fix: "坏修复", accepted: "已接受" };
let selectedTask = null;
let selectedTaskData = null;
let accessToken = localStorage.getItem("diffprism_token") || localStorage.getItem("evoagent_token") || "";
let toastTimer = null;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = value == null ? "" : String(value);
  return node.innerHTML;
}

function formatTime(value) {
  if (!value) return "时间未知";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  }).format(date);
}

function formatJson(value) { return JSON.stringify(value, null, 2); }

function renderDiagnosticJson(value) { $("#task-report").textContent = formatJson(value); }

function listValues(value) {
  if (Array.isArray(value)) return value.length ? value.map((item) => typeof item === "object" ? formatJson(item) : String(item)) : ["None recorded"];
  if (value && typeof value === "object") return Object.entries(value).map(([key, item]) => `${key}: ${typeof item === "object" ? formatJson(item) : item}`);
  return [value || "None recorded"];
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const response = await fetch(path, { ...options, headers });
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("json") ? await response.json() : await response.text();
  if (response.status === 401) {
    $("#login-overlay").classList.remove("hidden");
    $("#logout").classList.add("hidden");
  }
  if (!response.ok) {
    const plain = typeof data === "string" && !/<[a-z][\s\S]*>/i.test(data) ? data.trim() : "";
    throw new Error((typeof data === "object" ? data.error || data.detail : plain) || `请求失败 (${response.status})`);
  }
  return data;
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), 2600);
}

function setButtonBusy(button, busy, text) {
  if (!button) return;
  if (busy) {
    button.dataset.label = button.textContent;
    button.textContent = text;
    button.disabled = true;
  } else {
    button.disabled = false;
    if (button.dataset.label) button.textContent = button.dataset.label;
  }
  button.setAttribute("aria-busy", String(busy));
}

function show(view, updateHash = true) {
  if (!titles[view]) view = "inbox";
  $$(".view").forEach((item) => item.classList.toggle("active", item.id === `view-${view}`));
  $$(".nav-item").forEach((item) => {
    const active = item.dataset.view === view;
    item.classList.toggle("active", active);
    item.setAttribute("aria-current", active ? "page" : "false");
  });
  $("#page-title").textContent = titles[view];
  document.title = `${titles[view]} · DiffPrism`;
  if (updateHash) history.replaceState(null, "", `#${view}`);
  if (view === "workspace") loadTasks();
  if (view === "packs") loadSkills();
  if (view === "benchmark") loadBenchmark();
  window.scrollTo({ top: 0, behavior: reduceMotion.matches ? "auto" : "smooth" });
}

function taskRows(tasks) {
  if (!tasks?.length) return '<div class="empty-list">还没有审查任务。先提交一个 diff。</div>';
  return tasks.map((task) => {
    const state = String(task.state || "PENDING").toUpperCase();
    const pr = task.pull_request ? `PR #${task.pull_request}` : "MANUAL DIFF";
    return `<button class="task-row" data-task="${escapeHtml(task.id)}" type="button">
      <span class="task-main"><span class="task-glyph">PR</span><span><strong>${escapeHtml(task.repository || "未命名仓库")}</strong><small>${escapeHtml(pr)} · ${escapeHtml(formatTime(task.created_at))}</small></span></span>
      <span class="status state-${escapeHtml(state.toLowerCase())}">${escapeHtml(stateLabels[state] || state)}</span>
    </button>`;
  }).join("");
}

function bindTasks(root) {
  $$("[data-task]", root).forEach((row) => row.addEventListener("click", () => openTask(row.dataset.task)));
}

function statCard(label, value, note) {
  return `<article class="stat"><p>${escapeHtml(label)}</p><b>${escapeHtml(value)}</b><small>${escapeHtml(note)}</small></article>`;
}

async function loadDashboard() {
  try {
    const data = await api("/api/dashboard");
    $("#system-status").textContent = `${data.queue || "runtime"} · ${data.orchestrator || "DiffPrism"}`;
    const mode = $("#review-mode");
    mode.disabled = !data.llm?.enabled;
    mode.title = data.llm?.enabled ? "" : "需要配置模型后运行 agentic 审查";
    const stats = data.stats || {};
    const rate = `${Math.round(Number(stats.success_rate || 0) * 100)}%`;
    $("#stats").innerHTML = [
      statCard("TOTAL REVIEWS", stats.tasks_total ?? 0, "累计任务"),
      statCard("VERIFIED", stats.tasks_success ?? 0, "完成证据门禁"),
      statCard("SUCCESS RATE", rate, "任务执行成功率"),
      statCard("OPEN SIGNALS", stats.unresolved_failure_cases ?? 0, "待回放反馈"),
    ].join("");
    $("#recent-tasks").innerHTML = taskRows((data.tasks || []).slice(0, 6));
    bindTasks($("#recent-tasks"));
  } catch (error) {
    $("#system-status").textContent = "服务连接异常";
    $("#stats").innerHTML = '<div class="empty-list">无法读取工作区数据。</div>';
    $("#recent-tasks").innerHTML = '<div class="empty-list">任务加载失败。</div>';
    toast(error.message);
  }
}

async function loadTasks() {
  const root = $("#all-tasks");
  root.innerHTML = '<div class="skeleton row"></div>';
  try {
    const data = await api("/api/tasks");
    root.innerHTML = taskRows(data.tasks || []);
    bindTasks(root);
  } catch (error) {
    root.innerHTML = '<div class="empty-list">任务加载失败。</div>';
    toast(error.message);
  }
}

function findingCard(finding, index) {
  const severity = String(finding?.severity || "medium").toLowerCase();
  const verification = finding?.verification || "verified";
  return `<article class="finding-card severity-${escapeHtml(severity)}">
    <header><span class="finding-number">#${index + 1}</span><div><strong>${escapeHtml(finding?.title || "Untitled finding")}</strong><p>${escapeHtml(finding?.rule_id || "UNCLASSIFIED")} · ${escapeHtml(severity.toUpperCase())}</p></div><span class="status state-success">${escapeHtml(verification)}</span></header>
    <p class="finding-location">${escapeHtml(finding?.path || "unknown")}:${escapeHtml(finding?.line || "?")}</p>
    <dl><dt>Trigger</dt><dd>${escapeHtml(finding?.trigger || "Not established")}</dd><dt>Evidence</dt><dd><code>${escapeHtml(finding?.evidence || "Not established")}</code></dd><dt>Impact</dt><dd>${escapeHtml(finding?.impact || finding?.explanation || "Not established")}</dd><dt>Suggested fix</dt><dd>${escapeHtml(finding?.fix || "Not provided")}</dd><dt>Suggested verification</dt><dd>${escapeHtml(finding?.test || "Not provided")}</dd></dl>
    ${finding?.examiner_reason ? `<p class="examiner-note"><b>Examiner:</b> ${escapeHtml(finding.examiner_reason)}</p>` : ""}
  </article>`;
}

function keyValueRows(value) {
  const entries = value && typeof value === "object" ? Object.entries(value) : [];
  if (!entries.length) return '<p class="muted">No structured data recorded.</p>';
  return `<dl class="fact-list">${entries.map(([key, item]) => `<dt>${escapeHtml(key.replaceAll("_", " "))}</dt><dd>${listValues(item).map(escapeHtml).join("<br>")}</dd>`).join("")}</dl>`;
}

function renderReviewWorkspace(task) {
  const report = task?.report || null;
  $("#workspace-empty").classList.add("hidden");
  $("#workspace-report").classList.remove("hidden");
  $("#workspace-identity").innerHTML = `<p class="eyebrow">${escapeHtml(task?.id || "TASK")}</p><h2>${escapeHtml(task?.repository || "Unknown repository")}</h2><p>${task?.pull_request ? `Pull Request #${escapeHtml(task.pull_request)}` : "Manual diff review"} · ${escapeHtml(formatTime(task?.created_at))}</p>`;
  const state = String(task?.state || "PENDING").toUpperCase();
  const stateNode = $("#workspace-state");
  stateNode.className = `status state-${state.toLowerCase()}`;
  stateNode.textContent = stateLabels[state] || state;
  $("#create-fix").classList.toggle("hidden", !(report && task?.pull_request));
  renderDiagnosticJson(task);

  if (!report) {
    $("#verdict-card").innerHTML = '<p class="eyebrow">VERDICT</p><h3>Review in progress</h3><p class="muted">结构化报告将在任务完成后出现。</p>';
    $("#change-map").innerHTML = '<p class="eyebrow">CHANGE MAP</p><h3>Pending</h3><p class="muted">Scope Mapper 尚未提交范围。</p>';
    $("#finding-list").innerHTML = '<div class="empty-list">没有可显示的已验证发现。</div>';
    $("#finding-count").textContent = "0";
    $("#agent-trail").innerHTML = '<p class="eyebrow">AGENT TRAIL</p><h3>Runtime trace</h3>' + keyValueRows(task?.trace || []);
    $("#execution-facts").innerHTML = '<p class="eyebrow">EXECUTION</p><h3>Pending</h3>';
    $("#feedback-panel").classList.add("hidden");
    return;
  }

  const verdict = report.verdict || {};
  const decision = String(verdict.decision || (report.findings?.length ? "review" : "pass")).toLowerCase();
  $("#verdict-card").innerHTML = `<p class="eyebrow">MERGE VERDICT</p><div class="verdict-line"><h3>${escapeHtml(decision.toUpperCase())}</h3><span class="verdict-badge verdict-${escapeHtml(decision)}">${escapeHtml(report.risk || "unknown risk")}</span></div><p>${escapeHtml(verdict.reason || report.summary || "No rationale recorded")}</p>${verdict.required_actions ? `<h4>Required actions</h4><ul>${listValues(verdict.required_actions).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}`;
  $("#change-map").innerHTML = '<p class="eyebrow">CHANGE MAP</p><h3>Impact surface</h3>' + keyValueRows(report.change_map);
  const findings = Array.isArray(report.findings) ? report.findings : [];
  $("#finding-count").textContent = String(findings.length);
  $("#finding-list").innerHTML = findings.length ? findings.map(findingCard).join("") : '<div class="empty-list success-empty">Evidence Examiner did not verify an actionable defect.</div>';
  const trail = Array.isArray(task.trace) ? task.trace : [];
  $("#agent-trail").innerHTML = `<p class="eyebrow">AGENT TRAIL</p><h3>Review progression</h3><ol class="trail">${trail.map((item) => `<li><b>${escapeHtml(item.state || "STEP")}</b><span>${escapeHtml(item.message || "")}</span><small>${escapeHtml(formatTime(item.created_at))}</small></li>`).join("") || "<li>No trace recorded.</li>"}</ol>`;
  $("#execution-facts").innerHTML = '<p class="eyebrow">EXECUTION FACTS</p><h3>Runtime evidence</h3>' + keyValueRows(report.execution);
  $("#feedback-panel").classList.toggle("hidden", task.state !== "SUCCESS");
  populateFeedbackFindings(findings);
}

async function openTask(id) {
  show("workspace");
  try {
    const task = await api(`/v1/tasks/${encodeURIComponent(id)}`);
    selectedTask = id;
    selectedTaskData = task;
    renderReviewWorkspace(task);
    if (task.state === "SUCCESS" && task.report) await loadTaskFeedback(id);
  } catch (error) {
    $("#workspace-empty").classList.remove("hidden");
    $("#workspace-empty").innerHTML = `<h3>无法打开任务</h3><p>${escapeHtml(error.message)}</p>`;
    $("#workspace-report").classList.add("hidden");
  }
}

function populateFeedbackFindings(findings) {
  $("#feedback-finding").innerHTML = '<option value="">不关联</option>' + findings.map((finding, index) => `<option value="${index}">${escapeHtml(`${finding.rule_id || "规则"} · ${finding.path || "文件"}:${finding.line || "?"}`)}</option>`).join("");
  $("#feedback-result").textContent = "";
}

function renderTaskFeedback(cases) {
  const root = $("#task-feedback-history");
  root.innerHTML = cases?.length ? `<h4>本任务反馈</h4>${cases.map((item) => `<div class="feedback-case"><b>${escapeHtml(feedbackLabels[item.category] || item.category)}</b><span>${escapeHtml((item.payload || {}).note || "无说明")}</span><small>${item.resolved ? "已解决" : "待评测"}</small></div>`).join("")}` : '<p class="muted">尚无人工反馈。</p>';
}

async function loadTaskFeedback(taskId) {
  try {
    const data = await api(`/v1/tasks/${encodeURIComponent(taskId)}/feedback`);
    if (selectedTask === taskId) renderTaskFeedback(data.cases || []);
  } catch (error) {
    $("#task-feedback-history").innerHTML = `<p class="muted">反馈历史不可用：${escapeHtml(error.message)}</p>`;
  }
}

function reviewPackCard(skill) {
  const permissions = skill.permissions || skill.allowed_tools || [];
  return `<article class="pack-card"><div class="pack-top"><span class="pack-glyph">${escapeHtml((skill.display_name || skill.name || "RP").slice(0, 2).toUpperCase())}</span><span class="status ${skill.sandboxed ? "neutral" : "state-success"}">${escapeHtml(skill.status_label || "Active")}</span></div><h3>${escapeHtml(skill.display_name || skill.name)}</h3><p>${escapeHtml(skill.scope || skill.description || "No scope description available")}</p><dl><dt>Machine ID</dt><dd>${escapeHtml(skill.name)}</dd><dt>Version</dt><dd>${escapeHtml(skill.version || "1")}</dd><dt>Source</dt><dd>${escapeHtml(skill.source || "unknown")}</dd><dt>Allowed tools</dt><dd>${escapeHtml(permissions.length)}</dd></dl></article>`;
}

async function loadSkills() {
  const root = $("#skill-list");
  root.innerHTML = '<div class="skeleton card"></div><div class="skeleton card"></div>';
  try {
    const data = await api("/api/skills");
    const llm = data.llm || {};
    const enabled = Boolean(llm.enabled);
    $("#llm-runtime-status").className = `status ${enabled ? "state-success" : "neutral"}`;
    $("#llm-runtime-status").textContent = enabled ? "已配置" : "待配置";
    $("#llm-runtime-model").textContent = enabled ? `${llm.provider} / ${llm.model || "default"}` : "Agentic mode unavailable";
    $("#llm-capability-detail").textContent = enabled ? "为四角色协议提供上下文推理；工具负责提供可核验证据。" : "配置 DIFFPRISM_LLM_* 后启用完整四角色审查。";
    const skills = (data.skills || []).filter((item) => item.name !== "llm-review");
    root.innerHTML = skills.length ? skills.map(reviewPackCard).join("") : '<div class="empty-list">未发现 Review Pack。</div>';
  } catch (error) {
    root.innerHTML = `<div class="empty-list">Review Packs 加载失败：${escapeHtml(error.message)}</div>`;
  }
}

function metricRows(metrics) {
  const entries = Object.entries(metrics || {});
  return entries.length ? entries.map(([name, value]) => `<span><small>${escapeHtml(name.replaceAll("_", " "))}</small><b>${escapeHtml(value)}</b></span>`).join("") : '<p class="muted">No public metrics recorded.</p>';
}

function renderBenchmark(data) {
  const dataset = data?.dataset || {};
  const splits = dataset.splits || {};
  const ready = Boolean(dataset.production_ready);
  $("#benchmark-summary").innerHTML = `<article class="dataset-card"><div><p class="eyebrow">DATASET</p><h3>${escapeHtml(dataset.name || "Unknown benchmark")}</h3><p>${escapeHtml(dataset.cases || 0)} cases · ${escapeHtml(dataset.repositories || 0)} repositories · ${escapeHtml(dataset.findings || 0)} findings</p></div><span class="status ${ready ? "state-success" : "state-pending"}">${ready ? "PRODUCTION READY" : "SYNTHETIC FIXTURE"}</span><dl><dt>Validation</dt><dd>${escapeHtml(splits.validation || 0)}</dd><dt>Holdout</dt><dd>${escapeHtml(splits.holdout || 0)}</dd><dt>SHA-256</dt><dd><code>${escapeHtml(dataset.file_sha256 || "unknown")}</code></dd><dt>Limitation</dt><dd>${escapeHtml(dataset.limitation || "None recorded")}</dd></dl></article>`;
  const arms = Object.entries(data?.arms || {});
  const runs = data?.runs || [];
  $("#benchmark-runs").innerHTML = `<div class="arm-grid">${arms.map(([id, label]) => `<div class="arm"><small>${escapeHtml(id)}</small><strong>${escapeHtml(label)}</strong></div>`).join("")}</div>${runs.length ? `<div class="run-list">${runs.map((run) => `<article><div><span class="status ${String(run.decision).toLowerCase().includes("activ") ? "state-success" : "neutral"}">${escapeHtml(run.decision || "unknown")}</span><h4>${escapeHtml(run.arm_display_name || run.arm)}</h4><small>${escapeHtml(formatTime(run.created_at))}</small></div><div class="metric-strip">${metricRows(run.metrics)}</div></article>`).join("")}</div>` : '<div class="empty-list">尚无可公开的评测运行。数据集身份已固定，可运行脚本生成结果。</div>'}`;
}

async function loadBenchmark() {
  try {
    const [benchmark, status, failures] = await Promise.all([
      api("/api/benchmark"), api("/v1/evolution/status"), api("/api/failures").catch(() => ({ cases: [] })),
    ]);
    renderBenchmark(benchmark);
    $("#evolution-status").textContent = formatJson(status);
    const cases = failures.cases || [];
    $("#failure-list").innerHTML = cases.length ? `<h4>待评测反馈</h4>${cases.slice(0, 6).map((item) => `<div class="feedback-case"><b>${escapeHtml(feedbackLabels[item.category] || item.category)}</b><span>${escapeHtml((item.payload || {}).note || "无说明")}</span><small>${item.resolved ? "已解决" : "待处理"}</small></div>`).join("")}` : '<p class="muted">没有待处理反馈。</p>';
  } catch (error) {
    $("#benchmark-summary").innerHTML = `<div class="empty-list">Benchmark 加载失败：${escapeHtml(error.message)}</div>`;
  }
}

$$('.nav-item').forEach((button) => button.addEventListener("click", () => show(button.dataset.view)));
$$('[data-jump]').forEach((button) => button.addEventListener("click", () => show(button.dataset.jump)));
window.addEventListener("hashchange", () => show(location.hash.slice(1), false));

$("#review-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = $('button[type="submit"]', form);
  const values = new FormData(form);
  const body = { repository: values.get("repository"), diff: values.get("diff"), mode: values.get("mode") };
  if (values.get("pull_request")) body.pull_request = Number(values.get("pull_request"));
  const output = $("#review-result");
  setButtonBusy(button, true, "正在提交…");
  try {
    const data = await api(`/v1/reviews${values.get("async") ? "?async=true" : ""}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const taskId = data.task_id || data.id;
    output.className = "result";
    output.innerHTML = `<strong>任务已接收</strong><br>${escapeHtml(taskId || "已完成同步审查")}<br>${escapeHtml(data.state || "QUEUED")}`;
    await loadDashboard();
    if (taskId && !values.get("async")) await openTask(taskId);
    toast("审查任务已提交");
  } catch (error) { output.textContent = error.message; } finally { setButtonBusy(button, false); }
});

$("#create-fix").addEventListener("click", async () => {
  if (!selectedTask) return;
  const button = $("#create-fix");
  setButtonBusy(button, true, "正在创建…");
  try {
    await api(`/v1/tasks/${encodeURIComponent(selectedTask)}/fix`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    toast("安全修复分支已创建");
  } catch (error) { toast(error.message); } finally { setButtonBusy(button, false); }
});

$("#feedback-category").addEventListener("change", (event) => $("#feedback-missed-fields").classList.toggle("hidden", event.target.value !== "missed_issue"));
$("#feedback-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedTask || !selectedTaskData?.report) return;
  const form = event.currentTarget;
  const button = $('button[type="submit"]', form);
  const values = new FormData(form);
  const category = String(values.get("category"));
  const selectedIndex = values.get("finding_index");
  const findings = selectedTaskData.report.findings || [];
  const finding = selectedIndex === "" ? {} : { ...(findings[Number(selectedIndex)] || {}) };
  if (category === "missed_issue") {
    if (String(values.get("rule_id") || "").trim()) finding.rule_id = String(values.get("rule_id")).trim();
    if (String(values.get("path") || "").trim()) finding.path = String(values.get("path")).trim();
    if (Number(values.get("line")) > 0) finding.line = Number(values.get("line"));
  }
  setButtonBusy(button, true, "记录中…");
  try {
    const data = await api(`/v1/tasks/${encodeURIComponent(selectedTask)}/feedback`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ category, finding: Object.keys(finding).length ? finding : null, note: String(values.get("note") || "").trim() }) });
    $("#feedback-result").textContent = `${feedbackLabels[data.category] || data.category}已记录。`;
    form.reset();
    $("#feedback-missed-fields").classList.add("hidden");
    await loadTaskFeedback(selectedTask);
  } catch (error) { $("#feedback-result").textContent = `提交失败：${error.message}`; } finally { setButtonBusy(button, false); }
});

$("#reload-skills").addEventListener("click", async () => {
  const button = $("#reload-skills"); setButtonBusy(button, true, "扫描中…");
  try { await api("/v1/skills/reload", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }); await loadSkills(); toast("Review Packs 已重新加载"); } catch (error) { toast(error.message); } finally { setButtonBusy(button, false); }
});

$("#evolution-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const form = event.currentTarget; const button = $('button[type="submit"]', form); const values = new FormData(form); setButtonBusy(button, true, "评测中…");
  try { const data = await api("/v1/evolution/propose", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ skill_name: values.get("skill_name"), prompt: values.get("prompt") }) }); $("#evolution-result").className = "result"; $("#evolution-result").textContent = formatJson(data); await loadBenchmark(); } catch (error) { toast(error.message); } finally { setButtonBusy(button, false); }
});

$("#auto-evolve").addEventListener("click", async () => {
  const button = $("#auto-evolve"); setButtonBusy(button, true, "生成中…");
  try { const data = await api("/v1/evolution/auto", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ skill_name: "llm-review" }) }); $("#evolution-result").className = "result"; $("#evolution-result").textContent = formatJson(data); await loadBenchmark(); } catch (error) { toast(error.message); } finally { setButtonBusy(button, false); }
});

$("#refresh").addEventListener("click", async () => {
  const view = location.hash.slice(1) || "inbox";
  if (view === "workspace") await loadTasks(); else if (view === "packs") await loadSkills(); else if (view === "benchmark") await loadBenchmark(); else await loadDashboard();
  toast("数据已刷新");
});

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const form = event.currentTarget; const button = $('button[type="submit"]', form); const values = new FormData(form); setButtonBusy(button, true, "登录中…");
  try { const data = await api("/v1/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: values.get("username"), password: values.get("password"), tenant_id: values.get("tenant_id") }) }); accessToken = data.access_token; localStorage.setItem("diffprism_token", accessToken); localStorage.removeItem("evoagent_token"); $("#login-overlay").classList.add("hidden"); $("#logout").classList.remove("hidden"); $("#login-error").textContent = ""; await loadDashboard(); } catch (error) { $("#login-error").textContent = error.message; } finally { setButtonBusy(button, false); }
});

$("#logout").addEventListener("click", () => { accessToken = ""; localStorage.removeItem("diffprism_token"); localStorage.removeItem("evoagent_token"); $("#login-overlay").classList.remove("hidden"); $("#logout").classList.add("hidden"); });

const diffInput = $('textarea[name="diff"]', $("#review-form"));
function updateDiffStats() { const value = diffInput.value; $("#diff-stats").textContent = `${value ? value.split(/\r?\n/).length : 0} 行 · ${value.length} 字符`; }
diffInput.addEventListener("input", updateDiffStats);
updateDiffStats();
if (accessToken) $("#logout").classList.remove("hidden");
show(location.hash.slice(1) || "inbox", false);
loadDashboard();
