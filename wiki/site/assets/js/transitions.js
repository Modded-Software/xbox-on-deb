const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

export function swapWithTransition(applySwap) {
  const reduced = window.matchMedia(REDUCED_MOTION_QUERY).matches;
  if ('startViewTransition' in document && !reduced) {
    return document.startViewTransition(applySwap).finished;
  }
  applySwap();
  return Promise.resolve();
}
