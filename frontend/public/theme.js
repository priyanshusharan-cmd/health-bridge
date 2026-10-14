// Apply the preference before rendering to avoid a bright flash in dark mode.
(() => {
  let theme;
  try { theme = localStorage.getItem('healthbridge-theme'); } catch {}
  if (theme !== 'light' && theme !== 'dark') theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
})();
