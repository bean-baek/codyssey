/**
 * js/ui/assist.js — 도우미 섹션
 *
 * 모드 4개가 입력의 성격만 다르고 흐름은 같다.
 * synonym 만 앞뒤 문맥을 함께 보낸다. 그것이 사전과 달라지는 유일한 지점이라
 * 입력란을 숨기지 않고 항상 보여 준다.
 */

import { assist, AIError } from '../core/ai.js';

const MODES = {
  synonym: {
    label: '바꿀 단어',
    desc: '사전적 동의어가 아니라, 그 자리에 실제로 들어갈 수 있는 말을 찾습니다. 앞뒤 문맥을 함께 넣을수록 정확해집니다.',
    placeholder: '예: 쓸쓸하다',
    context: true,
  },
  recall: {
    label: '찾는 단어에 대한 설명',
    desc: '단어가 떠오르지 않을 때 설명만으로 찾습니다. 무엇을 뜻하는지, 어떤 느낌인지 적어 주세요.',
    placeholder: '예: 비가 그친 뒤 풀잎에 남은 물방울을 가리키는 말',
    context: false,
  },
  impression: {
    label: '문장',
    desc: '이 문장이 독자에게 어떤 인상을 주는지 세 단어로 답합니다. 고치라고 하지 않고, 좋고 나쁨도 판단하지 않습니다.',
    placeholder: '예: 그는 문을 닫고 오래 서 있었다.',
    context: false,
  },
  classify: {
    label: '원고 앞부분',
    desc: '글의 앞부분을 읽고 분류 태그 세 개와 폴더 이름 하나를 제안합니다. 내용을 요약하지는 않습니다.',
    placeholder: '원고 앞 몇 문단을 붙여넣으세요.',
    context: false,
  },
};

export function initAssist() {
  const tabs = [...document.querySelectorAll('[role="tab"][data-mode]')];
  const desc = document.getElementById('assist-desc');
  const label = document.getElementById('assist-label');
  const query = document.getElementById('assist-query');
  const contextField = document.getElementById('assist-context-field');
  const context = document.getElementById('assist-context');
  const runBtn = document.getElementById('assist-run');
  const notice = document.getElementById('assist-notice');
  const results = document.getElementById('assist-results');

  let mode = 'synonym';

  function selectMode(next) {
    mode = next;
    const cfg = MODES[mode];

    tabs.forEach((t) => t.setAttribute('aria-selected', String(t.dataset.mode === mode)));
    desc.textContent = cfg.desc;
    label.textContent = cfg.label;
    query.placeholder = cfg.placeholder;
    query.rows = mode === 'classify' ? 6 : 2;
    contextField.hidden = !cfg.context;

    notice.hidden = true;
    results.innerHTML = '';
  }

  async function run() {
    notice.hidden = true;
    results.innerHTML = '';

    runBtn.disabled = true;
    runBtn.textContent = '찾는 중…';
    try {
      const { candidates } = await assist(mode, {
        query: query.value,
        context: MODES[mode].context ? context.value : '',
      });
      render(candidates);
    } catch (err) {
      notice.textContent =
        err instanceof AIError ? err.message : '불러오지 못했습니다. 다시 시도해 주세요.';
      notice.hidden = false;
    } finally {
      runBtn.disabled = false;
      runBtn.textContent = '찾기';
    }
  }

  function render(candidates) {
    if (!candidates?.length) {
      results.innerHTML = '<p class="empty">후보를 찾지 못했습니다.</p>';
      return;
    }

    candidates.forEach((text) => {
      const chip = document.createElement('button');
      chip.className = 'chip';
      chip.type = 'button';
      chip.textContent = text;
      chip.title = '클릭하면 복사됩니다';
      chip.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(text);
          chip.classList.add('copied');
          setTimeout(() => chip.classList.remove('copied'), 900);
        } catch {
          // 클립보드 권한이 없어도 후보는 읽을 수 있으니 조용히 넘어간다
        }
      });
      results.append(chip);
    });
  }

  tabs.forEach((t) => t.addEventListener('click', () => selectMode(t.dataset.mode)));
  runBtn.addEventListener('click', run);
  query.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      run();
    }
  });

  selectMode('synonym');
}
