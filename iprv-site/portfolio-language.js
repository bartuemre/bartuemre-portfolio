// Pass the portfolio's selected language to the existing IPRV language setting.
// A direct visit without ?lang= retains the application's own saved preference.
(() => {
  const language = new URLSearchParams(window.location.search).get('lang');
  if (language !== 'en' && language !== 'tr') return;
  document.documentElement.lang = language;
  try { localStorage.setItem('iprv.language', language); } catch {}
})();
