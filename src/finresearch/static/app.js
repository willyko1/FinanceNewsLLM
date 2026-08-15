const form = document.querySelector("#research-form");
const question = document.querySelector("#question");
const submitButton = document.querySelector("#submit-button");
const workspace = document.querySelector("#workspace");
const loadingState = document.querySelector("#loading-state");
const loadingLabel = document.querySelector("#loading-label");
const progressBar = document.querySelector("#progress-bar");
const answer = document.querySelector("#answer");
const errorBox = document.querySelector("#error");

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[char]);

function renderMarkdown(markdown) {
  const safe = escapeHtml(markdown);
  const lines = safe.split("\n");
  let html = '<div class="answer-kicker">SignalDesk analysis</div>';
  let inList = false;
  for (const raw of lines) {
    const line = raw.trim();
    if (line.startsWith("- ") || line.startsWith("* ")) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${line.slice(2)}</li>`;
      continue;
    }
    if (inList) { html += "</ul>"; inList = false; }
    if (!line) continue;
    if (line.startsWith("### ")) html += `<h3>${line.slice(4)}</h3>`;
    else if (line.startsWith("## ")) html += `<h2>${line.slice(3)}</h2>`;
    else if (line.startsWith("# ")) html += `<h2>${line.slice(2)}</h2>`;
    else html += `<p>${line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")}</p>`;
  }
  if (inList) html += "</ul>";
  return html.replace(/\[S(\d+)\]/g, '<a class="citation" href="#source-S$1">S$1</a>');
}

function renderResult(data) {
  answer.innerHTML = renderMarkdown(data.answer);
  if (data.demo) answer.insertAdjacentHTML("afterbegin", '<div class="demo-banner">Saved demonstration · no AI quota used</div>');
  answer.classList.remove("hidden");
  document.querySelector("#timestamp").textContent = new Date(data.generated_at).toLocaleString();
  document.querySelector("#tool-count").textContent = `${data.trace.length} call${data.trace.length === 1 ? "" : "s"}`;
  document.querySelector("#source-count").textContent = `${data.sources.length} cited`;
  document.querySelector("#trace-list").innerHTML = data.trace.map((item) => {
    const args = Object.entries(item.arguments).map(([key, val]) => `${key}: ${val}`).join(" · ");
    return `<li><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(args)}${item.source_ids.length ? ` · ${escapeHtml(item.source_ids.join(", "))}` : ""}</small></li>`;
  }).join("") || '<li class="empty-trace">No tools were called.</li>';
  document.querySelector("#source-list").innerHTML = data.sources.map((source) => `
    <a class="source-card" id="source-${escapeHtml(source.id)}" href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">
      <span class="source-meta"><span>${escapeHtml(source.id)} · ${escapeHtml(source.publisher)}</span><span>${escapeHtml(source.published_at || "")}</span></span>
      <span class="source-name">${escapeHtml(source.title)} ↗</span>
    </a>`).join("") || '<p class="empty-sources">No source links were returned.</p>';
}

async function runResearch(event) {
  event.preventDefault();
  if (!question.value.trim()) return;
  workspace.classList.remove("hidden");
  loadingState.classList.remove("hidden");
  answer.classList.add("hidden");
  errorBox.classList.add("hidden");
  submitButton.disabled = true;
  workspace.scrollIntoView({behavior: "smooth", block: "start"});

  const phases = [
    ["Connecting to financial data tools…", "22%"],
    ["Reading market and news evidence…", "48%"],
    ["Checking regulatory filings…", "70%"],
    ["Cross-checking claims and citations…", "88%"],
  ];
  let phase = 0;
  loadingLabel.textContent = phases[0][0];
  progressBar.style.width = phases[0][1];
  const timer = setInterval(() => {
    phase = Math.min(phase + 1, phases.length - 1);
    loadingLabel.textContent = phases[phase][0];
    progressBar.style.width = phases[phase][1];
  }, 2200);

  try {
    const response = await fetch("/api/research", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({question: question.value.trim()})});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Research request failed");
    progressBar.style.width = "100%";
    renderResult(payload);
  } catch (error) {
    errorBox.innerHTML = `<strong>Couldn’t complete this investigation.</strong><br>${escapeHtml(error.message)}`;
    errorBox.classList.remove("hidden");
  } finally {
    clearInterval(timer);
    loadingState.classList.add("hidden");
    submitButton.disabled = false;
  }
}

form.addEventListener("submit", runResearch);
question.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") form.requestSubmit();
});
document.querySelectorAll("[data-question]").forEach((button) => button.addEventListener("click", () => {
  question.value = button.dataset.question;
  question.focus();
}));
document.querySelector("#demo-button").addEventListener("click", async () => {
  workspace.classList.remove("hidden");
  loadingState.classList.remove("hidden");
  answer.classList.add("hidden");
  errorBox.classList.add("hidden");
  workspace.scrollIntoView({behavior: "smooth", block: "start"});
  try {
    const response = await fetch("/api/demo");
    if (!response.ok) throw new Error("Could not load the saved example");
    renderResult(await response.json());
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.classList.remove("hidden");
  } finally {
    loadingState.classList.add("hidden");
  }
});

fetch("/api/health").then((res) => res.json()).then((data) => {
  const status = document.querySelector("#system-status");
  if (data.mcp === "connected") {
    status.classList.add("ready");
    status.innerHTML = `<span class="status-dot"></span>${data.tools.length} MCP tools online`;
  } else {
    status.classList.add("error");
    status.innerHTML = '<span class="status-dot"></span>MCP unavailable';
  }
}).catch(() => {});
