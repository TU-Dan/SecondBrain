(function () {
  let saved = 'light';
  try { saved = localStorage.getItem('knowledge-theme') || 'light'; } catch (_) {}
  if (saved === 'dark') document.documentElement.dataset.theme = 'dark';

  function updateButtons() {
    const dark = document.documentElement.dataset.theme === 'dark';
    for (const button of document.querySelectorAll('[data-theme-toggle]')) {
      button.setAttribute('aria-label', dark ? '切换浅色模式' : '切换深色模式');
      const label = button.querySelector('.theme-label');
      if (label) label.textContent = dark ? '浅色模式' : '深色模式';
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    updateButtons();
    for (const button of document.querySelectorAll('[data-theme-toggle]')) {
      button.addEventListener('click', () => {
        const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        document.documentElement.dataset.theme = next;
        try { localStorage.setItem('knowledge-theme', next); } catch (_) {}
        updateButtons();
      });
    }
  });
})();
