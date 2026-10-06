import { installRouter } from './router.js';

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
