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

// initial load
refreshPageList();
