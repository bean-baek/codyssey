/**
 * js/app.js — 부트스트랩
 *
 * 화면 모듈을 한 번씩 켜고 라우팅을 시작한다. 모든 AI 호출은
 * js/core/ai.js 한 곳을 거치므로 여기에는 fetch 가 없다.
 */

import { initNav } from './core/nav.js';
import { initPersona } from './ui/persona.js';
import { initEditor } from './ui/editor.js';
import { initAssist } from './ui/assist.js';

const persona = initPersona();
initEditor(() => persona.read());
initAssist();
initNav();
