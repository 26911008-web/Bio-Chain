/**
 * Module: AI Assistant Streaming Widget
 * Handles persona-based AI suggestions, LLM provider selection,
 * markdown streaming format, and floating action button.
 */
// ==============================================================
// ASISTEN AI — jawaban mengalir (streaming); konteks data dibatasi peran di server.
// Teks model dirender sebagai teks (esc) + markdown minimal; tidak ada HTML dari model yang dieksekusi.
// ==============================================================
const AI_SUGGEST = {
  petani: ["Bagaimana agar biomassa saya naik ke Grade A?", "Kapan waktu terbaik melapor stok?", "Apa manfaat abu bottom ash untuk sawah?"],
  pengepul: ["Antrean mana yang sebaiknya diverifikasi dulu?", "Cara cepat menilai kadar air di lapangan?", "Bagaimana menekan susut timbangan?"],
  driver: ["Tips muat biomassa agar bak truk optimal?", "Apa yang harus dicek saat scan QR?", "Bagaimana jika sinyal hilang di jalan?"],
  pabrik: ["Saran optimasi pasokan minggu ini?", "Bagaimana menekan susut pengepul→pabrik?", "Strategi blending untuk biomassa basah?"],
  auditor: ["Ringkas temuan neraca massa saat ini.", "Indikator kecurangan timbangan apa yang perlu dipantau?"],
  admin: ["Ringkas kondisi rantai pasok hari ini.", "Apa risiko operasional terbesar saat ini?"],
};
const AI = { history: [], providers: [], busy: false, quota: null };
// Hemat token: server hanya memakai 3 pesan terakhir (AI_HISTORY_MESSAGES); kirim sebanyak itu saja.
const AI_HISTORY_SEND = 3;

function aiQuotaNote() {
  const q = AI.quota;
  return q && q.limit ? ` · sisa kuota hari ini ${q.remaining}/${q.limit}` : "";
}

function aiFormat(text) {
  return esc(text)
    .replace(/(?:^|\n)###\s*(.+?)(?=\n|$)/g, "<h4>$1</h4>")
    .replace(/(?:^|\n)##\s*(.+?)(?=\n|$)/g, "<h3>$1</h3>")
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/(^|\n)\s*[-*]\s+/g, "$1• ")
    .replace(/\n/g, "<br>");
}

function aiStore(key, val) { try { val === undefined ? localStorage.removeItem(key) : localStorage.setItem(key, val); } catch {} }
function aiLoad(key) { try { return localStorage.getItem(key); } catch { return null; } }

function aiEnsureWidget() {
  if ($("ai-fab")) return;
  const fab = document.createElement("button");
  fab.id = "ai-fab";
  fab.type = "button";
  fab.innerHTML = '<span aria-hidden="true">🤖</span><span class="fab-label">Asisten</span>';
  fab.setAttribute("aria-label", "Asisten AI");
  fab.setAttribute("aria-controls", "ai-panel");
  document.body.appendChild(fab);

  const panel = document.createElement("div");
  panel.id = "ai-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Asisten AI Bio-Chain");
  panel.innerHTML = `
    <div class="ai-head">
      <strong style="font-size:14px;">🤖 Asisten Bio-Chain</strong>
      <span style="flex:1"></span>
      <button type="button" class="btn btn-secondary btn-sm" id="ai-clear" title="Mulai percakapan baru">↺</button>
      <button type="button" class="btn btn-secondary btn-sm" id="ai-close" aria-label="Tutup">✕</button>
      <div style="display:flex; gap:8px; width:100%;">
        <select id="ai-provider" aria-label="Penyedia AI"></select>
        <select id="ai-model" aria-label="Model"></select>
      </div>
    </div>
    <div class="ai-log" id="ai-log" aria-live="polite"></div>
    <div class="ai-chips" id="ai-chips"></div>
    <div class="ai-meta" id="ai-meta"></div>
    <form class="ai-form" id="ai-form">
      <textarea id="ai-input" placeholder="Tanya atau minta saran optimasi…" maxlength="2000"></textarea>
      <button type="submit" class="btn btn-primary" id="ai-send">Kirim</button>
    </form>`;
  document.body.appendChild(panel);

  fab.onclick = () => { panel.classList.toggle("open"); if (panel.classList.contains("open")) { aiInitProviders(); $("ai-input").focus(); } };
  $("ai-close").onclick = () => panel.classList.remove("open");
  $("ai-clear").onclick = aiReset;
  $("ai-provider").onchange = () => { aiStore("ai_provider", $("ai-provider").value); aiLoadModels(); };
  $("ai-model").onchange = () => aiStore(`ai_model_${$("ai-provider").value}`, $("ai-model").value);
  $("ai-form").onsubmit = e => { e.preventDefault(); aiSend($("ai-input").value); };
  $("ai-input").onkeydown = e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); aiSend($("ai-input").value); } };
}

function aiShow(loggedIn) {
  aiEnsureWidget();
  $("ai-fab").style.display = loggedIn ? "inline-flex" : "none";
  if (!loggedIn) $("ai-panel").classList.remove("open");
  aiReset();
  AI.providers = [];
}

function aiReset() {
  AI.history = [];
  if (!$("ai-log")) return;
  const role = STATE.user && STATE.user.role;
  $("ai-log").innerHTML = `<div class="ai-msg bot">Halo${STATE.user ? ", " + esc(STATE.user.full_name) : ""}! Saya bisa menjawab pertanyaan dan memberi saran optimasi berdasarkan data peran <b>${esc(role || "")}</b> Anda. Saya tidak bisa mengubah data.</div>`;
  $("ai-chips").innerHTML = (AI_SUGGEST[role] || []).map((q, i) =>
    `<span class="demo-chip" data-i="${i}">${esc(q)}</span>`).join("");
  $("ai-chips").querySelectorAll(".demo-chip").forEach(c => { c.onclick = () => aiSend(AI_SUGGEST[role][Number(c.dataset.i)]); });
}

async function aiInitProviders() {
  if (AI.providers.length) return;
  try {
    const r = await api("/api/v1/assistant/providers");
    AI.providers = r.providers;
    AI.quota = r.quota || null;
    const saved = aiLoad("ai_provider");
    const pick = AI.providers.find(p => p.id === saved && p.configured) ? saved : r.default;
    $("ai-provider").innerHTML = AI.providers.map(p =>
      `<option value="${esc(p.id)}" ${p.configured ? "" : "disabled"} ${p.id === pick ? "selected" : ""}>${esc(p.label)}${p.configured ? "" : " (belum diatur)"}</option>`).join("");
    aiLoadModels();
  } catch (err) {
    $("ai-meta").textContent = "Gagal memuat daftar penyedia: " + err.message;
  }
}

async function aiLoadModels() {
  const pid = $("ai-provider").value;
  const prov = AI.providers.find(p => p.id === pid) || {};
  const saved = aiLoad(`ai_model_${pid}`) || prov.default_model;
  $("ai-model").innerHTML = saved ? `<option>${esc(saved)}</option>` : `<option value="">memuat model…</option>`;
  $("ai-meta").textContent = (prov.note || "") + aiQuotaNote();
  try {
    const r = await api(`/api/v1/assistant/providers/${encodeURIComponent(pid)}/models`);
    const models = r.models.length ? r.models : (saved ? [saved] : []);
    $("ai-model").innerHTML = models.map(m => `<option ${m === saved ? "selected" : ""}>${esc(m)}</option>`).join("")
      || `<option value="">(tidak ada model)</option>`;
    if (saved && !models.includes(saved)) $("ai-meta").textContent = `Model ${saved} tidak ditemukan; pilih dari daftar.`;
  } catch (err) {
    $("ai-meta").textContent = err.message;          // mis. Ollama belum jalan / kunci ditolak
  }
}

async function aiSend(text) {
  text = (text || "").trim();
  if (!text || AI.busy) return;
  AI.busy = true;
  $("ai-send").disabled = true;
  $("ai-input").value = "";
  const log = $("ai-log");
  log.insertAdjacentHTML("beforeend", `<div class="ai-msg user">${esc(text)}</div>`);
  const bubble = document.createElement("div");
  bubble.className = "ai-msg bot";
  bubble.textContent = "⏳ Berpikir…";
  log.appendChild(bubble);
  log.scrollTop = log.scrollHeight;

  const started = Date.now();
  let answer = "";
  try {
    const res = await apiRaw("/api/v1/assistant/chat/stream", { timeoutMs: 30000,
      body: { message: text, history: AI.history.slice(-AI_HISTORY_SEND),
              provider: $("ai-provider").value || undefined, model: $("ai-model").value || undefined } });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      answer += decoder.decode(value, { stream: true });
      bubble.innerHTML = aiFormat(answer);
      log.scrollTop = log.scrollHeight;
    }
    if (!answer.trim()) throw new Error("Model tidak mengembalikan jawaban.");
    AI.history.push({ role: "user", content: text }, { role: "assistant", content: answer.slice(0, 4000) });
    const left = res.headers.get("X-AI-Quota-Remaining");
    if (AI.quota && left !== null) AI.quota.remaining = Number(left);
    $("ai-meta").textContent = `${res.headers.get("X-AI-Provider")} · ${res.headers.get("X-AI-Model")} · ${((Date.now() - started) / 1000).toFixed(1)} s${aiQuotaNote()}`;
  } catch (err) {
    bubble.className = "ai-msg err";
    bubble.textContent = err.message === "Failed to fetch" ? "Tidak ada koneksi ke server." : err.message;
  } finally {
    AI.busy = false;
    $("ai-send").disabled = false;
  }
}

