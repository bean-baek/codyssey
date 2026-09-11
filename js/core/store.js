/**
 * js/core/store.js — 편집 방침 보관
 *
 * localStorage는 사파리 시크릿 창이나 사이트 데이터 차단 설정에서
 * 읽기·쓰기 자체가 예외를 던진다. 방침이 저장되지 않는 것은 불편할 뿐이지만
 * 그 예외로 화면이 통째로 죽으면 안 되므로 전부 감싼다.
 */

const KEY = 'gyeol.persona.v1';

export const DEFAULT_PERSONA = {
  tone: 'neutral',
  maxSuggestions: 10,
  focusTypes: ['리듬', '중복', '모호', '군더더기', '호응'],
  lengthPreference: 'keep',
  protect: [],
  note: '',
};

export function loadPersona() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULT_PERSONA };
    return { ...DEFAULT_PERSONA, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_PERSONA };
  }
}

export function savePersona(persona) {
  try {
    localStorage.setItem(KEY, JSON.stringify(persona));
  } catch {
    /* 저장 못 해도 이번 세션 동안은 그대로 쓴다 */
  }
}

export function clearPersona() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* 무시 */
  }
}
