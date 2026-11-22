// Vercel 빌드 단계: 환경 변수 API_BASE_URL → public/config.js
// 바닐라 JS 는 브라우저에서 process.env 를 읽을 수 없으므로, 빌드 때 설정 파일을 만들어 넣는다.
import { writeFileSync } from "node:fs";

const url = (process.env.API_BASE_URL || "http://localhost:8000").trim().replace(/\/+$/, "");
if (!/^https?:\/\//.test(url)) {
  console.error(`API_BASE_URL 이 http(s) 주소가 아닙니다: ${url}`);
  process.exit(1);
}
writeFileSync(new URL("./public/config.js", import.meta.url),
  `// build.mjs 가 생성한 파일. 직접 고치지 말고 API_BASE_URL 환경 변수를 바꾸세요.\nwindow.APP_CONFIG = { API_BASE_URL: ${JSON.stringify(url)} };\n`);
console.log(`config.js 생성: API_BASE_URL=${url}`);
