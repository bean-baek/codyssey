/**
 * js/ui/editor.js — 퇴고 섹션
 *
 * 흐름: 원고 → splitSentences → revise() → 제안 카드 → 수락 시 원문 치환
 *
 * 실패는 전부 ai.js 가 AIError 로 정규화해 던지므로 여기서는
 * err.message 를 그대로 띄우기만 한다. 어떤 경우에도 원고는 지우지 않는다.
 */

import { revise, AIError } from '../core/ai.js';
import { splitSentences, applySuggestions } from '../core/sentences.js';

const MAX_TEXT = 5000;
const MIN_TEXT = 30;

const SAMPLE = `그날 저녁에 나는 그 골목을 다시 걸었다. 그리고 그 집 앞에서 한참을 서 있었다. 그리고 아무도 나오지 않았다.
불이 꺼진 창문은 그냥 어두웠고 그 어둠은 뭔가 이상하게 느껴지는 그런 어둠이었다. 나는 사실 그것이 무엇을 의미하는지 잘 알고 있었던 것 같다.
바람이 불었다. 추웠다. 나는 돌아섰다.
아주 오래전에 어머니가 나에게 해 주었던 말이 그때 문득 떠올랐는데 그 말은 사람은 결국 자기가 떠나온 자리로 돌아오게 되어 있다는 것이었다.`;

export function initEditor(getPersona) {
  const input = document.getElementById('manuscript');
  const counter = document.getElementById('counter');
  const runBtn = document.getElementById('revise-run');
  const sampleBtn = document.getElementById('revise-sample');
  const notice = document.getElementById('revise-notice');
  const results = document.getElementById('revise-results');

  /** 마지막 요청 시점의 문장 분해 결과. 제안의 index가 이걸 가리킨다. */
  let sentences = [];

  function updateCounter() {
    const n = input.value.length;
    counter.textContent = `${n.toLocaleString()}자`;
    counter.classList.toggle('over', n > MAX_TEXT);
  }

  function showNotice(message) {
    notice.textContent = message;
    notice.hidden = false;
  }

  function clearNotice() {
    notice.hidden = true;
    notice.textContent = '';
  }

  function setBusy(busy) {
    runBtn.disabled = busy;
    runBtn.textContent = busy ? '퇴고 중…' : '퇴고 요청';
  }

  async function run() {
    clearNotice();

    const text = input.value.trim();
    sentences = splitSentences(text);

    setBusy(true);
    try {
      const { suggestions } = await revise({
        text,
        sentences: sentences.map((s) => s.text),
        persona: getPersona(),
      });
      render(suggestions);
    } catch (err) {
      if (err instanceof AIError) showNotice(err.message);
      else showNotice('알 수 없는 오류가 발생했습니다. 다시 시도해 주세요.');
      // 원고와 기존 결과는 건드리지 않는다
    } finally {
      setBusy(false);
    }
  }

  function render(suggestions) {
    results.innerHTML = '';

    if (!suggestions.length) {
      results.innerHTML =
        '<p class="empty">고칠 지점을 찾지 못했습니다. 억지로 채우지 않는 것이 규칙입니다.</p>';
      return;
    }

    const head = document.createElement('div');
    head.className = 'results-head';
    head.innerHTML = `<h3>제안 ${suggestions.length}개</h3><span>납득되는 것만 반영하세요</span>`;
    results.append(head);

    suggestions.forEach((s) => results.append(card(s)));
  }

  function card(s) {
    const el = document.createElement('article');
    el.className = 'card';

    const top = document.createElement('div');
    top.className = 'card-top';
    top.innerHTML =
      `<span class="badge">${escape(s.type)}</span>` +
      `<span class="card-n">${s.index + 1}번째 문장</span>`;

    const before = document.createElement('p');
    before.className = 'line before';
    before.textContent = s.original;

    const after = document.createElement('p');
    after.className = 'line after';
    after.textContent = s.revised;

    const reason = document.createElement('p');
    reason.className = 'reason';
    reason.textContent = s.reason;

    const actions = document.createElement('div');
    actions.className = 'card-actions';

    const accept = document.createElement('button');
    accept.className = 'btn btn-primary';
    accept.type = 'button';
    accept.textContent = '이 제안 반영';

    const skip = document.createElement('button');
    skip.className = 'btn btn-quiet';
    skip.type = 'button';
    skip.textContent = '건너뛰기';

    accept.addEventListener('click', () => {
      // 반영 시점의 원고를 기준으로 다시 분해해야 offset이 맞는다.
      // 앞선 제안을 이미 반영했다면 뒤쪽 위치가 밀려 있기 때문이다.
      const current = splitSentences(input.value);
      const target = current[s.index];

      if (!target || target.text !== s.original) {
        markDone(el, actions, '원고가 바뀌어 반영할 수 없습니다. 다시 요청해 주세요.', false);
        return;
      }

      input.value = applySuggestions(input.value, current, [
        { index: s.index, revised: s.revised },
      ]);
      updateCounter();
      markDone(el, actions, '반영했습니다', true);
    });

    skip.addEventListener('click', () => markDone(el, actions, '건너뛰었습니다', false));

    actions.append(accept, skip);
    el.append(top, before, after, reason, actions);
    return el;
  }

  function markDone(el, actions, message, ok) {
    el.classList.add('done');
    actions.innerHTML = '';
    const span = document.createElement('span');
    span.className = ok ? 'applied' : 'muted';
    span.textContent = message;
    actions.append(span);
  }

  function escape(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
    );
  }

  input.addEventListener('input', updateCounter);
  runBtn.addEventListener('click', run);

  sampleBtn.addEventListener('click', () => {
    input.value = SAMPLE;
    updateCounter();
    input.focus();
  });

  // ⌘Enter / Ctrl+Enter
  input.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      run();
    }
  });

  updateCounter();
  return { MIN_TEXT, MAX_TEXT };
}
