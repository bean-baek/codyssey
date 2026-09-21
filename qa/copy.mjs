/**
 * qa/copy.mjs — 화면 문구 검사
 *
 * 맞춤법 검사기를 통째로 붙이지 않는다. 대신 이 저장소에서 실제로 틀리기 쉬운
 * 패턴만 규칙으로 둔다. 오탐이 많으면 아무도 보고서를 안 읽게 되므로,
 * 확실한 것만 넣고 애매한 것은 규칙에서 뺀다.
 *
 * 규칙은 { id, severity, test(text) → [{ found, suggest, why }] } 형태다.
 * severity: 'error' 는 틀린 것, 'warn' 은 일관성 문제.
 */

/** 한국어에서 자주 틀리는 표기 — 좌: 틀림, 우: 맞음 */
const SPELLING = [
  ['되요', '돼요'],
  ['안되', '안 되'],
  ['어떻해', '어떡해'],
  ['희안', '기이'],
  ['금새', '금세'],
  ['왠만', '웬만'],
  ['왠지모르', '왠지 모르'],
  ['오랫만', '오랜만'],
  ['일일히', '일일이'],
  ['며칠날', '며칟날'],
  ['바램', '바람'],
  ['역활', '역할'],
  ['설겆이', '설거지'],
  ['깨끗히', '깨끗이'],
  ['틀리다 ', '다르다 '],
];

/**
 * 띄어쓰기 — 정규식과 고칠 말.
 * 긴 규칙을 앞에 둔다. 겹치는 구간은 앞선 것만 세고 뒤는 버린다.
 * ('할수있습니다' 를 세 규칙이 각각 잡아 한 오류를 3건으로 부풀리던 문제)
 */
const SPACING = [
  [/할\s?수\s?없습니다/g, null],          // 이미 맞는 형태 — 자리만 잡아 뒤 규칙을 막는다
  [/할수\s?있습니다/g, '할 수 있습니다'],
  [/할수있/g, '할 수 있'],
  [/([가-힣])수있/g, '$1 수 있'],
  [/([가-힣])것입니다/g, '$1 것입니다'],
  [/([가-힣])보다더/g, '$1보다 더'],
];

/**
 * 이 제품에서 쓰기로 한 말 — 섞여 쓰이면 경고.
 *
 * variants 는 { word, unless } 로 쓸 수 있다. unless 에 걸리면 넘어간다.
 * 오탐이 한 번 쌓이면 보고서 전체를 안 읽게 되므로, 확실할 때만 올린다.
 * 실제로 걸렸던 오탐을 그대로 규칙에 반영해 둔다.
 */
const TERMS = [
  { canonical: '원고', why: '원고로 통일합니다',
    variants: [{ word: '원본 글' }, { word: '글감' }] },
  { canonical: '제안', why: '제안으로 통일합니다',
    variants: [{ word: '제안사항' }] },
  { canonical: '편집 방침', why: '화면에서는 편집 방침으로 부릅니다',
    variants: [
      // '엔드포인트 설정', '앱 설정' 처럼 다른 층을 가리키는 복합어는 제외한다
      { word: '설정', unless: /(엔드포인트|앱|플랫폼|환경 ?변수|초기|기본|에이전트|권한|언어)\s*설정|설정\s*(파일|값|법|방법)/ },
      { word: '페르소나', unless: /AGENTS|3층|층/ },
      { word: '옵션' },
    ] },
  { canonical: '퇴고', why: '퇴고로 통일합니다. 교정은 다른 일입니다',
    variants: [
      // '교정하지 않는다' 는 이 제품이 하지 않는 일을 밝히는 문장이라 옳다
      { word: '교정', unless: /교정\s*(하지|되지|을 하지)?\s*않/ },
      { word: '첨삭' },
    ] },
  { canonical: '도우미', why: '도우미로 통일합니다',
    variants: [{ word: '어시스턴트' }, { word: '헬퍼' }] },
];

/** 쓰지 않기로 한 말 */
const BANNED = [
  { word: 'AI가 고쳐', why: '이 서비스는 대신 고치지 않습니다. 핵심 약속과 어긋납니다' },
  { word: '자동으로 수정', why: '사용자가 고르는 구조입니다' },
  { word: '완벽', why: '과장 표현입니다' },
  { word: '최고의', why: '과장 표현입니다' },
];

export function inspect(text, where) {
  const found = [];
  const push = (severity, rule, snippet, suggest, why) =>
    found.push({ where, severity, rule, snippet, suggest, why });

  for (const [wrong, right] of SPELLING) {
    let at = text.indexOf(wrong);
    while (at !== -1) {
      push('error', 'spelling', context(text, at, wrong.length), right, `'${wrong}' → '${right}'`);
      at = text.indexOf(wrong, at + 1);
    }
  }

  const taken = [];   // 이미 지적한 구간
  const overlaps = (a, b) => taken.some(([x, y]) => a < y && b > x);
  for (const [re, right] of SPACING) {
    for (const m of text.matchAll(re)) {
      const from = m.index;
      const to = from + m[0].length;
      if (overlaps(from, to)) continue;
      taken.push([from, to]);
      if (right === null) continue;   // 맞는 형태를 미리 잡아 둔 규칙
      push('error', 'spacing', context(text, from, m[0].length), right, '띄어쓰기');
    }
  }

  for (const term of TERMS) {
    for (const v of term.variants) {
      if (v.unless && v.unless.test(text)) continue;
      let at = text.indexOf(v.word);
      while (at !== -1) {
        push('warn', 'term', context(text, at, v.word.length), term.canonical, term.why);
        at = text.indexOf(v.word, at + 1);
      }
    }
  }

  for (const b of BANNED) {
    let at = text.indexOf(b.word);
    while (at !== -1) {
      push('warn', 'banned', context(text, at, b.word.length), '(삭제)', b.why);
      at = text.indexOf(b.word, at + 1);
    }
  }

  // 같은 문장에서 마침표가 두 번 이상 연달아 찍힌 경우
  for (const m of text.matchAll(/[.]{2,}(?!\.)/g)) {
    if (m[0] !== '...') push('warn', 'punct', context(text, m.index, m[0].length), '…', '줄임표');
  }

  return found;
}

function context(text, at, len) {
  const from = Math.max(0, at - 12);
  const to = Math.min(text.length, at + len + 12);
  return (from ? '…' : '') + text.slice(from, to).replace(/\s+/g, ' ') + (to < text.length ? '…' : '');
}

/** 화면에서 사람이 읽는 문자열만 긁어 온다. */
export const COLLECT_SNIPPET = `
(() => {
  const out = [];
  const seen = new Set();
  document.querySelectorAll('[data-section]').forEach(sec => {
    const was = sec.hidden;
    sec.hidden = false;
    sec.querySelectorAll('h1,h2,h3,h4,p,li,label,legend,button,option,th,td,span.hint,.blank-title,.blank-body')
      .forEach(el => {
        const t = (el.textContent || '').replace(/\\s+/g, ' ').trim();
        if (t.length > 1 && !seen.has(t)) { seen.add(t); out.push({ where: sec.dataset.section, text: t }); }
      });
    ['placeholder', 'title', 'aria-label'].forEach(attr => {
      sec.querySelectorAll('[' + attr + ']').forEach(el => {
        const t = (el.getAttribute(attr) || '').replace(/\\s+/g, ' ').trim();
        if (t.length > 1 && !seen.has(t)) { seen.add(t); out.push({ where: sec.dataset.section + ':' + attr, text: t }); }
      });
    });
    sec.hidden = was;
  });
  return out;
})()`;
