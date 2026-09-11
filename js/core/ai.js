/**
 * js/core/ai.js — 모든 AI 호출의 단일 창구
 *
 * 확장은 fetch를 직접 쓰지 않고 ctx.ai.request()만 호출한다.
 * 타임아웃·재시도·연타 방지·오류 문구가 전부 여기 한 곳에 모인다.
 * 확장이 늘어도 실패 처리 코드는 늘지 않는다.
 */

const TIMEOUT = { revise: 20000, assist: 8000 };
const MAX_TEXT = 5000;
const MIN_TEXT = 30;

const MESSAGES = {
  EMPTY_INPUT: '퇴고할 글을 붙여넣어 주세요.',
  TOO_LONG: (n) => `문단을 나눠 요청해 주세요 (현재 ${n.toLocaleString()}자)`,
  RATE_LIMITED: '요청이 몰리고 있습니다. 잠시 후 다시 시도해 주세요.',
  UPSTREAM_ERROR: '잠시 후 다시 시도해 주세요.',
  BAD_SCHEMA: '잠시 후 다시 시도해 주세요.',
  TIMEOUT: '응답이 늦어집니다. 다시 시도해 주세요.',
  BUSY: '이전 요청을 처리하고 있습니다.',
  OFFLINE: '네트워크에 연결되어 있지 않습니다.',
};

/** 진행 중인 요청. 연타로 인한 중복 과금을 막는다. */
const inflight = new Map();

class AIError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

async function call(endpoint, payload, { timeout, retry }) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(`/api/${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    let data;
    try {
      data = await res.json();
    } catch {
      throw new AIError('BAD_SCHEMA', MESSAGES.BAD_SCHEMA);
    }

    if (!res.ok) {
      const code = data?.error?.code || 'UPSTREAM_ERROR';
      // 5xx만 1회 재시도한다. 4xx는 다시 보내도 같은 결과다.
      if (retry > 0 && res.status >= 500) {
        return call(endpoint, payload, { timeout, retry: retry - 1 });
      }
      const msg =
        code === 'TOO_LONG'
          ? MESSAGES.TOO_LONG(data.error.length ?? 0)
          : MESSAGES[code] || MESSAGES.UPSTREAM_ERROR;
      throw new AIError(code, msg);
    }

    return data;
  } catch (err) {
    if (err instanceof AIError) throw err;
    if (err.name === 'AbortError') throw new AIError('TIMEOUT', MESSAGES.TIMEOUT);
    if (!navigator.onLine) throw new AIError('OFFLINE', MESSAGES.OFFLINE);
    if (retry > 0) return call(endpoint, payload, { timeout, retry: retry - 1 });
    throw new AIError('UPSTREAM_ERROR', MESSAGES.UPSTREAM_ERROR);
  } finally {
    clearTimeout(timer);
  }
}

/** 같은 키의 요청이 진행 중이면 새 호출을 만들지 않고 그것을 돌려준다. */
function dedupe(key, fn) {
  if (inflight.has(key)) return Promise.reject(new AIError('BUSY', MESSAGES.BUSY));
  const p = fn().finally(() => inflight.delete(key));
  inflight.set(key, p);
  return p;
}

/**
 * 퇴고 요청
 * @returns {Promise<{suggestions: Array}>}
 */
export function revise({ text, sentences, persona }) {
  const trimmed = (text || '').trim();
  if (trimmed.length < MIN_TEXT) {
    return Promise.reject(new AIError('EMPTY_INPUT', MESSAGES.EMPTY_INPUT));
  }
  if (trimmed.length > MAX_TEXT) {
    return Promise.reject(new AIError('TOO_LONG', MESSAGES.TOO_LONG(trimmed.length)));
  }

  return dedupe('revise', () =>
    call('revise', { text: trimmed, sentences, persona }, {
      timeout: TIMEOUT.revise,
      retry: 1,
    })
  );
}

/**
 * 도우미 요청
 * @param {'synonym'|'recall'|'impression'|'classify'} mode
 * @returns {Promise<{mode: string, candidates: string[]}>}
 */
export function assist(mode, { query, context } = {}) {
  if (!query || !query.trim()) {
    return Promise.reject(new AIError('EMPTY_INPUT', '찾을 내용을 입력해 주세요.'));
  }

  return dedupe(`assist:${mode}`, () =>
    call('assist', { mode, query: query.trim(), context }, {
      timeout: TIMEOUT.assist,
      retry: 0, // 빠른 실패가 낫다. 사용자는 다시 입력하면 된다.
    })
  );
}

/** 진행 중 여부 — 버튼 비활성화·스피너 표시에 사용 */
export function isBusy(key = 'revise') {
  return inflight.has(key);
}

/** 확장에 넘길 ctx.ai 구현체 */
export function createAIContext() {
  return {
    request(mode, payload) {
      return mode === 'revise' ? revise(payload) : assist(mode, payload);
    },
    isBusy,
  };
}

export { AIError };
