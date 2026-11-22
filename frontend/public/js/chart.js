// 365일 신호 그래프(SVG 직접 그림, 라이브러리 없음). 일별 선 + 7일 이동평균 + 메모 있는 날 점.
const NS = "http://www.w3.org/2000/svg";
const fmt = (n) => Math.round(n).toLocaleString("ko-KR");

function el(name, attrs = {}) {
  const e = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

export function renderSignal(container, readout, series, memos) {
  container.replaceChildren();
  if (!series.length) {
    const p = document.createElement("div");
    p.className = "placeholder";
    p.textContent = "데이터가 없습니다. 오른쪽에서 추가하세요.";
    container.append(p);
    return;
  }
  const W = container.clientWidth || 800;
  const H = container.clientHeight || 140;
  const pad = { l: 44, r: 8, t: 6, b: 18 };
  // 스파이크 하나(3만 회)가 축을 독점하지 않게 로그 축을 쓴다
  const vals = series.map((p) => Math.max(1, p.value));
  const lo = Math.log10(Math.min(...vals) * 0.9);
  const hi = Math.log10(Math.max(...vals) * 1.05);
  const x = (i) => pad.l + (i / Math.max(1, series.length - 1)) * (W - pad.l - pad.r);
  const y = (v) => pad.t + (1 - (Math.log10(Math.max(1, v)) - lo) / (hi - lo || 1)) * (H - pad.t - pad.b);

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });

  const axis = el("g", { class: "axis" });
  for (const v of niceTicks(10 ** lo, 10 ** hi)) {
    const yy = y(v);
    axis.append(el("line", { x1: pad.l, x2: W - pad.r, y1: yy, y2: yy, "stroke-dasharray": "2 4" }));
    const t = el("text", { x: pad.l - 6, y: yy + 4, "text-anchor": "end" });
    t.textContent = v >= 1000 ? `${v / 1000}천` : v;
    axis.append(t);
  }
  let lastMonth = "";
  let lastX = -Infinity;
  series.forEach((p, i) => {
    const m = p.date.slice(0, 7);
    if (m !== lastMonth && p.date.slice(8) <= "07") {
      lastMonth = m;
      if (x(i) - lastX > (W < 600 ? 52 : 40) && (m.endsWith("-01") || i === 0 || series.length < 120 || Number(m.slice(5)) % 2 === 1)) {
        lastX = x(i);
        const t = el("text", { x: x(i), y: H - 3, "text-anchor": "start" });
        t.textContent = m.endsWith("-01") || i === 0 ? m.replace("-", ".") : `${Number(m.slice(5))}월`;
        axis.append(t);
      }
    }
  });
  svg.append(axis);

  const line = series.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join("");
  svg.append(el("path", { class: "area", d: `${line}L${x(series.length - 1)},${H - pad.b}L${x(0)},${H - pad.b}Z` }));
  svg.append(el("path", { class: "line", d: line }));
  const ma = series.map((p, i) => [i, p.ma7]).filter(([, v]) => v != null);
  if (ma.length) svg.append(el("path", { class: "ma", d: ma.map(([i, v], k) => `${k ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("") }));
  series.forEach((p, i) => { if (memos.get(p.date)) svg.append(el("circle", { class: "spike", cx: x(i), cy: y(p.value), r: 2.6 })); });

  const cursor = el("line", { class: "cursor", y1: pad.t, y2: H - pad.b, visibility: "hidden" });
  const dot = el("circle", { class: "dot", r: 4, visibility: "hidden" });
  svg.append(cursor, dot);
  container.append(svg);

  const defaultText = readout.dataset.default || readout.textContent;
  readout.dataset.default = defaultText;
  const show = (clientX) => {
    const rect = svg.getBoundingClientRect();
    const px = ((clientX - rect.left) / rect.width) * W;
    const i = Math.round(((px - pad.l) / (W - pad.l - pad.r)) * (series.length - 1));
    if (i < 0 || i >= series.length) return hide();
    const p = series[i];
    for (const [k, v] of [["x1", x(i)], ["x2", x(i)]]) cursor.setAttribute(k, v);
    dot.setAttribute("cx", x(i)); dot.setAttribute("cy", y(p.value));
    cursor.setAttribute("visibility", "visible"); dot.setAttribute("visibility", "visible");
    const memo = memos.get(p.date);
    readout.innerHTML = `${p.date} <b>${fmt(p.value)}회</b>` + (p.ma7 != null ? ` · 7일 평균 ${fmt(p.ma7)}` : "") +
      (memo ? ` <span class="memo">${escapeHtml(memo)}</span>` : "");
  };
  const hide = () => {
    cursor.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden");
    readout.textContent = defaultText;
  };
  svg.addEventListener("pointermove", (e) => show(e.clientX));
  svg.addEventListener("pointerleave", hide);
}

function niceTicks(min, max) {
  const out = [];
  for (const base of [1000, 2000, 5000, 10000, 20000, 50000]) if (base > min && base < max) out.push(base);
  return out.length > 4 ? out.filter((_, i) => i % 2 === 0) : out;
}

export function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
