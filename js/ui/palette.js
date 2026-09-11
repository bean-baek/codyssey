/**
 * js/ui/palette.js — 명령 팔레트
 *
 * AGENTS.md 1장 '호출 트리거' 행의 `>퇴고 요청`, `⌘K` 가 여기다.
 * 손을 키보드에서 떼지 않고 모든 기능에 닿는 것이 목적이므로,
 * 화면에 버튼이 있는 기능도 전부 명령으로 한 번 더 등록한다.
 *
 * 명령은 바깥에서 register() 로 넣는다. 팔레트는 무엇을 하는지 모른다.
 */

const commands = [];

let box;
let input;
let list;
let prefix;
let items = [];       // 현재 걸러진 명령
let active = 0;
let filtering = false;  // 검색어를 쳤는가 — 번호 표시 여부를 가른다

/**
 * @param {{id:string, title:string, hint?:string, keys?:string[],
 *          group?:string, when?:() => boolean, run:() => void}} cmd
 */
export function register(cmd) {
  commands.push(cmd);
}

export function isOpen() {
  return box && !box.hidden;
}

export function open(initial = '') {
  box.hidden = false;
  input.value = initial;
  refresh();
  input.focus();
  input.select();
}

export function close() {
  box.hidden = true;
  input.value = '';
}

/** 아주 단순한 부분일치 점수. 앞에서 맞을수록, 연속으로 맞을수록 높다. */
function score(text, query) {
  if (!query) return 1;
  const t = text.toLowerCase();
  const q = query.toLowerCase();

  const direct = t.indexOf(q);
  if (direct !== -1) return 1000 - direct;

  // 띄엄띄엄 매칭 (VSCode 식 fuzzy)
  let i = 0;
  let hits = 0;
  let streak = 0;
  let best = 0;
  for (const ch of t) {
    if (i < q.length && ch === q[i]) {
      i += 1;
      hits += 1;
      streak += 1;
      best = Math.max(best, streak);
    } else {
      streak = 0;
    }
  }
  return i === q.length ? hits * 10 + best : -1;
}

function refresh() {
  // '>' 는 명령 접두다. 있어도 없어도 같게 동작하지만 타이핑 습관을 받아 준다.
  const raw = input.value;
  const query = raw.startsWith('>') ? raw.slice(1).trim() : raw.trim();
  prefix.textContent = '>';
  filtering = query.length > 0;

  items = commands
    .filter((c) => (c.when ? c.when() : true))
    .map((c) => ({ cmd: c, s: score(`${c.title} ${c.hint || ''}`, query) }))
    .filter((x) => x.s >= 0)
    .sort((a, b) => b.s - a.s)
    .map((x) => x.cmd);

  active = 0;
  paint();
}

function paint() {
  list.innerHTML = '';

  if (!items.length) {
    const li = document.createElement('li');
    li.className = 'palette-empty';
    li.textContent = '일치하는 명령이 없습니다.';
    list.append(li);
    return;
  }

  items.forEach((cmd, i) => {
    const li = document.createElement('li');
    li.className = 'palette-item' + (i === active ? ' is-active' : '');
    li.setAttribute('role', 'option');
    li.setAttribute('aria-selected', String(i === active));

    const main = document.createElement('div');
    main.className = 'palette-main';
    const title = document.createElement('span');
    title.className = 'palette-title';
    title.textContent = cmd.title;
    main.append(title);
    if (cmd.hint) {
      const hint = document.createElement('span');
      hint.className = 'palette-hint';
      hint.textContent = cmd.hint;
      main.append(hint);
    }

    li.append(main);

    // 검색어를 치기 전에는 번호를 보여 준다. ⌘K 다음 숫자 한 자리로 끝난다.
    // 조합키를 여러 개 외우게 하는 것보다 이쪽이 훨씬 쉽다.
    const keys = document.createElement('span');
    keys.className = 'palette-keys';
    if (!filtering && i < 9) {
      const kbd = document.createElement('kbd');
      kbd.className = 'is-num';
      kbd.textContent = String(i + 1);
      keys.append(kbd);
    } else if (cmd.keys?.length) {
      cmd.keys.forEach((k) => {
        const kbd = document.createElement('kbd');
        kbd.textContent = k;
        keys.append(kbd);
      });
    }
    li.append(keys);

    li.addEventListener('mouseenter', () => {
      active = i;
      paint();
    });
    li.addEventListener('click', () => execute(i));
    list.append(li);
  });

  list.children[active]?.scrollIntoView({ block: 'nearest' });
}

function execute(index) {
  const cmd = items[index];
  if (!cmd) return;
  close();
  // 팔레트가 닫힌 뒤에 실행해야 포커스 이동이 자연스럽다
  requestAnimationFrame(() => cmd.run());
}

export function initPalette() {
  box = document.getElementById('palette');
  input = document.getElementById('palette-input');
  list = document.getElementById('palette-list');
  prefix = document.getElementById('palette-prefix');

  input.addEventListener('input', refresh);

  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      active = Math.min(active + 1, items.length - 1);
      paint();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      active = Math.max(active - 1, 0);
      paint();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      execute(active);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      close();
    } else if (!filtering && /^[1-9]$/.test(e.key)) {
      // 검색어가 없을 때만 숫자를 선택으로 받는다.
      // 검색 중에 숫자를 막으면 '제안 3개' 같은 걸 못 찾는다.
      e.preventDefault();
      execute(Number(e.key) - 1);
    }
  });

  // 바깥을 누르면 닫는다
  box.addEventListener('mousedown', (e) => {
    if (e.target === box) close();
  });

  document.getElementById('st-palette')?.addEventListener('click', () => open());
}
