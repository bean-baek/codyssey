/**
 * js/ui/compare.js — 원본 / 수정본 분할 비교
 *
 * 왼쪽은 퇴고를 요청한 시점의 원고(기준본), 오른쪽은 제안을 반영해 가는 현재 원고다.
 * 문장 번호를 붙여 나란히 세우고, 달라진 문장만 강조한다.
 *
 * 줄 단위가 아니라 문장 단위로 맞추는 이유는 이 도구가 문장 단위로만
 * 제안하기 때문이다. 한 문장이 한 행이면 좌우가 항상 같은 수로 떨어진다.
 */

import { splitSentences } from '../core/sentences.js';

let body;
let pane;
let left;
let right;
let toggleBtn;
let modeLabel;

/** 퇴고를 요청한 시점의 원고. 이것이 비교의 기준이다. */
let baseline = '';

export function setBaseline(text) {
  baseline = text;
}

export function hasBaseline() {
  return baseline.trim().length > 0;
}

export function baselineText() {
  return baseline;
}

export function isOpen() {
  return body?.dataset.view === 'diff';
}

function rowsFor(text) {
  return splitSentences(text).map((s) => s.text);
}

function render(current) {
  const a = rowsFor(baseline);
  const b = rowsFor(current);
  const n = Math.max(a.length, b.length);

  left.innerHTML = '';
  right.innerHTML = '';

  if (!n) {
    left.innerHTML = '<p class="diff-empty">아직 퇴고를 요청하지 않았습니다.</p>';
    right.innerHTML = '<p class="diff-empty">제안을 반영하면 여기에 나타납니다.</p>';
    return;
  }

  for (let i = 0; i < n; i += 1) {
    const before = a[i];
    const after = b[i];
    const changed = before !== after;

    left.append(row(i + 1, before, changed ? 'is-removed' : ''));
    right.append(row(i + 1, after, changed ? 'is-added' : ''));
  }
}

function row(number, text, extra) {
  const el = document.createElement('div');
  el.className = `diff-row ${extra}`.trim();

  const num = document.createElement('span');
  num.className = 'diff-num';
  num.textContent = String(number);

  const body_ = document.createElement('span');
  body_.className = 'diff-text';
  body_.textContent = text ?? '';
  if (text === undefined) el.classList.add('is-void');

  el.append(num, body_);
  return el;
}

export function refresh(currentText) {
  if (isOpen()) render(currentText);
}

export function setView(view, currentText) {
  body.dataset.view = view;
  pane.hidden = view !== 'diff';
  document.querySelector('.editpane').hidden = view === 'diff';

  toggleBtn.setAttribute('aria-pressed', String(view === 'diff'));
  modeLabel.textContent = view === 'diff' ? '비교' : '편집';

  if (view === 'diff') render(currentText);
}

export function toggle(currentText) {
  setView(isOpen() ? 'edit' : 'diff', currentText);
}

export function initCompare(getText) {
  body = document.getElementById('ide-body');
  pane = document.getElementById('diffpane');
  left = document.getElementById('diff-left');
  right = document.getElementById('diff-right');
  toggleBtn = document.getElementById('toggle-compare');
  modeLabel = document.getElementById('st-mode');

  toggleBtn.addEventListener('click', () => toggle(getText()));

  // 좌우 스크롤을 묶는다. 따로 놀면 비교가 안 된다.
  let syncing = false;
  const link = (from, to) => {
    from.addEventListener('scroll', () => {
      if (syncing) return;
      syncing = true;
      to.scrollTop = from.scrollTop;
      requestAnimationFrame(() => {
        syncing = false;
      });
    });
  };
  link(left, right);
  link(right, left);
}
