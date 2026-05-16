// Minimal vanilla JS for the LLM Wiki UI.

// -------------------- tab switching --------------------

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});

// -------------------- helpers --------------------

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`${r.status}: ${detail}`);
  }
  return r.json();
}

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return r.json();
}

function setStatus(el, text, isError = false) {
  el.textContent = text;
  el.classList.toggle("error", isError);
}

function renderTrace(ol, trace) {
  ol.innerHTML = "";
  for (const step of trace || []) {
    const li = document.createElement("li");
    const argStr = JSON.stringify(step.args || {});
    li.innerHTML =
      `<span class="tool-name">${escapeHtml(step.tool)}</span>` +
      `<span class="tool-args">(${escapeHtml(truncate(argStr, 200))})</span>` +
      `<pre>${escapeHtml(step.result_preview || "")}</pre>`;
    ol.appendChild(li);
  }
}

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function truncate(s, n) {
  return s && s.length > n ? s.slice(0, n) + "…" : s;
}

// Derive a kebab-case slug from a filename (drops extension).
function slugifyFilename(name) {
  const base = name.replace(/\.[^.]+$/, "");
  return base
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

// Very tiny markdown-ish renderer for the *answer/summary/report* boxes.
function tinyMarkdown(text) {
  if (!text) return "";
  let s = escapeHtml(text);
  s = s.replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code}</code></pre>`);
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(^|\n)### (.*)/g, "$1<h3>$2</h3>");
  s = s.replace(/(^|\n)## (.*)/g, "$1<h2>$2</h2>");
  s = s.replace(/(^|\n)# (.*)/g, "$1<h1>$2</h1>");
  s = s.replace(/\n\n/g, "</p><p>");
  s = s.replace(/\n/g, "<br>");
  return `<p>${s}</p>`;
}

// -------------------- ingest (modal, PDF-only) --------------------

const ingestModal   = document.getElementById("ingest-modal");
const ingestOpenBtn = document.getElementById("ingest-open");
const ingestOpenAlt = document.getElementById("ingest-open-alt");
const ingestCloseBtn= document.getElementById("ingest-close");
const ingestDrop    = document.getElementById("ingest-drop");
const ingestDropText= document.getElementById("ingest-drop-text");
const ingestFile    = document.getElementById("ingest-file");
const ingestName    = document.getElementById("ingest-name");
const ingestGo      = document.getElementById("ingest-go");
const ingestStatus  = document.getElementById("ingest-status");
const ingestResult  = document.getElementById("ingest-result");
const ingestSummary = document.getElementById("ingest-summary");
const ingestTrace   = document.getElementById("ingest-trace");
const inlineIngest  = document.querySelector(".inline-ingest");

function openIngestModal() {
  ingestModal.classList.add("is-open");
  ingestModal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function closeIngestModal() {
  ingestModal.classList.remove("is-open");
  ingestModal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}

function resetIngestForm() {
  ingestFile.value = "";
  ingestName.value = "";
  ingestDrop.classList.remove("has-file", "is-drag");
  ingestDropText.textContent = "Click to select a PDF or .md file, or drag & drop here";
  setStatus(ingestStatus, "");
  ingestResult.hidden = true;
  ingestSummary.innerHTML = "";
  ingestTrace.innerHTML = "";
}

function fileKind(file) {
  const name = (file.name || "").toLowerCase();
  if (name.endsWith(".pdf")) return "pdf";
  if (name.endsWith(".md") || name.endsWith(".markdown")) return "md";
  const type = (file.type || "").toLowerCase();
  if (type === "application/pdf") return "pdf";
  if (type === "text/markdown") return "md";
  return null;
}

ingestOpenBtn.addEventListener("click", openIngestModal);
if (ingestOpenAlt) ingestOpenAlt.addEventListener("click", openIngestModal);
if (inlineIngest)  inlineIngest.addEventListener("click", openIngestModal);
ingestCloseBtn.addEventListener("click", closeIngestModal);

ingestModal.addEventListener("click", (e) => {
  if (e.target === ingestModal) closeIngestModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && ingestModal.classList.contains("is-open")) closeIngestModal();
});

// drag & drop
["dragenter", "dragover"].forEach((ev) =>
  ingestDrop.addEventListener(ev, (e) => {
    e.preventDefault();
    ingestDrop.classList.add("is-drag");
  })
);
["dragleave", "drop"].forEach((ev) =>
  ingestDrop.addEventListener(ev, (e) => {
    e.preventDefault();
    ingestDrop.classList.remove("is-drag");
  })
);
ingestDrop.addEventListener("drop", (e) => {
  const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
  if (f) assignFile(f);
});

ingestFile.addEventListener("change", () => {
  const f = ingestFile.files && ingestFile.files[0];
  if (f) assignFile(f);
});

function assignFile(file) {
  // place into the hidden input via DataTransfer so the form sees it
  const dt = new DataTransfer();
  dt.items.add(file);
  ingestFile.files = dt.files;

  ingestDrop.classList.add("has-file");
  ingestDropText.textContent = file.name;
  if (!ingestName.value.trim()) {
    ingestName.value = slugifyFilename(file.name);
  }
}

ingestGo.addEventListener("click", async () => {
  const name = ingestName.value.trim();
  const file = ingestFile.files && ingestFile.files[0];
  if (!file) {
    setStatus(ingestStatus, "Select a PDF or .md file first.", true);
    return;
  }
  if (!name) {
    setStatus(ingestStatus, "Provide a source name.", true);
    return;
  }
  if (!fileKind(file)) {
    setStatus(ingestStatus, "Unsupported file type. Use .pdf or .md.", true);
    return;
  }
  ingestGo.disabled = true;
  setStatus(ingestStatus, "Ingesting... the agent may take a while.");
  try {
    const fd = new FormData();
    fd.append("source_name", name);
    fd.append("file", file);
    const r = await fetch("/api/ingest/file", { method: "POST", body: fd });
    if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
    const res = await r.json();
    setStatus(ingestStatus, "Done.");
    ingestResult.hidden = false;
    ingestSummary.innerHTML = tinyMarkdown(res.summary);
    renderTrace(ingestTrace, res.trace);
    refreshPageList();
  } catch (e) {
    setStatus(ingestStatus, e.message, true);
  } finally {
    ingestGo.disabled = false;
  }
});

// -------------------- query --------------------

document.getElementById("query-go").addEventListener("click", async () => {
  const q = document.getElementById("query-q").value.trim();
  const btn = document.getElementById("query-go");
  const status = document.getElementById("query-status");
  if (!q) {
    setStatus(status, "Type a question.", true);
    return;
  }
  btn.disabled = true;
  setStatus(status, "Thinking...");
  try {
    const res = await postJSON("/api/query", { question: q });
    setStatus(status, "Done.");
    document.getElementById("query-answer").innerHTML = tinyMarkdown(res.answer);
    renderTrace(document.getElementById("query-trace"), res.trace);
  } catch (e) {
    setStatus(status, e.message, true);
  } finally {
    btn.disabled = false;
  }
});

// -------------------- lint --------------------

document.getElementById("lint-go").addEventListener("click", async () => {
  const btn = document.getElementById("lint-go");
  const status = document.getElementById("lint-status");
  btn.disabled = true;
  setStatus(status, "Running lint...");
  try {
    const res = await postJSON("/api/lint", {});
    setStatus(status, "Done.");
    document.getElementById("lint-report").innerHTML = tinyMarkdown(res.report);
    renderTrace(document.getElementById("lint-trace"), res.trace);
    refreshPageList();
  } catch (e) {
    setStatus(status, e.message, true);
  } finally {
    btn.disabled = false;
  }
});

// -------------------- hallucination --------------------

function renderHalluStats(findings) {
  const total = findings.length;
  if (!total) return "<p class=\"muted\">No findings recorded.</p>";
  const byVerdict = {};
  const byType = {};
  const byLayer = { 1: 0, 2: 0, 3: 0 };
  for (const f of findings) {
    byVerdict[f.verdict] = (byVerdict[f.verdict] || 0) + 1;
    byType[f.type] = (byType[f.type] || 0) + 1;
    byLayer[f.layer] = (byLayer[f.layer] || 0) + 1;
  }
  const verdictOrder = ["supported", "contradicted", "unverifiable", "hallucination"];
  const typeOrder = ["factual", "quantitative", "relational", "temporal", "negation", "synthesis"];
  const row = (label, val) =>
    `<li><span class="mono">${escapeHtml(label)}</span>: <strong>${val}</strong></li>`;
  let html = `<p><strong>${total}</strong> findings total.</p>`;
  html += "<p><strong>By verdict</strong></p><ul>";
  for (const v of verdictOrder) html += row(v, byVerdict[v] || 0);
  html += "</ul>";
  html += "<p><strong>By layer</strong></p><ul>";
  for (const l of [1, 2, 3]) html += row(`layer ${l}`, byLayer[l] || 0);
  html += "</ul>";
  html += "<p><strong>By claim type</strong></p><ul>";
  for (const t of typeOrder) if (byType[t]) html += row(t, byType[t]);
  html += "</ul>";
  return html;
}

async function loadHalluReport() {
  try {
    const res = await getJSON("/api/hallucination-report");
    document.getElementById("hallu-report").innerHTML = res.content_html;
    return true;
  } catch (_e) {
    return false;
  }
}

document.getElementById("hallu-go").addEventListener("click", async () => {
  const btn = document.getElementById("hallu-go");
  const status = document.getElementById("hallu-status");
  btn.disabled = true;
  setStatus(status, "Running hallucination sweep... the agent may take a while.");
  try {
    const res = await postJSON("/api/hallucination-check", {});
    setStatus(status, `Done — ${res.findings.length} findings.`);
    document.getElementById("hallu-stats-card").hidden = false;
    document.getElementById("hallu-summary").innerHTML = tinyMarkdown(res.summary);
    document.getElementById("hallu-stats").innerHTML = renderHalluStats(res.findings);
    await loadHalluReport();
    renderTrace(document.getElementById("hallu-trace"), res.trace);
  } catch (e) {
    setStatus(status, e.message, true);
  } finally {
    btn.disabled = false;
  }
});

// Show the previous report when the user opens the tab for the first time.
document.querySelector('.tab[data-tab="hallucination"]').addEventListener("click", () => {
  const reportEl = document.getElementById("hallu-report");
  if (!reportEl.innerHTML.trim()) loadHalluReport();
});

// -------------------- browse --------------------

async function refreshPageList() {
  try {
    const pages = await getJSON("/api/pages");
    const ul = document.getElementById("page-list");
    ul.innerHTML = "";
    if (!pages.length) {
      ul.innerHTML = '<li class="muted">(no pages yet)</li>';
      return;
    }
    for (const name of pages) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.textContent = name;
      btn.addEventListener("click", () => loadPage(name));
      li.appendChild(btn);
      ul.appendChild(li);
    }
  } catch (e) {
    console.error(e);
  }
}

async function loadPage(name) {
  try {
    const res = await getJSON(`/api/page/${encodeURIComponent(name)}`);
    document.getElementById("page-title").textContent = `wiki/${name}.md`;
    document.getElementById("page-body").innerHTML = res.content_html;
  } catch (e) {
    document.getElementById("page-body").innerHTML = `<p class="muted">${escapeHtml(e.message)}</p>`;
  }
}

document.getElementById("browse-refresh").addEventListener("click", refreshPageList);

document.getElementById("show-index").addEventListener("click", async () => {
  const res = await getJSON("/api/index");
  document.getElementById("page-title").textContent = "index.md";
  document.getElementById("page-body").innerHTML = res.content_html;
});

document.getElementById("show-log").addEventListener("click", async () => {
  const res = await getJSON("/api/log");
  document.getElementById("page-title").textContent = "log.md";
  document.getElementById("page-body").innerHTML = `<pre>${escapeHtml(res.content_md)}</pre>`;
});

document.getElementById("show-schema").addEventListener("click", async () => {
  const res = await getJSON("/api/schema");
  document.getElementById("page-title").textContent = "SCHEMA.md";
  document.getElementById("page-body").innerHTML = `<pre>${escapeHtml(res.content_md)}</pre>`;
});

// -------------------- chat --------------------

const chatHistory = []; // [{role, content, trace?}]

const chatLog = document.getElementById("chat-log");
const chatInput = document.getElementById("chat-input");
const chatForm = document.getElementById("chat-form");
const chatStatus = document.getElementById("chat-status");
const chatSend = document.getElementById("chat-send");

function renderChat() {
  chatLog.innerHTML = "";
  for (const m of chatHistory) {
    const wrap = document.createElement("div");
    wrap.className = "msg " + m.role;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (m.role === "assistant") {
      bubble.innerHTML = tinyMarkdown(m.content);
    } else {
      bubble.textContent = m.content;
    }
    wrap.appendChild(bubble);
    if (m.trace && m.trace.length) {
      const det = document.createElement("details");
      const sum = document.createElement("summary");
      sum.textContent = `tool trace (${m.trace.length})`;
      det.appendChild(sum);
      const ol = document.createElement("ol");
      ol.className = "trace";
      renderTrace(ol, m.trace);
      det.appendChild(ol);
      wrap.appendChild(det);
    }
    chatLog.appendChild(wrap);
  }
  chatLog.scrollTop = chatLog.scrollHeight;
}

function showThinking(on) {
  let el = document.getElementById("chat-thinking");
  if (on) {
    if (!el) {
      el = document.createElement("div");
      el.id = "chat-thinking";
      el.className = "msg assistant";
      el.innerHTML = '<div class="bubble thinking">thinking</div>';
      chatLog.appendChild(el);
      chatLog.scrollTop = chatLog.scrollHeight;
    }
  } else if (el) {
    el.remove();
  }
}

async function sendChat() {
  const text = chatInput.value.trim();
  if (!text) return;
  chatHistory.push({ role: "user", content: text });
  chatInput.value = "";
  renderChat();
  chatSend.disabled = true;
  setStatus(chatStatus, "");
  showThinking(true);

  const payload = chatHistory.map(({ role, content }) => ({ role, content }));
  try {
    const res = await postJSON("/api/chat", { messages: payload });
    chatHistory.push({ role: "assistant", content: res.reply, trace: res.trace });
    renderChat();
  } catch (e) {
    setStatus(chatStatus, e.message, true);
  } finally {
    showThinking(false);
    chatSend.disabled = false;
    chatInput.focus();
  }
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  sendChat();
});

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
});

document.getElementById("chat-clear").addEventListener("click", () => {
  chatHistory.length = 0;
  setStatus(chatStatus, "");
  renderChat();
});

// initial load
refreshPageList();
chatInput.focus();
