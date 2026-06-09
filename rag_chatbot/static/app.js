const messagesEl = document.querySelector("#messages");
const sourcesEl = document.querySelector("#sources");
const form = document.querySelector("#chatForm");
const input = document.querySelector("#messageInput");
const sendBtn = document.querySelector("#sendBtn");
const clearBtn = document.querySelector("#clearBtn");
const topK = document.querySelector("#topK");
const topKValue = document.querySelector("#topKValue");
const useRag = document.querySelector("#useRag");
const lastPerf = document.querySelector("#lastPerf");
const modelSelect = document.querySelector("#modelSelect");
const customModel = document.querySelector("#customModel");

let history = [];

function ms(value) {
  return `${Math.round(value)} ms`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderAssistantMarkdown(value) {
  let html = escapeHtml(value);
  html = html
    .replace(/^### (.*)$/gm, "<h4>$1</h4>")
    .replace(/^## (.*)$/gm, "<h3>$1</h3>")
    .replace(/^# (.*)$/gm, "<h2>$1</h2>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/^[-•] (.*)$/gm, '<div class="md-bullet">$1</div>')
    .replace(/^✅ (.*)$/gm, '<div class="md-bullet good">$1</div>')
    .replace(/^❌ (.*)$/gm, '<div class="md-bullet warn">$1</div>')
    .replace(/\n{2,}/g, "<br><br>")
    .replace(/\n/g, "<br>");
  return html;
}

function setBubbleContent(bubble, role, content) {
  if (role === "assistant") {
    bubble.innerHTML = renderAssistantMarkdown(content);
  } else {
    bubble.textContent = content;
  }
}

function selectedModel() {
  if (modelSelect.value === "__custom__") {
    return customModel.value.trim();
  }
  return modelSelect.value;
}

async function loadModels() {
  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    const options = data.models || [];
    modelSelect.innerHTML = options.map((model) => `
      <option value="${escapeHtml(model)}">${escapeHtml(model)}</option>
    `).join("") + '<option value="__custom__">Custom model...</option>';
    modelSelect.value = data.default || options[0] || "";
  } catch {
    modelSelect.innerHTML = '<option value="">Default model</option><option value="__custom__">Custom model...</option>';
  }
}

function addMessage(role, content) {
  const row = document.createElement("div");
  row.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  setBubbleContent(bubble, role, content);
  row.appendChild(bubble);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderWelcome() {
  messagesEl.innerHTML = `
    <div class="system-note">
      Bắt đầu bằng câu hỏi pháp luật hoặc hỏi nối tiếp như một chatbot bình thường.
      Ví dụ: "Tàng trữ trái phép chất ma túy bị phạt thế nào?"
    </div>
  `;
}

function renderSources(sources) {
  if (!sources.length) {
    sourcesEl.className = "sources-empty";
    sourcesEl.textContent = "No evidence sources returned for this answer.";
    return;
  }
  sourcesEl.className = "";
  sourcesEl.innerHTML = sources.map((source) => {
    const score = Number(source.score).toFixed(3);
    const isNews = source.source_type === "news" && source.url;
    const title = escapeHtml(source.title);
    const meta = `${escapeHtml(source.retrieval)} · ${escapeHtml(source.source_type)} · chunk ${escapeHtml(source.chunk_index)}`;
    const body = isNews
      ? `<a class="article-link" href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">Open article link</a>`
      : `<div class="source-preview">${escapeHtml(source.preview)}</div>`;
    const legalLine = !isNews && source.source_pdf
      ? `<div class="source-meta">Legal source: ${escapeHtml(source.source_pdf)}</div>`
      : "";
    return `
      <article class="source-card ${isNews ? "news-card" : "legal-card"}">
        <div class="source-top">
          <div class="source-title">${title}</div>
          <div class="score">${score}</div>
        </div>
        <div class="source-meta">${meta}</div>
        ${legalLine}
        ${body}
      </article>
    `;
  }).join("");
}

function renderPerf(perf) {
  lastPerf.textContent = `${perf.model} · Total ${ms(perf.total_ms)} · retrieval ${ms(perf.retrieval_ms)} · generation ${ms(perf.generation_ms)} · ${perf.mode}`;
}

async function loadHealth() {
  const el = document.querySelector("#health");
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    el.innerHTML = `
      <strong>${data.ok ? "Ready" : "Needs Day08 path"}</strong><br>
      Default model: ${escapeHtml(data.model)}<br>
      OpenRouter key: ${data.has_openrouter_key ? "yes" : "missing"}<br>
      Day08: ${escapeHtml(data.day08_dir)}
    `;
  } catch (error) {
    el.textContent = `Health check failed: ${error.message}`;
  }
}

async function loadPerformance() {
  try {
    const [summaryRes, recentRes] = await Promise.all([
      fetch("/api/performance"),
      fetch("/api/performance/recent"),
    ]);
    const summary = await summaryRes.json();
    const recent = await recentRes.json();
    document.querySelector("#avgTotal").textContent = ms(summary.avg_total_ms);
    document.querySelector("#p95").textContent = ms(summary.p95_total_ms);
    document.querySelector("#fastest").textContent = ms(summary.fastest_ms);
    document.querySelector("#runs").textContent = summary.count;
    document.querySelector("#recentPerf").innerHTML = recent.slice(0, 8).map((row) => `
      <div class="recent-row">
        <span>${escapeHtml(new Date(row.ts).toLocaleTimeString())} · ${escapeHtml(row.model || row.mode)}</span>
        <strong>${ms(row.total_ms)}</strong>
      </div>
    `).join("") || `<div class="source-meta">No runs yet.</div>`;
  } catch {
    document.querySelector("#recentPerf").innerHTML = `<div class="source-meta">Performance unavailable.</div>`;
  }
}

async function sendMessage(message) {
  sendBtn.disabled = true;
  addMessage("user", message);
  const pending = document.createElement("div");
  pending.className = "message assistant";
  pending.innerHTML = `<div class="bubble">Retrieving evidence, drafting answer, and measuring latency...</div>`;
  messagesEl.appendChild(pending);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        history,
        top_k: Number(topK.value),
        use_rag: useRag.checked,
        model: selectedModel(),
      }),
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || "Request failed");
    }
    const data = await res.json();
    setBubbleContent(pending.querySelector(".bubble"), "assistant", data.answer);
    history.push({ role: "user", content: message });
    history.push({ role: "assistant", content: data.answer });
    renderSources(data.sources);
    renderPerf(data.performance);
    await loadPerformance();
  } catch (error) {
    setBubbleContent(pending.querySelector(".bubble"), "assistant", `Lỗi: ${error.message}`);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

topK.addEventListener("input", () => {
  topKValue.textContent = topK.value;
});

modelSelect.addEventListener("change", () => {
  customModel.hidden = modelSelect.value !== "__custom__";
  if (!customModel.hidden) {
    customModel.focus();
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  await sendMessage(message);
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

clearBtn.addEventListener("click", () => {
  history = [];
  renderWelcome();
  renderSources([]);
  lastPerf.textContent = "No response yet";
});

renderWelcome();
loadModels();
loadHealth();
loadPerformance();
