/**
 * js/app.js — 부트스트랩과 키 바인딩
 *
 * 화면에 버튼이 있는 기능도 전부 명령으로 한 번 더 등록한다.
 * AGENTS.md 1장의 호출 트리거(`⌘Enter`, `>퇴고 요청`, `⌘K`)를 그대로 따른 것이고,
 * 손을 키보드에서 떼지 않고 쓰는 것이 이 도구의 사용 방식이다.
 */

import { initNav, go } from './core/nav.js';
import { initPersona } from './ui/persona.js';
import { initEditor } from './ui/editor.js';
import { initAssist, askAssist } from './ui/assist.js';
import { initCompare, toggle as toggleCompare } from './ui/compare.js';
import { initPalette, register, open as openPalette, isOpen as paletteOpen, close as closePalette } from './ui/palette.js';

const persona = initPersona();
const editor = initEditor(() => persona.read());
initCompare(() => editor.getText());
initAssist();
initPalette();
initNav();

/* ─────────────────────────────────────────── 명령 등록 */

const inRevise = () => location.hash === '#revise' || location.hash === '';

register({
  id: 'revise.run',
  title: '퇴고 요청',
  hint: '원고 전체를 문장 단위로 검토합니다',
  keys: ['⌘', '↵'],
  when: inRevise,
  run: () => editor.run(),
});

register({
  id: 'revise.compare',
  title: '비교 보기 전환',
  hint: '원본과 수정본을 나란히 봅니다',
  when: inRevise,
  run: () => toggleCompare(editor.getText()),
});

register({
  id: 'revise.applyAll',
  title: '남은 제안 모두 반영',
  when: () => inRevise() && editor.pendingCount() > 0,
  run: () => editor.applyRemaining(),
});

register({
  id: 'revise.reset',
  title: '원본으로 되돌리기',
  hint: '퇴고 요청 시점의 원고로 복구합니다',
  when: inRevise,
  run: () => editor.resetToBaseline(),
});

register({
  id: 'revise.persona',
  title: '편집 방침 열고 닫기',
  when: inRevise,
  run: () => persona.toggleDrawer(),
});

register({
  id: 'revise.sample',
  title: '예시 원고 넣기',
  when: inRevise,
  run: () => editor.insertSample(),
});

/* 선택한 텍스트를 도우미로 — AGENTS.md 의 '텍스트 선택' 트리거 */

register({
  id: 'assist.synonym',
  title: '유의어 찾기 (선택한 단어)',
  hint: '원고에서 단어를 선택한 뒤 실행하세요',
  run: () => {
    const word = editor.selection();
    if (!word) {
      go('assist');
      askAssist('synonym', '', '');
      return;
    }
    go('assist');
    askAssist('synonym', word, editor.sentenceAtCursor());
  },
});

register({
  id: 'assist.impression',
  title: '이 문장의 인상 보기',
  hint: '커서가 놓인 문장을 그대로 보냅니다',
  run: () => {
    const sentence = editor.selection() || editor.sentenceAtCursor();
    go('assist');
    askAssist('impression', sentence, '');
  },
});

register({
  id: 'assist.recall',
  title: '그 단어 뭐였지 (설명으로 찾기)',
  run: () => {
    go('assist');
    askAssist('recall', editor.selection(), '');
  },
});

register({
  id: 'assist.classify',
  title: '원고 분류 태그 제안',
  run: () => {
    go('assist');
    askAssist('classify', editor.getText().slice(0, 400), '');
  },
});

/* 이동 */

[
  ['home', '홈'],
  ['revise', '퇴고'],
  ['assist', '도우미'],
  ['design', '설계'],
].forEach(([id, label]) =>
  register({
    id: `go.${id}`,
    title: `이동: ${label}`,
    group: '이동',
    run: () => go(id),
  })
);

/* ─────────────────────────────────────────── 전역 단축키

   외울 것은 두 개뿐이다.
     ⌘K  — 모든 기능
     ⌘↵  — 퇴고 요청 (가장 자주 쓰는 하나라서 따로 뒀다)

   나머지는 ⌘K 를 누른 뒤 번호 한 자리로 실행한다.
   ⌘\ 나 ⌘, 같은 조합은 아무도 외우지 못해 걷어냈다. */

const isMac = navigator.platform.toUpperCase().includes('MAC');
const mod = (e) => (isMac ? e.metaKey : e.ctrlKey);

addEventListener('keydown', (e) => {
  if (mod(e) && (e.key === 'k' || e.key === 'K')) {
    // 크롬은 ⌘K 를 주소창 검색에 쓴다. 막지 않으면 팔레트가 열리지 않는다.
    e.preventDefault();
    paletteOpen() ? closePalette() : openPalette();
    return;
  }

  if (paletteOpen()) return;   // 팔레트 안에서는 자체 키 처리를 쓴다

  if (mod(e) && e.key === 'Enter') {
    e.preventDefault();
    editor.run();
  }
});
