const labels: Record<string, string> = { 'Switch to light theme': 'Açık temaya geç', 'Switch to dark theme': 'Koyu temaya geç', 'Open navigation': 'Menüyü aç', 'Close navigation': 'Menüyü kapat' };
const t = (label: string) => document.documentElement.lang === 'tr' ? labels[label] ?? label : label;
const root = document.documentElement;
const themeButton = document.querySelector<HTMLButtonElement>('#theme-toggle');
const systemTheme = matchMedia('(prefers-color-scheme: dark)');
let hasPreference = false;
try { hasPreference = ['light', 'dark'].includes(localStorage.getItem('portfolio-theme') ?? ''); } catch {}
function setTheme(theme: string) {
  root.dataset.theme = theme;
  themeButton?.setAttribute('aria-label', t(`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`));
}
setTheme(root.dataset.theme ?? (systemTheme.matches ? 'dark' : 'light'));
if (themeButton) {
  themeButton.hidden = false;
  themeButton.addEventListener('click', () => {
    const theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    setTheme(theme);
    hasPreference = true;
    try { localStorage.setItem('portfolio-theme', theme); } catch {}
  });
}
systemTheme.addEventListener('change', (event) => { if (!hasPreference) setTheme(event.matches ? 'dark' : 'light'); });

const menuButton = document.querySelector<HTMLButtonElement>('#menu-toggle');
const nav = document.querySelector<HTMLElement>('#primary-navigation');
const mobile = matchMedia('(max-width: 1000px)');
function closeMenu(returnFocus = false) {
  menuButton?.setAttribute('aria-expanded', 'false');
  menuButton?.setAttribute('aria-label', t('Open navigation'));
  if (nav) nav.hidden = mobile.matches;
  if (returnFocus) menuButton?.focus();
}
if (menuButton && nav) {
  menuButton.hidden = !mobile.matches;
  closeMenu();
  menuButton.addEventListener('click', () => {
    const open = menuButton.getAttribute('aria-expanded') !== 'true';
    menuButton.setAttribute('aria-expanded', String(open));
    menuButton.setAttribute('aria-label', t(open ? 'Close navigation' : 'Open navigation'));
    nav.hidden = !open;
  });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && menuButton.getAttribute('aria-expanded') === 'true') closeMenu(true); });
  document.addEventListener('click', (event) => { if (mobile.matches && event.target instanceof Node && !nav.contains(event.target) && !menuButton.contains(event.target)) closeMenu(); });
  nav.addEventListener('click', (event) => { if (mobile.matches && event.target instanceof Element && event.target.closest('a')) closeMenu(); });
  mobile.addEventListener('change', () => { menuButton.hidden = !mobile.matches; closeMenu(); });
}

const motion = matchMedia('(prefers-reduced-motion: reduce)');
if (!motion.matches && 'IntersectionObserver' in window) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('revealed');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.08 });
  // Content stays visible by default; only below-the-fold elements are enhanced.
  document.querySelectorAll<HTMLElement>('[data-reveal]').forEach((element) => {
    if (element.getBoundingClientRect().top > innerHeight) {
      element.classList.add('will-reveal');
      observer.observe(element);
    }
  });
  motion.addEventListener('change', () => {
    if (motion.matches) { document.querySelectorAll('.will-reveal').forEach((el) => el.classList.add('revealed')); observer.disconnect(); }
  });
}
