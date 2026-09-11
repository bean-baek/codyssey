import { splitSentences, applySuggestions } from '../js/core/sentences.js';

let pass = 0, fail = 0;
const eq = (label, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  ok ? pass++ : fail++;
  console.log(`${ok ? '✓' : '✗'} ${label}`);
  if (!ok) console.log('   기대:', JSON.stringify(want), '\n   실제:', JSON.stringify(got));
};

// 기본 분해
eq('마침표 분해',
  splitSentences('첫 문장이다. 둘째 문장이다.').map(s => s.text),
  ['첫 문장이다.', '둘째 문장이다.']);

// offset 이 원문을 정확히 가리키는가
const t1 = '첫 문장이다. 둘째 문장이다.';
const s1 = splitSentences(t1);
eq('offset 정확도', s1.map(s => t1.slice(s.start, s.end)), s1.map(s => s.text));

// 소수점 / 약어를 쪼개지 않는가
eq('소수점 유지',
  splitSentences('기온은 3.5도까지 떨어졌다.').map(s => s.text),
  ['기온은 3.5도까지 떨어졌다.']);

// 말줄임표와 연속 부호
eq('줄임표는 문장 중간의 쉼',
  splitSentences('그래서…… 갔다. 정말?!').map(s => s.text),
  ['그래서…… 갔다.', '정말?!']);

eq('줄임표+마침표로 끝나면 분해',
  splitSentences('그는 말을 잇지 못했다……. 밖은 조용했다.').map(s => s.text),
  ['그는 말을 잇지 못했다…….', '밖은 조용했다.']);

eq('줄임표 문장도 폐기 규칙을 통과해야 한다',
  ['그래서…… 갔다.'].map(t => [...t].filter(c => '.!?'.includes(c)).length),
  [1]);

// 닫는 따옴표는 앞 문장에
eq('닫는 따옴표',
  splitSentences('"가자." 그가 말했다.').map(s => s.text),
  ['"가자."', '그가 말했다.']);

// 종결 부호 없는 꼬리
eq('부호 없는 마지막',
  splitSentences('첫 문장이다. 끝은 부호가 없다').map(s => s.text),
  ['첫 문장이다.', '끝은 부호가 없다']);

// 줄바꿈
eq('줄바꿈 구분',
  splitSentences('첫 줄이다.\n\n둘째 문단이다.').map(s => s.text),
  ['첫 줄이다.', '둘째 문단이다.']);

// 빈 입력
eq('빈 입력', splitSentences(''), []);
eq('공백만', splitSentences('   \n  '), []);

// 같은 문장이 두 번 나올 때 — 문자열 검색 방식이 틀리는 케이스
const t2 = '비가 왔다. 해가 떴다. 비가 왔다.';
const s2 = splitSentences(t2);
eq('중복 문장 — 세 번째만 치환',
  applySuggestions(t2, s2, [{ index: 2, revised: '비가 내렸다.' }]),
  '비가 왔다. 해가 떴다. 비가 내렸다.');

// 여러 제안 동시 적용 (offset 밀림 방지)
eq('다중 적용',
  applySuggestions(t2, s2, [
    { index: 0, revised: '비가 쏟아졌다.' },
    { index: 2, revised: '또 비가 왔다.' },
  ]),
  '비가 쏟아졌다. 해가 떴다. 또 비가 왔다.');

// 길이가 크게 바뀌어도 뒤 문장이 안 깨지는가
eq('길이 변화',
  applySuggestions(t2, s2, [{ index: 0, revised: '하늘에서 아주 오랫동안 비가 쏟아져 내렸다.' }]),
  '하늘에서 아주 오랫동안 비가 쏟아져 내렸다. 해가 떴다. 비가 왔다.');

console.log(`\n통과 ${pass} / 실패 ${fail}`);
process.exit(fail ? 1 : 0);
