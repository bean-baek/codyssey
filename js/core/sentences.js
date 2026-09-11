/**
 * js/core/sentences.js — 원고를 문장 단위로 나눈다.
 *
 * offset(start/end)을 함께 돌려주는 것이 이 모듈의 존재 이유다.
 * 서버는 index만 받아 suggestions[i].index로 답하고, 화면은 그 index로
 * 원문의 어느 구간을 갈아끼울지 알아야 한다. 문자열을 다시 찾는 방식은
 * 같은 문장이 두 번 나오면 엉뚱한 곳을 고치므로 쓰지 않는다.
 */

/** 서버 상한과 맞춘다 (api/revise.py MAX_SENTENCES) */
export const MAX_SENTENCES = 300;

/**
 * 문장 끝으로 인정하는 부호.
 *
 * 줄임표(…)는 넣지 않는다. 한국어에서 '그래서…… 갔다.'처럼 문장 중간의 쉼으로
 * 쓰이는 경우가 더 흔해서, 종결로 보면 멀쩡한 문장이 토막 난다.
 * 줄임표로 끝나는 문장은 뒤에 마침표를 찍는 것이 원칙이므로 그때는 정상 분해된다.
 * api/revise.py 의 폐기 규칙도 같은 기준을 쓴다.
 */
const TERMINATORS = new Set(['.', '!', '?']);

/** 종결 부호 앞뒤에 붙어도 같은 덩어리로 삼키는 부호 */
const ABSORB = new Set(['.', '!', '?', '…']);

/** 종결 부호 뒤에 붙어도 같은 문장으로 보는 닫는 기호 */
const TRAILING = new Set(['"', "'", '”', '’', '」', '』', ')', ']', '》', '〉']);

/**
 * @param {string} text
 * @returns {{text: string, start: number, end: number}[]}
 */
export function splitSentences(text) {
  const source = text || '';
  const out = [];

  let cursor = 0; // 현재 문장이 시작된 위치
  let i = 0;

  while (i < source.length) {
    const ch = source[i];

    if (!TERMINATORS.has(ch)) {
      i += 1;
      continue;
    }

    // "?!", ".…" 처럼 부호가 이어지면 끝까지 삼킨다
    let end = i + 1;
    while (end < source.length && ABSORB.has(source[end])) end += 1;

    // 닫는 따옴표·괄호는 앞 문장에 붙인다
    while (end < source.length && TRAILING.has(source[end])) end += 1;

    // 부호 뒤가 공백이나 글 끝이어야 문장 경계다.
    // 이 조건이 "3.5초", "a.m." 같은 것을 문장으로 쪼개지 않게 막는다.
    const next = source[end];
    if (next !== undefined && !/\s/.test(next)) {
      i = end;
      continue;
    }

    push(out, source, cursor, end);
    // 문장 사이 공백은 다음 문장에 넣지 않는다
    while (end < source.length && /\s/.test(source[end])) end += 1;
    cursor = end;
    i = end;
  }

  // 종결 부호 없이 끝난 마지막 덩어리
  if (cursor < source.length) push(out, source, cursor, source.length);

  return out.slice(0, MAX_SENTENCES);
}

function push(out, source, start, end) {
  const raw = source.slice(start, end);
  const trimmed = raw.trim();
  if (!trimmed) return;

  // 앞뒤 공백을 뺀 실제 구간으로 offset을 보정한다
  const lead = raw.length - raw.trimStart().length;
  const tail = raw.length - raw.trimEnd().length;
  out.push({ text: trimmed, start: start + lead, end: end - tail });
}

/**
 * 제안들을 원문에 한꺼번에 적용한다.
 *
 * 뒤에서부터 갈아끼운다. 앞에서부터 하면 첫 치환 순간 뒤쪽 offset이 전부 밀린다.
 *
 * @param {string} text 원문
 * @param {{text:string,start:number,end:number}[]} sentences splitSentences 결과
 * @param {{index:number, revised:string}[]} applied 적용할 제안
 * @returns {string}
 */
export function applySuggestions(text, sentences, applied) {
  const ordered = [...applied]
    .filter((s) => sentences[s.index])
    .sort((a, b) => b.index - a.index);

  let out = text;
  for (const { index, revised } of ordered) {
    const { start, end } = sentences[index];
    out = out.slice(0, start) + revised + out.slice(end);
  }
  return out;
}
