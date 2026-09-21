/**
 * qa/harness.mjs — 브라우저 조작 공통 도구
 *
 * 헤드리스 크롬에 CDP 로 붙어 실제 사용자처럼 키를 누르고 클릭한다.
 * 화면을 거치지 않는 단위 테스트로는 '⌘K 가 크롬 주소창에 먹히는가' 같은 것을
 * 잡을 수 없어서, QA 는 반드시 실제 브라우저를 통과시킨다.
 *
 * --window-size 는 500px 밑으로 내려가지 않으므로 모바일 폭 검증에는
 * Emulation.setDeviceMetricsOverride 를 쓴다.
 */

import { spawn } from 'node:child_process';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PORT = 9222;

export const MOD = { none: 0, alt: 1, ctrl: 2, meta: 4, shift: 8 };
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** 크롬을 띄우고 디버깅 포트가 열릴 때까지 기다린다. */
export async function launchChrome(profileDir) {
  spawn(CHROME, [
    '--headless=new',
    '--disable-gpu',
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${profileDir}`,
    'about:blank',
  ], { detached: true, stdio: 'ignore' }).unref();

  for (let i = 0; i < 60; i += 1) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      if ((await res.json()).some((t) => t.type === 'page')) return;
    } catch { /* 아직 */ }
    await sleep(250);
  }
  throw new Error('크롬 디버깅 포트가 열리지 않았습니다');
}

export async function connect() {
  const res = await fetch(`http://127.0.0.1:${PORT}/json/list`);
  const page = (await res.json()).find((t) => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((r) => { ws.onopen = r; });

  let id = 0;
  const pending = new Map();
  const events = { console: [], exceptions: [], requests: [], failures: [] };

  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) {
      const { resolve, reject } = pending.get(m.id);
      pending.delete(m.id);
      m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
      return;
    }
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
      events.console.push(m.params.args.map((a) => a.value ?? a.description ?? '').join(' '));
    }
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails;
      events.exceptions.push((d.exception?.description || d.text || '').split('\n')[0]);
    }
    if (m.method === 'Network.responseReceived') {
      const { url, status } = m.params.response;
      if (url.includes('/api/')) events.requests.push({ url, status, at: Date.now() });
    }
    if (m.method === 'Network.loadingFailed' && m.params.type !== 'Image') {
      events.failures.push(m.params.errorText);
    }
  };

  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const n = (id += 1);
      pending.set(n, { resolve, reject });
      ws.send(JSON.stringify({ id: n, method, params }));
    });

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Network.enable');
  await send('Network.setCacheDisabled', { cacheDisabled: true });

  /** 페이지에서 표현식을 평가한다. 예외는 문자열로 돌려준다. */
  const evaluate = async (expression) => {
    const r = await send('Runtime.evaluate', {
      expression, awaitPromise: true, returnByValue: true,
    });
    if (r.exceptionDetails) {
      return { error: (r.exceptionDetails.exception?.description || '').split('\n')[0] };
    }
    return { value: r.result?.value };
  };

  const js = async (expression) => (await evaluate(expression)).value;

  const key = async (k, modifiers = 0) => {
    const code = k.length === 1 ? k.toUpperCase().charCodeAt(0) : (k === 'Enter' ? 13 : 0);
    for (const type of ['keyDown', 'keyUp']) {
      await send('Input.dispatchKeyEvent', {
        type, key: k, modifiers, windowsVirtualKeyCode: code,
        text: type === 'keyDown' && k.length === 1 && modifiers === 0 ? k : undefined,
      });
    }
  };

  const viewport = (width, height, mobile = width < 700) =>
    send('Emulation.setDeviceMetricsOverride', {
      width, height, deviceScaleFactor: 2, mobile,
    });

  const scheme = (value) =>
    send('Emulation.setEmulatedMedia', {
      features: [{ name: 'prefers-color-scheme', value }],
    });

  /** 같은 URL 로 navigate 하면 문서가 다시 실행되지 않는다. 항상 강제 새로고침한다. */
  const goto = async (url) => {
    events.exceptions.length = 0;
    events.console.length = 0;
    await send('Page.navigate', { url });
    await sleep(400);
    await send('Page.reload', { ignoreCache: true });
    await sleep(2200);
  };

  const screenshot = async () => (await send('Page.captureScreenshot', { format: 'png' })).data;

  return { send, js, evaluate, key, viewport, scheme, goto, screenshot, events,
    close: () => ws.close() };
}
