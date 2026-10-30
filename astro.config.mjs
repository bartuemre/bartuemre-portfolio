import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';

// Static hosts resolve this public directory's index; Astro dev needs the redirect.
const iprvPublicIndex = {
  name: 'iprv-public-index',
  configureServer(server) {
    server.middlewares.use((request, response, next) => {
      const url = new URL(request.url ?? '/', 'http://localhost');
      if (url.pathname !== '/iprv-app/') return next();
      response.writeHead(307, { Location: `/iprv-app/index.html${url.search}` });
      response.end();
    });
  },
};

export default defineConfig({
  site: 'https://bartuemre.com',
  output: 'static',
  trailingSlash: 'always',
  devToolbar: { enabled: false },
  integrations: [sitemap({ filter: (page) => !page.endsWith('/404/') })],
  vite: { plugins: [tailwindcss(), iprvPublicIndex] },
});
