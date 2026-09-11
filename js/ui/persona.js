/**
 * js/ui/persona.js — 편집 방침 패널
 *
 * 화면의 입력값을 api/revise.py 의 normalize_persona 가 받는 6개 필드와
 * 1:1로 맞춘다. 서버는 어떤 값이 와도 화이트리스트로 걸러 내지만,
 * 애초에 맞는 모양으로 보내야 사용자가 고른 것이 그대로 반영된다.
 */

import { loadPersona, savePersona, clearPersona, DEFAULT_PERSONA } from '../core/store.js';

const NOTE_MAX = 200;

export function initPersona() {
  const tone = document.getElementById('p-tone');
  const max = document.getElementById('p-max');
  const maxOut = document.getElementById('p-max-out');
  const length = document.getElementById('p-length');
  const note = document.getElementById('p-note');
  const noteCount = document.getElementById('p-note-count');
  const focusBox = document.getElementById('p-focus');
  const protectBox = document.getElementById('p-protect');
  const reset = document.getElementById('p-reset');

  const boxes = (root) => [...root.querySelectorAll('input[type=checkbox]')];

  function read() {
    return {
      tone: tone.value,
      maxSuggestions: Number(max.value),
      focusTypes: boxes(focusBox).filter((b) => b.checked).map((b) => b.value),
      lengthPreference: length.value,
      protect: boxes(protectBox).filter((b) => b.checked).map((b) => b.value),
      note: note.value.trim().slice(0, NOTE_MAX),
    };
  }

  function write(p) {
    tone.value = p.tone;
    max.value = String(p.maxSuggestions);
    length.value = p.lengthPreference;
    note.value = p.note;
    boxes(focusBox).forEach((b) => { b.checked = p.focusTypes.includes(b.value); });
    boxes(protectBox).forEach((b) => { b.checked = p.protect.includes(b.value); });
    paint();
  }

  function paint() {
    maxOut.textContent = max.value;
    noteCount.textContent = `${note.value.length}/${NOTE_MAX}`;
  }

  function persist() {
    paint();
    savePersona(read());
  }

  [tone, max, length, note].forEach((el) => {
    el.addEventListener('input', persist);
    el.addEventListener('change', persist);
  });
  [...boxes(focusBox), ...boxes(protectBox)].forEach((b) =>
    b.addEventListener('change', persist)
  );

  reset.addEventListener('click', () => {
    clearPersona();
    write({ ...DEFAULT_PERSONA });
  });

  // 방침 서랍 — 기본은 접어 둔다. 원고가 화면의 주인이어야 한다.
  const toggle = document.getElementById('persona-toggle');
  const drawer = document.getElementById('persona-drawer');
  function toggleDrawer() {
    const open = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', String(!open));
    drawer.hidden = open;
  }
  toggle.addEventListener('click', toggleDrawer);

  write(loadPersona());

  return { read, toggleDrawer };
}
