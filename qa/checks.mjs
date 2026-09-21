/**
 * qa/checks.mjs — 검사 목록
 *
 * 검사 하나는 { id, area, title, run(ctx) } 이고 run 은
 * { pass, detail, evidence? } 를 돌려준다. 던지면 오류로 집계된다.
 *
 * 통과/실패만 남기지 않고 detail 에 관찰값을 적는다.
 * 회차 비교에서 '언제부터 느려졌나' 같은 걸 보려면 수치가 있어야 한다.
 */

import { MOD, sleep } from './harness.mjs';

const BASE = 'http://localhost:8899';

const SAMPLE =
  '그날 저녁에 나는 그 골목을 다시 걸었다. 그리고 그 집 앞에서 한참을 서 있었다. ' +
  '그리고 아무도 나오지 않았다. 불이 꺼진 창문은 그냥 어두웠고 그 어둠은 뭔가 ' +
  '이상하게 느껴지는 그런 어둠이었다.';

const setText = (value) =>
  `(()=>{const el=document.getElementById('manuscript');` +
  `el.value=${JSON.stringify(value)};el.dispatchEvent(new Event('input'));return el.value.length})()`;

/** 퇴고 요청이 끝날 때까지 기다린다. 최대 wait 초. */
async function waitIdle(ctx, seconds = 30) {
  for (let i = 0; i < seconds * 2; i += 1) {
    await sleep(500);
    if (!(await ctx.js(`document.getElementById('revise-run').disabled`))) return true;
  }
  return false;
}

/* ───────────────────────────────────────────── 기능 */

export const checks = [
  {
    id: 'nav.sections',
    area: '기능',
    title: '네 개 섹션이 모두 열린다',
    async run(ctx) {
      const missing = [];
      for (const id of ['home', 'revise', 'assist', 'design']) {
        await ctx.js(`location.hash='#${id}'`);
        await sleep(350);
        const shown = await ctx.js(
          `!document.querySelector('[data-section="${id}"]').hidden`
        );
        const marked = await ctx.js(
          `document.querySelector('[data-nav="${id}"]').getAttribute('aria-current')==='page'`
        );
        if (!shown || !marked) missing.push(id);
      }
      return { pass: missing.length === 0, detail: missing.length ? `실패: ${missing}` : '4/4' };
    },
  },

  {
    id: 'palette.open',
    area: '기능',
    title: '⌘K 로 명령 팔레트가 열린다',
    async run(ctx) {
      await ctx.js(`location.hash='#revise'`);
      await sleep(300);
      await ctx.key('k', MOD.meta);
      await sleep(400);
      const open = await ctx.js(`!document.getElementById('palette').hidden`);
      const value = await ctx.js(`document.getElementById('palette-input').value`);
      const count = await ctx.js(`document.querySelectorAll('.palette-item').length`);
      await ctx.key('Escape');
      await sleep(200);
      return {
        pass: open && value === '' && count > 0,
        detail: `열림=${open} 입력값=${JSON.stringify(value)} 명령=${count}개`,
        evidence: { commandCount: count },
      };
    },
  },

  {
    id: 'palette.number',
    area: '기능',
    title: '팔레트에서 번호 키로 바로 실행된다',
    async run(ctx) {
      await ctx.js(`location.hash='#revise'`);
      await sleep(300);
      await ctx.key('k', MOD.meta);
      await sleep(400);
      const nums = await ctx.js(
        `[...document.querySelectorAll('.palette-keys .is-num')].map(e=>e.textContent).join(',')`
      );
      const before = await ctx.js(`document.getElementById('ide-body').dataset.view`);
      await ctx.key('2');
      await sleep(600);
      const after = await ctx.js(`document.getElementById('ide-body').dataset.view`);
      const closed = await ctx.js(`document.getElementById('palette').hidden`);
      if (after === 'diff') { await ctx.key('k', MOD.meta); await sleep(300); await ctx.key('2'); await sleep(400); }
      return {
        pass: closed && before !== after,
        detail: `번호=${nums} 모드 ${before}→${after} 닫힘=${closed}`,
      };
    },
  },

  {
    id: 'palette.search',
    area: '기능',
    title: '검색어를 치면 번호가 숨고 이름으로 걸러진다',
    async run(ctx) {
      await ctx.key('k', MOD.meta);
      await sleep(350);
      await ctx.js(
        `(()=>{const i=document.getElementById('palette-input');i.value='방침';i.dispatchEvent(new Event('input'))})()`
      );
      await sleep(300);
      const titles = await ctx.js(
        `[...document.querySelectorAll('.palette-title')].map(e=>e.textContent)`
      );
      const numsHidden = await ctx.js(`document.querySelectorAll('.palette-keys .is-num').length===0`);
      await ctx.key('Escape');
      await sleep(200);
      return {
        pass: numsHidden && titles.length >= 1 && titles.every((t) => t.includes('방침')),
        detail: `결과=${JSON.stringify(titles)} 번호숨김=${numsHidden}`,
      };
    },
  },

  {
    id: 'revise.happy',
    area: '기능',
    title: '⌘Enter 로 퇴고 제안을 받는다',
    async run(ctx) {
      await ctx.js(`location.hash='#revise'`);
      await sleep(300);
      await ctx.js(setText(SAMPLE));
      const started = Date.now();
      await ctx.key('Enter', MOD.meta);
      const done = await waitIdle(ctx, 35);
      const elapsed = Date.now() - started;
      const cards = await ctx.js(`document.querySelectorAll('#revise-results .card').length`);
      const badge = await ctx.js(`document.getElementById('suggest-count').textContent`);
      return {
        pass: done && cards > 0 && String(cards) === badge,
        detail: `제안 ${cards}개 · 배지 ${badge} · ${(elapsed / 1000).toFixed(1)}초`,
        evidence: { suggestions: cards, ms: elapsed },
      };
    },
  },

  {
    id: 'revise.apply',
    area: '기능',
    title: '제안을 반영하면 그 문장만 바뀐다',
    async run(ctx) {
      const before = await ctx.js(`document.getElementById('manuscript').value`);
      const ok = await ctx.js(
        `(()=>{const b=document.querySelector('#revise-results .card:not(.done) .btn-primary');if(!b)return false;b.click();return true})()`
      );
      if (!ok) return { pass: false, detail: '반영할 제안이 없습니다 (앞 검사 실패 영향)' };
      await sleep(500);
      const after = await ctx.js(`document.getElementById('manuscript').value`);
      const beforeN = before.split(/(?<=[.!?])\s+/).length;
      const afterN = after.split(/(?<=[.!?])\s+/).length;
      return {
        pass: before !== after && beforeN === afterN,
        detail: `원고 변경=${before !== after} 문장수 ${beforeN}→${afterN} (같아야 함)`,
      };
    },
  },

  {
    id: 'compare.split',
    area: '기능',
    title: '비교 보기가 좌우를 같은 행수로 세운다',
    async run(ctx) {
      await ctx.js(
        `[...document.querySelectorAll('.palette-item')].length;` +
        `document.getElementById('toggle-compare').click()`
      );
      await sleep(700);
      const view = await ctx.js(`document.getElementById('ide-body').dataset.view`);
      const left = await ctx.js(`document.querySelectorAll('#diff-left .diff-row').length`);
      const right = await ctx.js(`document.querySelectorAll('#diff-right .diff-row').length`);
      const changed = await ctx.js(`document.querySelectorAll('#diff-right .is-added').length`);
      await ctx.js(`document.getElementById('toggle-compare').click()`);
      await sleep(300);
      return {
        pass: view === 'diff' && left === right && left > 0,
        detail: `좌 ${left} / 우 ${right} / 강조 ${changed}`,
        evidence: { rows: left, changed },
      };
    },
  },

  {
    id: 'assist.modes',
    area: '기능',
    title: '도우미 네 모드가 모두 후보를 돌려준다',
    async run(ctx) {
      const cases = {
        synonym: ['쓸쓸하다', '불이 꺼진 창문은 어두웠다.'],
        recall: ['해가 뜨기 직전의 어스름한 시간대를 이르는 말', ''],
        impression: ['그는 문을 닫고 오래 서 있었다.', ''],
        classify: ['그날 저녁에 나는 그 골목을 다시 걸었다.', ''],
      };
      const out = {};
      for (const [mode, [query, context]] of Object.entries(cases)) {
        const r = await ctx.js(`
          fetch('/api/assist',{method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({mode:'${mode}',query:${JSON.stringify(query)},context:${JSON.stringify(context)}})})
            .then(r=>r.json()).then(d=>d.candidates||['ERR:'+(d.error&&d.error.code)])`);
        out[mode] = r;
      }
      const bad = Object.entries(out).filter(([, v]) => !v?.length || String(v[0]).startsWith('ERR'));
      return {
        pass: bad.length === 0,
        detail: Object.entries(out).map(([k, v]) => `${k}(${v.length})`).join(' '),
        evidence: { candidates: out },
      };
    },
  },

  /* ───────────────────────────────────────── 실패 처리 */

  {
    id: 'fail.short',
    area: '실패 처리',
    title: '30자 미만은 서버를 부르지 않고 안내한다',
    async run(ctx) {
      await ctx.js(`location.hash='#revise'`);
      await sleep(300);
      const n0 = ctx.events.requests.length;
      await ctx.js(setText('짧다.'));
      await ctx.js(`document.getElementById('revise-run').click()`);
      await sleep(900);
      const msg = await ctx.js(
        `(()=>{const n=document.getElementById('revise-notice');return n.hidden?'':n.textContent.trim()})()`
      );
      const stuck = await ctx.js(
        `document.getElementById('revise-results').textContent.includes('읽고 있습니다')`
      );
      const called = ctx.events.requests.length > n0;
      return {
        pass: msg.includes('붙여넣어') && !called && !stuck,
        detail: `문구="${msg}" 서버호출=${called} 로딩문구잔류=${stuck}`,
      };
    },
  },

  {
    id: 'fail.long',
    area: '실패 처리',
    title: '5,000자 초과는 글자 수와 함께 안내한다',
    async run(ctx) {
      const n0 = ctx.events.requests.length;
      await ctx.js(setText('가'.repeat(5001)));
      await ctx.js(`document.getElementById('revise-run').click()`);
      await sleep(900);
      const msg = await ctx.js(
        `(()=>{const n=document.getElementById('revise-notice');return n.hidden?'':n.textContent.trim()})()`
      );
      const called = ctx.events.requests.length > n0;
      await ctx.js(setText(''));
      return {
        pass: msg.includes('문단을 나눠') && msg.includes('5,001') && !called,
        detail: `문구="${msg}" 서버호출=${called}`,
      };
    },
  },

  {
    id: 'fail.badmode',
    area: '실패 처리',
    title: '없는 모드로 직접 POST 하면 400 을 준다',
    async run(ctx) {
      const r = await ctx.js(`
        fetch('/api/assist',{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({mode:'해킹',query:'x'})})
          .then(async r=>({status:r.status, code:(await r.json()).error?.code}))`);
      return {
        pass: r.status === 400 && r.code === 'BAD_REQUEST',
        detail: `HTTP ${r.status} code=${r.code}`,
      };
    },
  },

  {
    id: 'fail.dedupe',
    area: '실패 처리',
    title: '요청이 진행 중이면 두 번째 요청을 막는다',
    async run(ctx) {
      const r = await ctx.js(`
        import('/js/core/ai.js').then(async m=>{
          const p1 = m.revise({text:${JSON.stringify(SAMPLE)},sentences:['가'.repeat(40)],persona:{}});
          const second = await m.revise({text:${JSON.stringify(SAMPLE)},sentences:['나'],persona:{}})
            .then(()=> 'resolved').catch(e=>e.code);
          p1.catch(()=>{});
          return second;
        })`);
      return { pass: r === 'BUSY', detail: `두 번째 요청 결과=${r}` };
    },
  },

  /* ───────────────────────────────────────── 접근성 */

  {
    id: 'a11y.labels',
    area: '접근성',
    title: '모든 입력에 이름이 붙어 있다',
    async run(ctx) {
      const bad = await ctx.js(`
        [...document.querySelectorAll('input,select,textarea')]
          .filter(el => !el.closest('[hidden]'))
          .filter(el => !(
            el.labels?.length ||
            el.getAttribute('aria-label') ||
            el.getAttribute('aria-labelledby') ||
            el.type === 'hidden'
          ))
          .map(el => el.id || el.name || el.tagName)`);
      return { pass: bad.length === 0, detail: bad.length ? `이름 없음: ${bad}` : '전부 연결됨' };
    },
  },

  {
    id: 'a11y.buttons',
    area: '접근성',
    title: '버튼에 읽을 수 있는 이름이 있다',
    async run(ctx) {
      const bad = await ctx.js(`
        [...document.querySelectorAll('button')]
          .filter(b => !b.closest('[hidden]'))
          .filter(b => !(b.textContent.trim() || b.getAttribute('aria-label') || b.title))
          .map(b => b.id || b.className)`);
      return { pass: bad.length === 0, detail: bad.length ? `이름 없음: ${bad}` : '전부 있음' };
    },
  },

  /* ───────────────────────────────────────── 반응형 */

  {
    id: 'responsive.overflow',
    area: '반응형',
    title: '좁은 화면에서 가로 스크롤이 생기지 않는다',
    async run(ctx) {
      const widths = [320, 375, 768, 1440];
      const bad = [];
      const detail = [];
      for (const w of widths) {
        await ctx.viewport(w, 820);
        await sleep(450);
        const over = await ctx.js(
          `Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)`
        );
        detail.push(`${w}:${over}px`);
        if (over > 1) bad.push(w);
      }
      await ctx.viewport(1440, 950);
      await sleep(300);
      return { pass: bad.length === 0, detail: detail.join(' '), evidence: { overflow: detail } };
    },
  },

  /* ───────────────────────────────────────── 콘솔 */

  {
    id: 'runtime.clean',
    area: '런타임',
    title: '콘솔 오류와 예외가 없다',
    async run(ctx) {
      return {
        pass: ctx.events.exceptions.length === 0 && ctx.events.console.length === 0,
        detail: `예외 ${ctx.events.exceptions.length} / 콘솔오류 ${ctx.events.console.length}`,
        evidence: {
          exceptions: ctx.events.exceptions.slice(0, 5),
          console: ctx.events.console.slice(0, 5),
        },
      };
    },
  },
];

export { BASE, SAMPLE };
