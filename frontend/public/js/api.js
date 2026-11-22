// 백엔드 호출. API_BASE_URL 은 config.js(배포 시 Vercel 환경 변수로 생성)에서 온다.
export const API_BASE = (window.APP_CONFIG?.API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

function detailText(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // Pydantic 422: [{loc:[..., "value"], msg: "..."}]
    return detail.map((d) => `${(d.loc || []).filter((x) => x !== "body").join(".")}: ${d.msg}`).join(" / ");
  }
  return "";
}

async function request(path, { method = "GET", body, timeout = 70000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout);
  let res;
  try {
    res = await fetch(API_BASE + path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
  } catch (e) {
    throw new ApiError(e.name === "AbortError"
      ? "서버 응답이 너무 늦습니다. 잠시 후 다시 시도하세요."
      : "서버에 연결할 수 없습니다. 주소(API_BASE_URL)와 서버 상태를 확인하세요.", 0);
  } finally {
    clearTimeout(timer);
  }
  const data = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (!res.ok) throw new ApiError(detailText(data?.detail) || `요청 실패 (${res.status})`, res.status);
  return data;
}

export const api = {
  health: () => request("/api/health", { timeout: 90000 }),
  summary: () => request("/api/data/summary"),
  statistics: () => request("/api/data/statistics"),
  listData: (params = {}) => request("/api/data?" + new URLSearchParams(params)),
  createData: (body) => request("/api/data", { method: "POST", body }),
  updateData: (id, body) => request(`/api/data/${encodeURIComponent(id)}`, { method: "PUT", body }),
  deleteData: (id) => request(`/api/data/${encodeURIComponent(id)}`, { method: "DELETE" }),
  exportUrl: (format) => `${API_BASE}/api/data/export?format=${format}`,
  listConversations: () => request("/api/conversations"),
  getConversation: (id) => request(`/api/conversations/${encodeURIComponent(id)}`),
  deleteConversation: (id) => request(`/api/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),
  chat: (message, conversation_id) => request("/api/chat", { method: "POST", body: { message, conversation_id }, timeout: 90000 }),
};
