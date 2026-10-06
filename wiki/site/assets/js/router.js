import { swapWithTransition } from './transitions.js';

let routes = null;

function updatePrimaryNav(pathname) {
  const primary = document.querySelector('nav[aria-label="Primary"]');
  if (!primary) {
    return;
  }
  for (const link of primary.querySelectorAll('a')) {
    link.removeAttribute('aria-current');
    if (link.pathname === pathname) {
      link.setAttribute('aria-current', 'page');
    }
  }
}

function swapHead(doc) {
  document.title = doc.title;
  const description = document.querySelector('meta[name="description"]');
  const incoming = doc.querySelector('meta[name="description"]');
  if (description && incoming) {
    description.setAttribute('content', incoming.getAttribute('content'));
  }
  const canonical = document.querySelector('link[rel="canonical"]');
  const incomingCanonical = doc.querySelector('link[rel="canonical"]');
  if (canonical && incomingCanonical) {
    canonical.setAttribute('href', incomingCanonical.getAttribute('href'));
  }
}

function applySwap(doc, incomingMain, url) {
  document.querySelector('main').replaceChildren(...incomingMain.childNodes);
  swapHead(doc);
  const heading = document.querySelector('main h1');
  if (heading) {
    heading.focus();
    const announcer = document.querySelector('#announcer');
    if (announcer) {
      announcer.textContent = heading.textContent;
    }
  }
  updatePrimaryNav(url.pathname);
}

async function fetchAndSwap(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error('route fetch failed');
  }
  const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
  const incomingMain = doc.querySelector('main');
  if (!incomingMain) {
    throw new Error('route document malformed');
  }
  await swapWithTransition(() => applySwap(doc, incomingMain, url));
}

function onNavigate(event) {
  if (!event.canIntercept) {
    return;
  }
  const url = new URL(event.destination.url);
  if (url.pathname === window.location.pathname) {
    return;
  }
  if (routes && !routes.has(url.pathname)) {
    return;
  }
  event.intercept({
    handler: () => fetchAndSwap(url),
  });
}

export function installRouter(navigation, routePromise) {
  routePromise.then((data) => {
    routes = data;
    updatePrimaryNav(window.location.pathname);
  });
  navigation.addEventListener('navigate', onNavigate);
  navigation.addEventListener('navigateerror', () => {
    navigation.removeEventListener('navigate', onNavigate);
    window.location.reload();
  });
  updatePrimaryNav(window.location.pathname);
}
