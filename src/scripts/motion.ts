type MotionPreference = 'paused' | 'running' | null;
const system = matchMedia('(prefers-reduced-motion: reduce)');
const listeners = new Set<(paused: boolean) => void>();
let preference: MotionPreference = null;

function readPreference(value: string | null): MotionPreference {
  return value === 'paused' || value === 'running' ? value : null;
}
try { preference = readPreference(localStorage.getItem('portfolio-motion')); } catch {}

export function isMotionPaused() {
  // A system request for less motion always takes precedence.
  return system.matches || preference === 'paused';
}
export function motionIsSystemReduced() { return system.matches; }
function notify() {
  const paused = isMotionPaused();
  document.documentElement.dataset.motion = paused ? 'paused' : 'running';
  listeners.forEach(listener => listener(paused));
}
export function setMotionPaused(paused: boolean) {
  preference = paused ? 'paused' : 'running';
  try { localStorage.setItem('portfolio-motion', preference); } catch {}
  notify();
}
export function onMotionChange(listener: (paused: boolean) => void) {
  listeners.add(listener);
  listener(isMotionPaused());
  return () => listeners.delete(listener);
}
system.addEventListener('change', notify);
window.addEventListener('storage', event => {
  if (event.key === 'portfolio-motion' || event.key === null) {
    preference = readPreference(event.key === null ? null : event.newValue);
    notify();
  }
});
notify();
