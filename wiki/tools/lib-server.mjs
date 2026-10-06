import { createServer } from 'node:http';
import { readFileSync, existsSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';
import { SITE } from './lib-docs.mjs';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.xml': 'application/xml; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.webp': 'image/webp',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png': 'image/png',
  '.gif': 'image/gif',
  '.avif': 'image/avif',
};

function serve(request, response) {
  const pathname = decodeURIComponent(new URL(request.url, 'http://local').pathname);
  let file = join(SITE, pathname);
  if (pathname.endsWith('/')) {
    file = join(file, 'index.html');
  }
  if (!existsSync(file) || !statSync(file).isFile()) {
    response.writeHead(404, { 'content-type': MIME['.html'] });
    response.end(readFileSync(join(SITE, 'en', '404.html')));
    return;
  }
  const mime = MIME[extname(file)];
  if (!mime) {
    response.writeHead(415, { 'content-type': MIME['.html'] });
    response.end(`unsupported media type: ${extname(file)}`);
    return;
  }
  response.writeHead(200, { 'content-type': mime });
  response.end(readFileSync(file));
}

export async function startSiteServer(port = 0) {
  const server = createServer(serve);
  await new Promise((resolve) => server.listen(port, '127.0.0.1', resolve));
  const baseURL = `http://127.0.0.1:${server.address().port}`;
  return { server, baseURL };
}
