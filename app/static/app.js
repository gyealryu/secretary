// AI 비서 화면 동작
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);
const ERROR_MARK = "\n\n[오류] ";

const state = { convId: null, busy: false, docMode: "summary" };

// ---------- 공통 ----------

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => el.classList.remove("show"), 3500);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {},
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return res.json();
}

// 스트리밍 응답을 받아 글자가 올 때마다 onText(전체 글) 호출
async function streamPost(path, body, onText) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let text = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    text += decoder.decode(value, { stream: true });
    onText(text);
  }
  return text;
}

function renderInto(el, text) {
  const idx = text.indexOf(ERROR_MARK);
  if (idx >= 0) {
    el.innerHTML = renderMarkdown(text.slice(0, idx)) +
      '<div class="error-box">' + text.slice(idx + ERROR_MARK.length).replace(/</g, "&lt;") + "</div>";
  } else {
    el.innerHTML = renderMarkdown(text);
  }
}

// 코드 블록 복사 버튼
document.addEventListener("click", (e) => {
  if (!e.target.classList.contains("copy-code")) return;
  const code = e.target.closest(".codeblock").querySelector("code").innerText;
  navigator.clipboard.writeText(code).then(() => toast("코드를 복사했어요"));
});

// 탭 전환
$$(".tab").forEach((btn) => btn.addEventListener("click", () => {
  $$(".tab").forEach((b) => b.classList.toggle("active", b === btn));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + btn.dataset.tab));
  if (btn.dataset.tab === "tasks") loadTasks();
}));

// ---------- 대화 ----------

async function loadConversations() {
  const convs = await api("/api/conversations");
  const list = $("#conv-list");
  list.innerHTML = "";
  for (const c of convs) {
    const li = document.createElement("li");
    li.className = c.id === state.convId ? "active" : "";
    li.innerHTML = '<span class="title"></span><button class="del" title="삭제">×</button>';
    li.querySelector(".title").textContent = c.title;
    li.addEventListener("click", () => openConversation(c.id));
    li.querySelector(".del").addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm("이 대화를 삭제할까요?")) return;
      await api("/api/conversations/" + c.id, { method: "DELETE" });
      if (state.convId === c.id) { state.convId = null; showMessages([]); }
      loadConversations();
    });
    list.appendChild(li);
  }
}

function addBubble(role, text) {
  $("#chat-empty")?.remove();
  const div = document.createElement("div");
  div.className = "msg " + role;
  const body = document.createElement("div");
  body.className = "md";
  if (role === "user") body.textContent = text; else renderInto(body, text);
  div.appendChild(body);
  $("#messages").appendChild(div);
  scrollDown();
  return body;
}

function scrollDown() {
  const m = $("#messages");
  m.scrollTop = m.scrollHeight;
}

function showMessages(msgs) {
  const box = $("#messages");
  box.innerHTML = msgs.length ? "" :
    '<div class="empty" id="chat-empty"><h2>무엇을 같이 고민해 볼까요?</h2><p>개발 아이디어, 웹페이지 구성, 코드 질문 무엇이든 좋아요.</p></div>';
  msgs.forEach((m) => addBubble(m.role, m.content));
}

async function openConversation(id) {
  state.convId = id;
  showMessages(await api(`/api/conversations/${id}/messages`));
  loadConversations();
  $("#chat-input").focus();
}

$("#new-chat").addEventListener("click", () => {
  state.convId = null;
  showMessages([]);
  loadConversations();
  $("#chat-input").focus();
});

async function sendChat() {
  const input = $("#chat-input");
  const content = input.value.trim();
  if (!content || state.busy) return;
  state.busy = true;
  $("#chat-send").disabled = true;
  input.value = "";
  try {
    if (!state.convId) state.convId = (await api("/api/conversations", { method: "POST" })).id;
    addBubble("user", content);
    const body = addBubble("assistant", "");
    body.innerHTML = '<span class="typing">생각하는 중…</span>';
    await streamPost(`/api/conversations/${state.convId}/chat`, { content }, (text) => {
      renderInto(body, text);
      scrollDown();
    });
    loadConversations();
  } catch (err) {
    toast(err.message);
  } finally {
    state.busy = false;
    $("#chat-send").disabled = false;
    input.focus();
  }
}

$("#chat-form").addEventListener("submit", (e) => { e.preventDefault(); sendChat(); });
$("#chat-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendChat(); }
});

// ---------- 문서 ----------

function updateDocCount() {
  const n = $("#doc-text").value.length;
  const limit = +(state.settings?.max_doc_chars || 12000);
  $("#doc-count").textContent = n ? `${n.toLocaleString()}자` +
    (n > limit ? ` · 앞부분 ${limit.toLocaleString()}자만 사용됩니다 (설정에서 변경 가능)` : "") : "";
}
$("#doc-text").addEventListener("input", updateDocCount);

async function loadFile(file) {
  $("#drop-label").textContent = `읽는 중: ${file.name}`;
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await api("/api/documents/extract", { method: "POST", body: form });
    $("#doc-text").value = res.text;
    $("#drop-label").textContent = `불러옴: ${res.filename}`;
    updateDocCount();
  } catch (err) {
    $("#drop-label").textContent = "파일을 끌어다 놓거나 클릭하세요";
    toast(err.message);
  }
}

$("#doc-file").addEventListener("change", (e) => e.target.files[0] && loadFile(e.target.files[0]));
const drop = $("#drop");
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => {
  e.preventDefault();
  drop.classList.remove("over");
  if (e.dataTransfer.files[0]) loadFile(e.dataTransfer.files[0]);
});

$$("#doc-modes .mode").forEach((btn) => btn.addEventListener("click", () => {
  state.docMode = btn.dataset.mode;
  $$("#doc-modes .mode").forEach((b) => b.classList.toggle("active", b === btn));
}));

$("#doc-run").addEventListener("click", async () => {
  const text = $("#doc-text").value;
  if (!text.trim()) return toast("문서를 넣어 주세요");
  const btn = $("#doc-run");
  const out = $("#doc-result");
  btn.disabled = true;
  out.innerHTML = '<span class="typing">작업하는 중…</span>';
  try {
    out.dataset.raw = await streamPost("/api/documents/run",
      { mode: state.docMode, text, instruction: $("#doc-instruction").value },
      (t) => renderInto(out, t));
  } catch (err) {
    out.innerHTML = "";
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
});

$("#doc-copy").addEventListener("click", () => {
  const raw = $("#doc-result").dataset.raw;
  if (raw) navigator.clipboard.writeText(raw).then(() => toast("결과를 복사했어요"));
});

// ---------- 할 일 ----------

function dueLabel(due) {
  if (!due) return "";
  const d = new Date(due.replace(" ", "T"));
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const day = new Date(d); day.setHours(0, 0, 0, 0);
  const diff = Math.round((day - today) / 86400000);
  const rel = diff === 0 ? "오늘" : diff === 1 ? "내일" : diff === -1 ? "어제" : diff < 0 ? `${-diff}일 지남` : `${diff}일 후`;
  return `${due} · ${rel}`;
}

async function loadTasks() {
  const tasks = await api("/api/tasks");
  const list = $("#task-list");
  list.innerHTML = tasks.length ? "" : '<li class="hint">할 일이 없어요</li>';
  for (const t of tasks) {
    const li = document.createElement("li");
    const overdue = !t.done && t.due && new Date(t.due.replace(" ", "T")) < new Date();
    li.className = (t.done ? "done" : "") + (overdue ? " overdue" : "");
    li.innerHTML = '<input type="checkbox"><div class="t"><div class="title"></div><div class="due"></div></div><button class="del" title="삭제">×</button>';
    li.querySelector("input").checked = !!t.done;
    li.querySelector(".title").textContent = t.title;
    li.querySelector(".due").textContent = dueLabel(t.due);
    li.querySelector("input").addEventListener("change", async (e) => {
      await api("/api/tasks/" + t.id, { method: "PATCH", body: JSON.stringify({ done: e.target.checked }) });
      loadTasks();
    });
    li.querySelector(".del").addEventListener("click", async () => {
      await api("/api/tasks/" + t.id, { method: "DELETE" });
      loadTasks();
    });
    list.appendChild(li);
  }
}

$("#task-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const title = $("#task-title").value.trim();
  if (!title) return;
  const due = $("#task-due").value.replace("T", " ") || null;
  try {
    await api("/api/tasks", { method: "POST", body: JSON.stringify({ title, due }) });
    $("#task-title").value = ""; $("#task-due").value = "";
    loadTasks();
  } catch (err) { toast(err.message); }
});

$("#task-ai-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = $("#task-ai-input").value.trim();
  if (!text) return;
  const btn = $("#task-ai-btn");
  btn.disabled = true; btn.textContent = "분석 중…";
  try {
    const res = await api("/api/tasks/parse", { method: "POST", body: JSON.stringify({ text }) });
    $("#task-ai-input").value = "";
    toast(`${res.created.length}개를 추가했어요`);
    loadTasks();
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false; btn.textContent = "추가";
  }
});

// ---------- 설정 ----------

const dialog = $("#settings");
const sform = $("#settings-form");

async function loadSettings() {
  state.settings = await api("/api/settings");
}

$("#open-settings").addEventListener("click", async () => {
  await loadSettings();
  for (const [k, v] of Object.entries(state.settings)) if (sform.elements[k]) sform.elements[k].value = v;
  $("#conn-status").textContent = "";
  dialog.showModal();
});

sform.addEventListener("submit", async (e) => {
  if (e.submitter?.value !== "save") return;
  const data = Object.fromEntries(new FormData(sform));
  data.max_doc_chars = parseInt(data.max_doc_chars, 10) || 12000;
  try {
    state.settings = await api("/api/settings", { method: "PUT", body: JSON.stringify(data) });
    toast("설정을 저장했어요");
  } catch (err) { toast(err.message); }
});

$("#test-conn").addEventListener("click", async () => {
  const status = $("#conn-status");
  // 입력 중인 주소로 확인하기 위해 먼저 저장
  const data = Object.fromEntries(new FormData(sform));
  data.max_doc_chars = parseInt(data.max_doc_chars, 10) || 12000;
  status.textContent = "확인 중…";
  try {
    state.settings = await api("/api/settings", { method: "PUT", body: JSON.stringify(data) });
    const { models } = await api("/api/models");
    $("#model-options").innerHTML = models.map((m) => `<option value="${m}">`).join("");
    const has = models.includes(data.model);
    status.textContent = `연결 성공 · 설치된 모델 ${models.length}개` +
      (has ? "" : ` · '${data.model}'은(는) 설치되어 있지 않아요 (목록: ${models.join(", ") || "없음"})`);
  } catch (err) {
    status.textContent = "연결 실패: " + err.message;
  }
});

// ---------- 시작 ----------

loadSettings();
loadConversations();
