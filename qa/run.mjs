/**
 * qa/run.mjs — QA 회차 실행기
 *
 *   node qa/run.mjs            검사 전체 실행 → 보고서 + 이력 누적
 *   node qa/run.mjs --only 기능 특정 영역만
 *
 * 회차마다 qa/reports/<회차>.md 를 남기고 qa/history.jsonl 에 한 줄을 덧붙인다.
 * 이력이 쌓여야 '언제부터 깨졌나', '느려지고 있나' 를 볼 수 있다.
 *
 * 이 파일은 사실만 기록한다. 해석과 제안은 gyeol-qa 에이전트가 쓴다.
 */

import { mkdirSync, writeFileSync, appendFileSync, existsSync, readFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { launchChrome, connect, sleep } from './harness.mjs';
import { checks, BASE } from './checks.mjs';
import { inspect, COLLECT_SNIPPET } from './copy.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const QA = join(ROOT, 'qa');
const REPORTS = join(QA, 'reports');
const HISTORY = join(QA, 'history.jsonl');

const onlyArea = process.argv.includes('--only')
  ? process.argv[process.argv.indexOf('--only') + 1]
  : null;

/* 개발 서버가 떠 있지 않으면 띄운다 */
async function ensureServer() {
  try {
    const r = await fetch(BASE, { signal: AbortSignal.timeout(1500) });
    if (r.ok) return null;
  } catch { /* 없다 */ }

  const proc = spawn(join(ROOT, '.venv/bin/python'), [join(ROOT, 'tools/dev_server.py'), '8899'], {
    cwd: ROOT, detached: true, stdio: 'ignore',
  });
  proc.unref();
  for (let i = 0; i < 40; i += 1) {
    await sleep(300);
    try {
      if ((await fetch(BASE, { signal: AbortSignal.timeout(1000) })).ok) return proc;
    } catch { /* 아직 */ }
  }
  throw new Error('개발 서버를 띄우지 못했습니다');
}

function previousRun() {
  if (!existsSync(HISTORY)) return null;
  const lines = readFileSync(HISTORY, 'utf8').trim().split('\n').filter(Boolean);
  return lines.length ? JSON.parse(lines[lines.length - 1]) : null;
}

async function main() {
  mkdirSync(REPORTS, { recursive: true });
  await ensureServer();
  await launchChrome(join(QA, '.chrome-profile'));
  const ctx = await connect();

  await ctx.viewport(1440, 950);
  await ctx.scheme('light');
  await ctx.goto(`${BASE}/#revise`);

  const started = Date.now();
  const results = [];

  for (const check of checks) {
    if (onlyArea && check.area !== onlyArea) continue;
    const t0 = Date.now();
    try {
      const r = await check.run(ctx);
      results.push({ ...check, ...r, ms: Date.now() - t0 });
    } catch (err) {
      results.push({
        ...check, pass: false, detail: `검사 자체가 실패: ${err.message}`.slice(0, 300),
        ms: Date.now() - t0, crashed: true,
      });
    }
    process.stdout.write(`${results.at(-1).pass ? '✓' : '✗'} ${check.id}\n`);
  }

  /* 문구 검사 */
  await ctx.goto(`${BASE}/#home`);
  const strings = (await ctx.js(COLLECT_SNIPPET)) || [];
  const copyIssues = strings.flatMap((s) => inspect(s.text, s.where));

  const durationMs = Date.now() - started;
  ctx.close();

  /* 집계 */
  const passed = results.filter((r) => r.pass).length;
  const failed = results.length - passed;
  const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);

  const record = {
    at: new Date().toISOString(),
    stamp,
    total: results.length,
    passed,
    failed,
    durationMs,
    copyErrors: copyIssues.filter((i) => i.severity === 'error').length,
    copyWarns: copyIssues.filter((i) => i.severity === 'warn').length,
    checks: Object.fromEntries(results.map((r) => [r.id, r.pass])),
    metrics: Object.fromEntries(
      results.filter((r) => r.evidence).map((r) => [r.id, r.evidence])
    ),
  };

  const prev = previousRun();
  writeFileSync(join(REPORTS, `${stamp}.md`), report(record, results, copyIssues, prev), 'utf8');
  appendFileSync(HISTORY, `${JSON.stringify(record)}\n`, 'utf8');

  console.log(`\n${passed}/${results.length} 통과 · 문구 오류 ${record.copyErrors} 경고 ${record.copyWarns}`);
  console.log(`보고서: qa/reports/${stamp}.md`);
  process.exit(failed || record.copyErrors ? 1 : 0);
}

function report(rec, results, copy, prev) {
  const L = [];
  L.push(`# QA 회차 보고서 — ${rec.stamp}`);
  L.push('');
  L.push(`| 항목 | 값 |`);
  L.push(`| --- | --- |`);
  L.push(`| 검사 | ${rec.passed}/${rec.total} 통과 |`);
  L.push(`| 문구 | 오류 ${rec.copyErrors} · 경고 ${rec.copyWarns} |`);
  L.push(`| 소요 | ${(rec.durationMs / 1000).toFixed(1)}초 |`);
  L.push('');

  /* 지난 회차와의 차이 */
  if (prev) {
    const changes = [];
    for (const [id, pass] of Object.entries(rec.checks)) {
      const was = prev.checks?.[id];
      if (was === undefined) changes.push(`- 🆕 \`${id}\` 새 검사 — ${pass ? '통과' : '실패'}`);
      else if (was !== pass) changes.push(`- ${pass ? '🟢 복구' : '🔴 회귀'} \`${id}\` ${was ? '통과' : '실패'} → ${pass ? '통과' : '실패'}`);
    }
    for (const id of Object.keys(prev.checks || {})) {
      if (!(id in rec.checks)) changes.push(`- ⚪ \`${id}\` 이번 회차에서 사라짐`);
    }
    L.push(`## 지난 회차 대비 (${prev.stamp})`);
    L.push('');
    L.push(changes.length ? changes.join('\n') : '- 통과/실패 구성에 변화 없음');
    const dt = rec.durationMs - prev.durationMs;
    L.push(`- 소요 시간 ${(dt / 1000).toFixed(1)}초 ${dt > 0 ? '증가' : '감소'}`);
    L.push('');
  } else {
    L.push('## 지난 회차 대비');
    L.push('');
    L.push('- 첫 회차입니다. 다음 회차부터 비교가 붙습니다.');
    L.push('');
  }

  /* 검사 결과 */
  L.push('## 검사 결과');
  L.push('');
  const areas = [...new Set(results.map((r) => r.area))];
  for (const area of areas) {
    L.push(`### ${area}`);
    L.push('');
    L.push('| | 검사 | 관찰값 |');
    L.push('| --- | --- | --- |');
    for (const r of results.filter((x) => x.area === area)) {
      L.push(`| ${r.pass ? '✓' : '✗'} | ${r.title} | ${String(r.detail).replace(/\|/g, '\\|')} |`);
    }
    L.push('');
  }

  /* 문구 */
  L.push('## 문구 검사');
  L.push('');
  if (!copy.length) {
    L.push('발견된 문제가 없습니다.');
  } else {
    L.push('| 심각도 | 위치 | 발견 | 고칠 말 | 근거 |');
    L.push('| --- | --- | --- | --- | --- |');
    for (const c of copy.slice(0, 40)) {
      L.push(`| ${c.severity === 'error' ? '오류' : '경고'} | ${c.where} | ${c.snippet.replace(/\|/g, '\\|')} | ${c.suggest} | ${c.why} |`);
    }
    if (copy.length > 40) L.push(`\n…외 ${copy.length - 40}건`);
  }
  L.push('');

  /* 에이전트가 채울 자리 */
  L.push('---');
  L.push('');
  L.push('## 해석과 제안');
  L.push('');
  L.push('> 이 아래는 `gyeol-qa` 에이전트가 채운다. 실행기는 사실만 기록한다.');
  L.push('');
  L.push('### 작업자 관점');
  L.push('');
  L.push('_(비어 있음)_');
  L.push('');
  L.push('### 사용자 관점');
  L.push('');
  L.push('_(비어 있음)_');
  L.push('');
  L.push('### 다음 회차에 제안하는 작업');
  L.push('');
  L.push('_(비어 있음)_');
  L.push('');
  return L.join('\n');
}

main().catch((err) => {
  console.error('실행 실패:', err.message);
  process.exit(2);
});
