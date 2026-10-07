import { installRouter } from './router.js';

addEventListener('pointermove', (event) => {
  const root = document.documentElement;
  root.dataset.pointer = '';
  root.style.setProperty('--mx', `${event.clientX}px`);
  root.style.setProperty('--my', `${event.clientY}px`);
}, { passive: true });

const html = document.documentElement;
const stopDrag = () => html.classList.remove('dragging');
addEventListener('pointerdown', () => html.classList.add('dragging'));
addEventListener('pointerup', stopDrag);
addEventListener('pointercancel', stopDrag);
addEventListener('blur', stopDrag);
for (const img of document.querySelectorAll('img')) {
  img.draggable = false;
}

const cursorSets = [
  ['--cur-default', 'arrow', '2 2', 5],
  ['--cur-link', 'link', '2 2', 5],
  ['--cur-text', 'text', '16 16', 2],
];

if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const root = document.documentElement.style;
  let frame = 0;
  const step = () => {
    for (const [prop, name, hotspot, count] of cursorSets) {
      root.setProperty(prop, `url("/assets/media/cursors/${name}-${frame % count}.png") ${hotspot}`);
    }
    frame += 1;
  };
  step();
  setInterval(step, 100);
}

const routes = fetch('/assets/routes.json')
  .then((response) => response.json())
  .then((data) => new Set(Object.values(data.routes).flat()))
  .catch((error) => {
    console.error('route data failed to load', error);
    return null;
  });

if ('navigation' in window) {
  installRouter(window.navigation, routes);
}
