/**
 * js/core/nav.js — 해시 라우팅
 *
 * 한 문서 안에서 섹션을 갈아 끼운다. 서버 라우팅이 없으므로
 * Vercel에서 새로고침해도 404가 나지 않는다.
 */

const DEFAULT = 'home';

function sectionFromHash() {
  const id = (location.hash || '').replace(/^#/, '');
  return document.querySelector(`[data-section="${CSS.escape(id)}"]`) ? id : DEFAULT;
}

/**
 * @param {(id: string) => void} [onChange] 섹션이 바뀔 때마다 호출된다
 */
export function initNav(onChange) {
  const sections = [...document.querySelectorAll('[data-section]')];
  const links = [...document.querySelectorAll('[data-nav]')];

  function show(id) {
    sections.forEach((el) => {
      el.hidden = el.dataset.section !== id;
    });
    links.forEach((a) => {
      if (a.dataset.nav === id) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });

    const active = sections.find((el) => el.dataset.section === id);
    if (active) document.title = `${active.querySelector('h1, h2')?.textContent?.trim() || '결'} · 결`;

    onChange?.(id);
  }

  addEventListener('hashchange', () => {
    show(sectionFromHash());
    // 섹션을 바꿀 때는 위에서부터 읽는 것이 맞다
    scrollTo({ top: 0, behavior: 'instant' });
  });

  show(sectionFromHash());

  // 첫 로드에 #revise 같은 해시가 있으면 브라우저가 그 id로 스크롤해
  // 고정 상단바가 제목을 덮는다. 섹션 전환식이라 스크롤 자체가 필요 없다.
  if (location.hash) requestAnimationFrame(() => scrollTo({ top: 0, behavior: 'instant' }));
}
