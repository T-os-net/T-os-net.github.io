/* 原案: claude-v02「空もよう帳」。Codex改修: 手動動画、しおり、実画面の拡大。
   画像リンク・本文・動画の標準操作はJSなしでも利用可能。 */
(() => {
  'use strict';
  const root = document.documentElement;
  const all = selector => [...document.querySelectorAll(selector)];
  const one = selector => document.querySelector(selector);
  try {
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    const video = one('.clip');
    const videoButton = one('.vbtn');
    let stopped = false;
    const revealAll = () => all('.reveal').forEach(el => el.classList.add('in'));
    const syncMotion = () => {
      const calm = stopped || motion.matches;
      root.classList.toggle('calm', calm);
      all('.calm-btn').forEach(button => {
        button.setAttribute('aria-pressed', String(calm));
        button.disabled = motion.matches;
        button.textContent = motion.matches ? '動きを減らす設定中' : calm ? '動きを再開' : '動きを止める';
      });
      if (calm) { revealAll(); video.pause(); }
    };
    all('.calm-btn').forEach(button => button.addEventListener('click', () => { stopped = !stopped; syncMotion(); }));
    motion.addEventListener('change', syncMotion);
    syncMotion();
    // 収録数は常に正しい値を表示。カウントアップの読み上げや途中停止を避ける。
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(entries => entries.forEach(entry => {
        if (entry.isIntersecting) { entry.target.classList.add('in'); observer.unobserve(entry.target); }
      }), { threshold: 0.1 });
      all('.reveal').forEach(el => observer.observe(el));
      // 利用者が開始した動画も、画面外や別タブへ移ったら停止。自動再開はしない。
      new IntersectionObserver(entries => {
        if (!entries[0].isIntersecting) video.pause();
      }, { threshold: 0.1 }).observe(video);
    } else revealAll();
    setTimeout(revealAll, 6000);
    const videoLabel = () => { videoButton.textContent = video.paused ? '動画を再生' : '動画を一時停止'; };
    videoButton.addEventListener('click', () => {
      if (video.paused) video.play().catch(() => { videoButton.textContent = '再生できませんでした。もう一度試す'; });
      else video.pause();
    });
    video.addEventListener('play', videoLabel);
    video.addEventListener('pause', videoLabel);
    video.addEventListener('ended', videoLabel);
    document.addEventListener('visibilitychange', () => { if (document.hidden) video.pause(); });
    videoLabel();

    // 実画像をそのまま拡大する。作り物のスコアや現在の予報は表示しない。
    const dialog = one('.viewer');
    if (typeof dialog.showModal === 'function') {
      const shots = ['01-list-decide', '03-detail-score', '04-filter', '06-notify-priming'];
      const labels = ['候補を比べる', '理由と持ち物', '入場無料で探す', '予定の通知'];
      const notes = ['1.3.0の一覧画面です。', '1.3.4の施設詳細画面です。', '1.3.0の絞り込み画面です。', '1.3.0の通知案内画面です。'];
      const image = one('.viewer-image');
      const title = one('#viewer-title');
      const status = one('.viewer-status');
      const loaded = () => { image.hidden = false; status.hidden = true; };
      image.addEventListener('load', loaded);
      image.addEventListener('error', () => { status.hidden = false; status.textContent = '画面を読み込めませんでした。一度閉じて、もう一度お試しください。'; });
      const count = one('.viewer-count');
      const previous = one('.viewer-prev');
      const next = one('.viewer-next');
      let current = 0, origin = null;
      const render = () => {
        const source = one(`[data-shot="${current}"] img`);
        image.hidden = true; status.hidden = false; status.textContent = '画面を読み込み中…';
        image.src = source.closest("a").href;
        image.width = source.width;
        image.height = source.height;
        if (image.complete && image.naturalWidth) loaded();
        image.alt = source.alt;
        title.textContent = labels[current];
        one('#viewer-note').textContent = notes[current] + '表示中の天気やスコアは撮影時点のもので、現在の予報ではありません。';
        count.textContent = `${current + 1} / ${shots.length}`;
        previous.disabled = current === 0;
        next.disabled = current === shots.length - 1;
        one('.viewer-scroll').scrollTop = 0;
      };
      all('[data-shot]').forEach(link => link.addEventListener('click', event => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault(); origin = link; current = Number(link.dataset.shot);
        render(); dialog.showModal(); root.classList.add('gallery-open');
      }));
      previous.addEventListener('click', () => { if (current > 0) { current--; render(); if (previous.disabled) next.focus(); } });
      next.addEventListener('click', () => { if (current < shots.length - 1) { current++; render(); if (next.disabled) previous.focus(); } });
      one('.viewer-close').addEventListener('click', () => dialog.close());
      dialog.addEventListener('click', event => {
        const box = dialog.getBoundingClientRect();
        if (event.target === dialog && (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom)) dialog.close();
      });
      dialog.addEventListener('close', () => { root.classList.remove('gallery-open'); origin?.focus({ preventScroll: true }); });
      dialog.addEventListener('keydown', event => {
        if (event.key !== 'Tab') return;
        const controls = [...dialog.querySelectorAll('button:not(:disabled), [tabindex="0"]')];
        const first = controls[0], last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      });
    }
    window.__soraReady = true;
  } catch (error) {
    root.classList.remove('js');
    console.warn('装飾の初期化を省略しました。本文と画像リンクは利用できます。', error);
  }
})();
