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

// Very tiny markdown-ish renderer for the *answer/summary/report* boxes.
// The Browse tab uses server-rendered HTML directly.
function tinyMarkdown(text) {
  if (!text) return "";
  // Escape, then apply a few transforms.
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

// -------------------- ingest --------------------

document.getElementById("ingest-go").addEventListener("click", async () => {
  const name = document.getElementById("ingest-name").value.trim();
  const content = document.getElementById("ingest-content").value;
  const btn = document.getElementById("ingest-go");
  const status = document.getElementById("ingest-status");
  if (!name || !content.trim()) {
    setStatus(status, "Provide both a name and content.", true);
    return;
  }
  btn.disabled = true;
  setStatus(status, "Ingesting... the agent may take a while.");
  try {
    const res = await postJSON("/api/ingest", { source_name: name, content });
    setStatus(status, "Done.");
    document.getElementById("ingest-summary").innerHTML = tinyMarkdown(res.summary);
    renderTrace(document.getElementById("ingest-trace"), res.trace);
    refreshPageList();
  } catch (e) {
    setStatus(status, e.message, true);
  } finally {
    btn.disabled = false;
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

  // Send only role+content; the server doesn't need our trace echoes back.
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
