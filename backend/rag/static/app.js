const els = {
  thread: document.getElementById("thread"),
  empty: document.getElementById("emptyState"),
  form: document.getElementById("composer"),
  input: document.getElementById("messageInput"),
  send: document.getElementById("sendBtn"),
  error: document.getElementById("errorBar"),
  sessions: document.getElementById("sessionList"),
  title: document.getElementById("chatTitle"),
  stats: document.getElementById("statsBox"),
  searchBtn: document.getElementById("searchModeBtn"),
  searchPanel: document.getElementById("searchPanel"),
  searchForm: document.getElementById("searchForm"),
  searchInput: document.getElementById("searchInput"),
  searchResults: document.getElementById("searchResults"),
  dashboardFilter: document.getElementById("dashboardFilter"),
  dashboardList: document.getElementById("dashboardList"),
  chips: document.getElementById("exampleChips"),
  menu: document.getElementById("menuBtn"),
};

const state = {
  sessionId: localStorage.getItem("rag.session") || null,
  loading: false,
};

const EXAMPLES = [
  "Berapa jumlah pegawai berdasarkan tingkat pendidikan?",
  "Dashboard apa saja yang tersedia?",
  "Harga pangan apa saja yang dipantau?",
  "Berapa jumlah RS dan puskesmas yang tercatat?",
];

function showError(msg) {
  els.error.textContent = msg;
  els.error.classList.remove("hidden");
}
function clearError() {
  els.error.classList.add("hidden");
  els.error.textContent = "";
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* Minimal safe Markdown subset: headings, bold, tables, lists, code. */
function renderMarkdown(src) {
  const text = String(src ?? "");
  const lines = text.split("\n");
  let html = "";
  let i = 0;
  const inline = (s) => esc(s)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");

  const isTableRow = (l) => /^\s*\|.*\|\s*$/.test(l);
  const isSepRow = (l) => /^\s*\|?[\s:|-]+\|?[\s:|-]*\s*$/.test(l) && /-/.test(l);

  while (i < lines.length) {
    const line = lines[i];
    if (/^\s*$/.test(line)) { i++; continue; }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) { html += `<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`; i++; continue; }
    if (isTableRow(line) && i + 1 < lines.length && isSepRow(lines[i + 1])) {
      const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => inline(c.trim()));
      const head = cells(line);
      html += `<table><thead><tr>${head.map((c) => `<th>${c}</th>`).join("")}</tr></thead><tbody>`;
      i += 2;
      while (i < lines.length && isTableRow(lines[i])) {
        html += `<tr>${cells(lines[i]).map((c) => `<td>${c}</td>`).join("")}</tr>`;
        i++;
      }
      html += "</tbody></table>";
      continue;
    }
    if (/^\s*([-•]|\d+[.)])\s+/.test(line)) {
      html += "<ul>";
      while (i < lines.length && /^\s*([-•]|\d+[.)])\s+/.test(lines[i])) {
        html += `<li>${inline(lines[i].replace(/^\s*([-•]|\d+[.)])\s+/, ""))}</li>`;
        i++;
      }
      html += "</ul>";
      continue;
    }
    html += `<p>${inline(line)}</p>`;
    i++;
  }
  return html;
}

function sourceCard(s) {
  const stale = s.possibly_outdated
    ? ' <span class="badge stale">mungkin basi</span>'
    : '';
  return `<div class="source">
    <div class="head"><span>${esc(s.dashboard)} · ${esc(s.chart)}</span>${stale}</div>
    <div><span class="badge">${esc(s.rows_covered || "")}</span>
    <span class="badge">data: ${esc(s.data_as_of || "-")}</span>
    <span class="badge">relevansi ${esc(s.relevance ?? "")}</span></div>
    <details><summary>Isi kutipan data</summary><pre>${esc(s.content)}</pre></details>
  </div>`;
}

function addMessage(role, text, sources = []) {
  if (els.empty) els.empty.remove();
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  const body = role === "user" ? `<div>${esc(text)}</div>` : `<div class="md">${renderMarkdown(text)}</div>`;
  div.innerHTML = `<div class="role">${role === "user" ? "Anda" : "Asisten"}</div>${body}` +
    (sources.length ? `<div class="sources">${sources.map(sourceCard).join("")}</div>` : "");
  els.thread.appendChild(div);
  els.thread.scrollTop = els.thread.scrollHeight;
  return div;
}

class ApiError extends Error {
  constructor(status, code, detail, extra = {}) {
    super(detail || `HTTP ${status}`);
    this.status = status;
    this.code = code || "http_error";
    Object.assign(this, extra);
  }
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.code, body.detail, body);
  }
  return res.json();
}

const FRIENDLY_ERRORS = {
  quota_exhausted: (e) => e.retry_after_s != null
    ? `Kuota AI habis. Coba lagi dalam ${Math.ceil(e.retry_after_s)} detik.`
    : "Kuota AI habis. Coba lagi nanti.",
  model_busy: () => "Layanan AI sedang sibuk. Coba lagi beberapa saat.",
  upstream_unreachable: () => "Tidak dapat menghubungi layanan AI. Periksa koneksi lalu coba lagi.",
  server_misconfigured: () => "Server belum dikonfigurasi dengan benar (API key/model). Hubungi admin.",
  model_empty: () => "Model tidak memberikan jawaban. Coba ulangi pertanyaan.",
  tool_loop: () => "Model berputar-putar tanpa jawaban. Coba pertanyaan yang lebih spesifik.",
  chat_failed: (e) => e.message,
};

function friendlyError(err) {
  if (err instanceof ApiError && FRIENDLY_ERRORS[err.code]) {
    return FRIENDLY_ERRORS[err.code](err);
  }
  return err.message || "Terjadi kesalahan tak terduga.";
}

async function refreshSessions() {
  const data = await api("/api/sessions");
  els.sessions.innerHTML = "";
  for (const s of data.sessions) {
    const b = document.createElement("button");
    b.className = "session" + (s.id === state.sessionId ? " active" : "");
    b.innerHTML = `<div class="t">${esc(s.title)}</div>
      <div class="m"><span>${esc((s.updated_at || "").slice(0, 16).replace("T", " "))}</span>
      <span>${s.turn_count} pesan</span></div>`;
    b.onclick = () => openSession(s.id);
    const del = document.createElement("button");
    del.className = "del";
    del.textContent = "hapus";
    del.onclick = async (e) => {
      e.stopPropagation();
      await api(`/api/sessions/${s.id}`, { method: "DELETE" });
      if (state.sessionId === s.id) {
        state.sessionId = null;
        localStorage.removeItem("rag.session");
      }
      await refreshSessions();
      els.thread.innerHTML = "";
      els.title.textContent = "Chat baru";
    };
    const wrap = document.createElement("div");
    wrap.appendChild(b);
    wrap.appendChild(del);
    els.sessions.appendChild(wrap);
  }
}

async function openSession(id) {
  const s = await api(`/api/sessions/${id}`);
  state.sessionId = s.id;
  localStorage.setItem("rag.session", s.id);
  els.title.textContent = s.title;
  els.thread.innerHTML = "";
  if (!s.turns.length) {
    els.thread.innerHTML = '<div class="empty"><h2>Belum ada pesan</h2><p>Mulai bertanya di bawah.</p></div>';
  }
  for (const t of s.turns) addMessage(t.role === "user" ? "user" : "assistant", t.text, t.sources || []);
  document.body.classList.remove("nav-open");
  await refreshSessions();
}

async function refreshMeta() {
  try {
    const [charts, stats] = await Promise.all([api("/api/charts"), api("/api/stats")]);
    els.dashboardList.innerHTML = charts.dashboards.map((d) => `<option value="${esc(d)}">`).join("");
    els.stats.textContent = `${stats.count} chunk · ${stats.charts} chart · ${stats.sessions} sesi`;
  } catch (e) {
    els.stats.textContent = "Statistik tidak tersedia (index belum dibuat?)";
  }
}

els.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = els.input.value.trim();
  if (!text || state.loading) return;
  clearError();
  state.loading = true;
  els.send.disabled = true;
  addMessage("user", text);
  els.input.value = "";
  const typing = addMessage("assistant", "Menjawab…");
  try {
    const data = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        message: text,
        session_id: state.sessionId,
        dashboard_name: els.dashboardFilter.value.trim() || null,
      }),
    });
    state.sessionId = data.session_id;
    localStorage.setItem("rag.session", data.session_id);
    typing.querySelector(".md").innerHTML = renderMarkdown(data.reply);
    if (data.sources?.length) {
      const box = document.createElement("div");
      box.className = "sources";
      box.innerHTML = data.sources.map(sourceCard).join("");
      typing.appendChild(box);
    }
    els.title.textContent = text.slice(0, 60);
    await refreshSessions();
  } catch (err) {
    typing.remove();
    showError(`Gagal menjawab: ${friendlyError(err)}`);
  } finally {
    state.loading = false;
    els.send.disabled = false;
  }
});

els.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    els.form.requestSubmit();
  }
});

document.getElementById("newChatBtn").onclick = () => {
  state.sessionId = null;
  localStorage.removeItem("rag.session");
  els.title.textContent = "Chat baru";
  els.thread.innerHTML = "";
  document.body.classList.remove("nav-open");
  refreshSessions();
};

els.searchBtn.onclick = () => els.searchPanel.classList.toggle("hidden");
els.menu.onclick = () => document.body.classList.toggle("nav-open");

els.searchForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = els.searchInput.value.trim();
  if (!q) return;
  els.searchResults.innerHTML = "Mencari…";
  try {
    const data = await api("/api/search", {
      method: "POST",
      body: JSON.stringify({ query: q, dashboard_name: els.dashboardFilter.value.trim() || null }),
    });
    els.searchResults.innerHTML = data.results.length
      ? data.results.map(sourceCard).join("")
      : "Tidak ada data yang relevan.";
  } catch (err) {
    els.searchResults.textContent = `Gagal mencari: ${err.message}`;
  }
});

els.chips.innerHTML = EXAMPLES.map((x) => `<button type="button" class="chip">${esc(x)}</button>`).join("");
els.chips.querySelectorAll(".chip").forEach((c) => {
  c.onclick = () => {
    els.input.value = c.textContent;
    els.form.requestSubmit();
  };
});

refreshSessions();
refreshMeta();
if (state.sessionId) openSession(state.sessionId).catch(() => {
  state.sessionId = null;
  localStorage.removeItem("rag.session");
});
