/**
 * js/ui/editor.js — 퇴고 화면
 *
 * 흐름: 원고 → splitSentences → revise() → 제안 카드 → 수락 시 원문 치환
 *
 * 실패는 전부 ai.js 가 AIError 로 정규화해 던지므로 여기서는
 * err.message 를 그대로 띄우기만 한다. 어떤 경우에도 원고는 지우지 않는다.
 */

import { revise, AIError } from '../core/ai.js';
import { splitSentences, applySuggestions } from '../core/sentences.js';
import * as compare from './compare.js';

const MAX_TEXT = 5000;
const MIN_TEXT = 30;

const SAMPLE = `그날 저녁에 나는 그 골목을 다시 걸었다. 그리고 그 집 앞에서 한참을 서 있었다. 그리고 아무도 나오지 않았다.
불이 꺼진 창문은 그냥 어두웠고 그 어둠은 뭔가 이상하게 느껴지는 그런 어둠이었다. 나는 사실 그것이 무엇을 의미하는지 잘 알고 있었던 것 같다.
바람이 불었다. 추웠다. 나는 돌아섰다.
아주 오래전에 어머니가 나에게 해 주었던 말이 그때 문득 떠올랐는데 그 말은 사람은 결국 자기가 떠나온 자리로 돌아오게 되어 있다는 것이었다.`;

export function initEditor(getPersona) {
  const input = document.getElementById('manuscript');
  const runBtn = document.getElementById('revise-run');
  const notice = document.getElementById('revise-notice');
  const results = document.getElementById('revise-results');
  const count = document.getElementById('suggest-count');
  const applyAll = document.getElementById('apply-all');
  const dirty = document.getElementById('tab-dirty');
  const stChars = document.getElementById('st-chars');
  const stSentences = document.getElementById('st-sentences');

  /** 마지막 요청 시점의 문장 분해 결과. 제안의 index 가 이걸 가리킨다. */
  let sentences = [];
  /** 아직 반영하지 않은 제안 */
  let pending = [];

  function stats() {
    const n = input.value.length;
    stChars.textContent = `${n.toLocaleString()} / ${MAX_TEXT.toLocaleString()}`;
    stChars.classList.toggle('is-over', n > MAX_TEXT);
    stSentences.textContent = `문장 ${splitSentences(input.value).length}`;
    dirty.hidden = !compare.hasBaseline() || input.value === undefined;
    compare.refresh(input.value);
  }

  const showNotice = (message) => {
    notice.textContent = message;
    notice.hidden = false;
  };
  const clearNotice = () => {
    notice.hidden = true;
    notice.textContent = '';
  };

  function setBusy(busy) {
    runBtn.disabled = busy;
    if (busy) runBtn.textContent = '읽는 중…';
    else runBtn.innerHTML = '퇴고 <kbd>⌘</kbd><kbd>↵</kbd>';
  }

  async function run() {
    clearNotice();

    const text = input.value.trim();
    sentences = splitSentences(text);

    const previous = results.innerHTML;
    results.innerHTML =
      '<p class="empty">문장을 하나씩 읽고 있습니다.<br>길이에 따라 10초 안팎 걸립니다.</p>';

    setBusy(true);
    try {
      const { suggestions } = await revise({
        text,
        sentences: sentences.map((s) => s.text),
        persona: getPersona(),
      });
      // 이 시점의 원고가 비교의 기준이 된다
      compare.setBaseline(input.value);
      render(suggestions);
      stats();
    } catch (err) {
      results.innerHTML = previous;
      showNotice(
        err instanceof AIError ? err.message : '알 수 없는 오류가 발생했습니다. 다시 시도해 주세요.'
      );
    } finally {
      setBusy(false);
    }
  }

  function render(suggestions) {
    pending = [...suggestions];
    results.innerHTML = '';
    count.textContent = String(suggestions.length);
    applyAll.hidden = suggestions.length === 0;

    if (!suggestions.length) {
      results.innerHTML =
        '<p class="empty">고칠 지점을 찾지 못했습니다. 억지로 채우지 않는 것이 규칙입니다.</p>';
      return;
    }
    suggestions.forEach((s) => results.append(card(s)));
  }

  function card(s) {
    const el = document.createElement('article');
    el.className = 'card';

    const top = document.createElement('div');
    top.className = 'card-top';
    const badge = document.createElement('span');
    badge.className = 'badge';
    badge.textContent = s.type;
    const num = document.createElement('span');
    num.className = 'card-n';
    num.textContent = `${s.index + 1}번째 문장`;
    top.append(badge, num);

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
    accept.className = 'btn btn-primary btn-sm';
    accept.type = 'button';
    accept.textContent = '반영';

    const skip = document.createElement('button');
    skip.className = 'btn btn-quiet btn-sm';
    skip.type = 'button';
    skip.textContent = '건너뛰기';

    accept.addEventListener('click', () => {
      const ok = applyOne(s);
      markDone(el, actions, ok ? '반영했습니다' : '원고가 바뀌어 반영할 수 없습니다', ok);
    });
    skip.addEventListener('click', () => {
      pending = pending.filter((x) => x !== s);
      markDone(el, actions, '건너뛰었습니다', false);
    });

    actions.append(accept, skip);
    el.append(top, before, after, reason, actions);
    return el;
  }

  /** 반영 시점에 다시 분해해야 offset 이 맞는다. 앞 제안을 이미 반영했으면 뒤가 밀려 있다. */
  function applyOne(s) {
    const current = splitSentences(input.value);
    const target = current[s.index];
    if (!target || target.text !== s.original) return false;

    input.value = applySuggestions(input.value, current, [
      { index: s.index, revised: s.revised },
    ]);
    pending = pending.filter((x) => x !== s);
    stats();
    return true;
  }

  function markDone(el, actions, message, ok) {
    el.classList.add('done');
    actions.innerHTML = '';
    const span = document.createElement('span');
    span.className = ok ? 'applied' : 'muted';
    span.textContent = message;
    actions.append(span);
  }

  function applyRemaining() {
    if (!pending.length) return 0;
    // 뒤 인덱스부터 적용해야 offset 이 밀리지 않는다
    const current = splitSentences(input.value);
    const valid = pending.filter(
      (s) => current[s.index] && current[s.index].text === s.original
    );
    input.value = applySuggestions(input.value, current, valid);
    pending = [];
    stats();

    [...results.querySelectorAll('.card:not(.done)')].forEach((el) => {
      const actions = el.querySelector('.card-actions');
      if (actions) markDone(el, actions, '반영했습니다', true);
    });
    return valid.length;
  }

  function insertSample() {
    input.value = SAMPLE;
    stats();
    input.focus();
  }

  function resetToBaseline() {
    if (!compare.hasBaseline()) return false;
    input.value = compare.baselineText();
    stats();
    return true;
  }

  input.addEventListener('input', stats);
  runBtn.addEventListener('click', run);
  applyAll.addEventListener('click', applyRemaining);

  stats();

  return {
    run,
    insertSample,
    applyRemaining,
    resetToBaseline,
    getText: () => input.value,
    focus: () => input.focus(),
    selection: () => {
      const el = document.getElementById('manuscript');
      return el.value.slice(el.selectionStart, el.selectionEnd).trim();
    },
    sentenceAtCursor: () => {
      const el = document.getElementById('manuscript');
      const at = el.selectionStart;
      const found = splitSentences(el.value).find((s) => at >= s.start && at <= s.end);
      return found ? found.text : '';
    },
    pendingCount: () => pending.length,
  };
}
