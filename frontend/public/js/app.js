import { api, ApiError } from "./api.js";
import { renderSignal, escapeHtml } from "./chart.js";

const $ = (s) => document.querySelector(s);
const fmt = (n) => Math.round(n).toLocaleString("ko-KR");
const PAGE = 30;

const state = {
  conversationId: null,
  conversations: [],
  rows: [],          // 날짜 내림차순 전체
  shown: PAGE,
  stats: null,
  sending: false,
};

/* ---------------- 공통 ---------------- */
let toastTimer;
function toast(msg, isErr = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.toggle("err", isErr);
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 3200);
}

function setStatus(stateName, text) {
  const s = $("#server-status");
  s.dataset.state = stateName;
  s.textContent = text;
}

// 아주 작은 마크다운: **굵게**, 줄바꿈, "- " 목록. HTML 은 먼저 이스케이프해서 XSS 를 막는다.
function renderMarkdown(text) {
  const blocks = escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").split(/\n{2,}/);
  return blocks.map((b) => {
    const lines = b.split("\n");
    if (lines.every((l) => /^\s*[-•*]\s+/.test(l))) {
      return "<ul>" + lines.map((l) => `<li>${l.replace(/^\s*[-•*]\s+/, "")}</li>`).join("") + "</ul>";
    }
    return `<p>${lines.join("<br>")}</p>`;
  }).join("");
}

/* ---------------- 테마 ---------------- */
function initTheme() {
  $("#theme-toggle").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch {}
  });
}

/* ---------------- 모바일 탭 ---------------- */
function initTabs() {
  document.querySelectorAll(".mobile-tabs button").forEach((b) => b.addEventListener("click", () => showPane(b.dataset.pane)));
}
function showPane(name) {
  document.querySelectorAll(".mobile-tabs button").forEach((b) => b.setAttribute("aria-current", String(b.dataset.pane === name)));
  document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("is-active", p.dataset.pane === name));
}

/* ---------------- 서버 깨우기(콜드스타트) ---------------- */
async function wake() {
  setStatus("pending", "서버 연결 중");
  const slow = setTimeout(() => { $("#wake-banner").hidden = false; setStatus("waking", "서버 깨우는 중"); }, 2500);
  try {
    const h = await api.health();
    setStatus("ok", h.storage === "firestore" ? "연결됨" : "연결됨 (메모리 저장소)");
    const badge = $("#model-badge");
    badge.textContent = h.model === "offline-demo" ? "데모 모드: GPT 키 없음" : h.model;
    badge.classList.toggle("demo", h.model === "offline-demo");
    badge.hidden = false;
    return true;
  } catch (e) {
    setStatus("error", "연결 실패");
    toast(e.message, true);
    return false;
  } finally {
    clearTimeout(slow);
    $("#wake-banner").hidden = true;
  }
}

/* ---------------- 요약·통계·그래프 ---------------- */
async function loadSummary() {
  const [s, st] = await Promise.all([api.summary(), api.statistics()]);
  state.stats = st;
  const set = (k, html, dir) => { const dd = $(`#summary dd[data-k="${k}"]`); dd.innerHTML = html; if (dir) dd.dataset.dir = dir; };
  if (!s.count) {
    for (const k of ["period", "count", "average", "max", "min", "trend", "volatility"]) set(k, "–");
  } else {
    const m = s.metrics;
    set("period", `${s.start.replaceAll("-", ".")} ~ ${s.end.replaceAll("-", ".")}`);
    set("count", `${fmt(s.count)}<small>일</small>`);
    set("average", `${fmt(m.average)}<small>회</small>`);
    set("max", `${fmt(m.max.value)}<small>${m.max.date}</small>`);
    set("min", `${fmt(m.min.value)}<small>${m.min.date}</small>`);
    set("trend", escapeHtml(s.trend.label), s.trend.direction);
    set("volatility", st.volatility_pct == null ? "–" : `하루 변화율 표준편차 ${st.volatility_pct}%`);
  }
  drawSignal();
}

function drawSignal() {
  const memos = new Map(state.rows.filter((r) => r.memo).map((r) => [r.date, r.memo]));
  renderSignal($("#signal-chart"), $("#signal-readout"), state.stats?.series || [], memos);
}

/* ---------------- 데이터 관리 ---------------- */
async function loadData() {
  const res = await api.listData({ order: "desc" });
  state.rows = res.items;
  renderRows();
}

function filteredRows() {
  const m = $("#data-filter").value;
  return m ? state.rows.filter((r) => r.date.startsWith(m)) : state.rows;
}

function renderRows(flashId) {
  const rows = filteredRows();
  const body = $("#data-rows");
  body.replaceChildren(...rows.slice(0, state.shown).map((r) => {
    const tr = document.createElement("tr");
    tr.dataset.id = r.id;
    if (r.id === flashId) tr.className = "flash";
    tr.innerHTML = `<td>${r.date}</td><td class="num">${fmt(r.value)}</td><td class="memo">${escapeHtml(r.memo || "")}</td>
      <td class="row-actions"><button type="button" data-act="edit">수정</button><button type="button" data-act="del">삭제</button></td>`;
    return tr;
  }));
  $("#data-count").textContent = `${fmt(rows.length)}건${$("#data-filter").value ? " (필터)" : ""}`;
  $("#data-more").hidden = rows.length <= state.shown;
}

function startEdit(row) {
  $("#edit-id").value = row.id;
  $("#f-date").value = row.date;
  $("#f-value").value = row.value;
  $("#f-memo").value = row.memo || "";
  $("#data-submit").textContent = "수정 저장";
  $("#data-cancel").hidden = false;
  $("#data-form").classList.add("editing");
  setFormMsg("");
  $("#f-value").focus();
}

function resetForm() {
  $("#data-form").reset();
  $("#edit-id").value = "";
  $("#data-submit").textContent = "추가";
  $("#data-cancel").hidden = true;
  $("#data-form").classList.remove("editing");
}

function setFormMsg(text, kind = "") {
  const m = $("#data-msg");
  m.textContent = text;
  m.className = `form-msg ${kind}`;
}

async function afterDataChange(flashId) {
  await loadData();
  await loadSummary();
  renderRows(flashId);
}

function initData() {
  $("#export-csv").href = api.exportUrl("csv");
  $("#export-json").href = api.exportUrl("json");

  $("#data-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = $("#edit-id").value;
    const body = { date: $("#f-date").value, value: Number($("#f-value").value), memo: $("#f-memo").value.trim() };
    const btn = $("#data-submit");
    btn.disabled = true;
    try {
      const row = id ? await api.updateData(id, body) : await api.createData(body);
      setFormMsg(id ? `${row.date} 수정했습니다` : `${row.date} 추가했습니다`, "ok");
      resetForm();
      $("#data-filter").value = "";
      await afterDataChange(row.id);
    } catch (err) {
      setFormMsg(err.message, "err");
    } finally {
      btn.disabled = false;
    }
  });
  $("#data-cancel").addEventListener("click", () => { resetForm(); setFormMsg(""); });

  $("#data-rows").addEventListener("click", async (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    const id = btn.closest("tr").dataset.id;
    const row = state.rows.find((r) => r.id === id);
    if (btn.dataset.act === "edit") return startEdit(row);
    // 삭제는 두 번 눌러 확인(브라우저 confirm 창 대신)
    if (!btn.classList.contains("confirm")) {
      btn.classList.add("confirm");
      btn.textContent = "정말 삭제";
      setTimeout(() => { btn.classList.remove("confirm"); btn.textContent = "삭제"; }, 3000);
      return;
    }
    try {
      await api.deleteData(id);
      toast(`${row.date} 데이터를 삭제했습니다`);
      if ($("#edit-id").value === id) resetForm();
      await afterDataChange();
    } catch (err) {
      toast(err.message, true);
    }
  });

  $("#data-filter").addEventListener("change", () => { state.shown = PAGE; renderRows(); });
  $("#data-more").addEventListener("click", () => { state.shown += PAGE; renderRows(); });
}

/* ---------------- 대화 기록 ---------------- */
async function loadConversations() {
  const res = await api.listConversations();
  state.conversations = res.items;
  renderConversations();
}

function renderConversations() {
  const list = $("#conv-list");
  $("#conv-empty").hidden = state.conversations.length > 0;
  list.replaceChildren(...state.conversations.map((c) => {
    const li = document.createElement("li");
    li.className = "conv-item";
    li.dataset.id = c.id;
    li.setAttribute("aria-current", String(c.id === state.conversationId));
    const when = c.updated_at ? new Date(c.updated_at).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
    li.innerHTML = `<button type="button" class="open"><span class="conv-title">${escapeHtml(c.title || "제목 없음")}</span>
      <span class="conv-meta">${when} · 메시지 ${c.message_count}개</span></button>
      <button type="button" class="del" aria-label="대화 삭제">삭제</button>`;
    return li;
  }));
}

async function openConversation(id) {
  try {
    const c = await api.getConversation(id);
    state.conversationId = c.id;
    $("#chat-title").textContent = c.title || "대화";
    const box = $("#messages");
    box.replaceChildren();
    for (const m of c.messages) appendMessage(m.role, m.content, (m.tools || []).map((name) => ({ name })));
    box.scrollTop = box.scrollHeight;
    renderConversations();
    showPane("chat");
  } catch (e) {
    toast(e.message, true);
  }
}

function newChat() {
  state.conversationId = null;
  $("#chat-title").textContent = "새 대화";
  const box = $("#messages");
  box.replaceChildren(introNode);
  renderConversations();
  showPane("chat");
  $("#chat-input").focus();
}

function initHistory() {
  $("#new-chat").addEventListener("click", newChat);
  $("#conv-list").addEventListener("click", async (e) => {
    const li = e.target.closest(".conv-item");
    if (!li) return;
    if (e.target.closest(".open")) return openConversation(li.dataset.id);
    const del = e.target.closest(".del");
    if (!del) return;
    if (!del.classList.contains("confirm")) {
      del.classList.add("confirm");
      del.textContent = "확인";
      setTimeout(() => { del.classList.remove("confirm"); del.textContent = "삭제"; }, 3000);
      return;
    }
    try {
      await api.deleteConversation(li.dataset.id);
      if (state.conversationId === li.dataset.id) newChat();
      await loadConversations();
      toast("대화를 삭제했습니다");
    } catch (err) {
      toast(err.message, true);
    }
  });
}

/* ---------------- 채팅 ---------------- */
let introNode;

function appendMessage(role, content, tools = [], isError = false) {
  const box = $("#messages");
  $("#intro")?.remove();
  const div = document.createElement("div");
  div.className = `msg ${role}${isError ? " error" : ""}`;
  if (role === "user") {
    div.textContent = content;
  } else {
    div.innerHTML = `<div class="body">${renderMarkdown(content)}</div>`;
    if (tools.length) {
      const t = document.createElement("div");
      t.className = "tools";
      t.innerHTML = tools.map((x) => `<span class="tool" title="${escapeHtml(x.reason || "")}">도구 <b>${escapeHtml(x.name)}</b>${x.reason ? ` ${escapeHtml(x.reason)}` : ""}</span>`).join("");
      div.append(t);
    }
  }
  box.append(div);
  box.scrollTop = box.scrollHeight;
  return div;
}

function showTyping() {
  const div = document.createElement("div");
  div.className = "msg assistant";
  div.innerHTML = `<span class="typing" role="status"><i></i><i></i><i></i> 데이터 요약을 보고 답을 쓰는 중</span>`;
  $("#messages").append(div);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return div;
}

async function send(text) {
  if (state.sending || !text.trim()) return;
  state.sending = true;
  const input = $("#chat-input");
  const btn = $("#send-btn");
  btn.disabled = true;
  input.value = "";
  autoGrow();
  appendMessage("user", text);
  const typing = showTyping();
  try {
    const res = await api.chat(text, state.conversationId);
    typing.remove();
    appendMessage("assistant", res.reply, res.tool_calls);
    const isNew = state.conversationId !== res.conversation_id;
    state.conversationId = res.conversation_id;
    if (isNew) $("#chat-title").textContent = text.length > 40 ? text.slice(0, 39) + "…" : text;
    await loadConversations();
  } catch (e) {
    typing.remove();
    appendMessage("assistant", e instanceof ApiError ? e.message : "알 수 없는 오류가 발생했습니다.", [], true);
    input.value = text;           // 실패하면 질문을 되돌려 다시 보낼 수 있게
    autoGrow();
  } finally {
    state.sending = false;
    btn.disabled = false;
    input.focus();
  }
}

function autoGrow() {
  const t = $("#chat-input");
  t.style.height = "auto";
  t.style.height = Math.min(t.scrollHeight, 160) + "px";
  t.style.overflowY = t.scrollHeight > 160 ? "auto" : "hidden";
}

function initChat() {
  introNode = $("#intro");
  $("#chat-form").addEventListener("submit", (e) => { e.preventDefault(); send($("#chat-input").value); });
  $("#chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(e.target.value); }
  });
  $("#chat-input").addEventListener("input", autoGrow);
  introNode.addEventListener("click", (e) => { const b = e.target.closest(".suggest"); if (b) send(b.textContent); });
}

/* ---------------- 시작 ---------------- */
async function main() {
  initTheme(); initTabs(); initChat(); initHistory(); initData();
  let resizeTimer;
  addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(drawSignal, 150); });
  if (!(await wake())) return;
  try {
    await loadData();
    await Promise.all([loadSummary(), loadConversations()]);
  } catch (e) {
    toast(e.message, true);
  }
}

main();
