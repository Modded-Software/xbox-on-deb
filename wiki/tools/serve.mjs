import { startSiteServer } from './lib-server.mjs';

const port = Number(process.env.PORT ?? 18082);
const { baseURL } = await startSiteServer(port);
console.log(`Serving the wiki at ${baseURL}/en/ (Ctrl-C to stop)`);
