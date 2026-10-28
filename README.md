# Bartu Emre — Portfolio

An English-language, static portfolio for [bartuemre.com](https://bartuemre.com), built with Astro 7, TypeScript, and Tailwind CSS 4. Phase 1 covers the core site, truthful project descriptions, accessibility, and a safe Cloudflare Pages migration.

## Local development

Use Node.js **24.22.1** (pinned in `.nvmrc` and `.node-version`) and npm 9.6.5 or newer. Dependencies are pinned in `package-lock.json`.

```sh
npm ci
npm run dev
```

Astro prints the local URL, usually `http://localhost:4321`. For the production output:

```sh
npm run check
npm run build
npm test
npm run preview
```

Browser checks use Playwright and axe-core against the production build:

```sh
npx playwright install chromium
npm run test:e2e
```

Alternatively, use an installed Microsoft Edge without downloading Chromium:

```powershell
$env:PLAYWRIGHT_CHANNEL = 'msedge'
npm run test:e2e
```

The browser test runner starts and stops its own preview server. Port 4321 must be free or serve this project's current production build. Screenshot outputs are in `test-results/` (gitignored).

### This Codex Windows workspace

The host has Node but no `npm` on PATH. A workspace-local npm 12.2.1 was downloaded outside this repository, under `../.tools/package`. The exact equivalent commands used here are:

```powershell
node '../.tools/package/bin/npm-cli.js' ci
node '../.tools/package/bin/npm-cli.js' run check
node '../.tools/package/bin/npm-cli.js' run build
node '../.tools/package/bin/npm-cli.js' test
$env:PLAYWRIGHT_CHANNEL = 'msedge'
node '../.tools/package/bin/npm-cli.js' run test:e2e
node '../.tools/package/bin/npm-cli.js' run dev
```

This local npm bootstrap is not needed by another developer or Cloudflare with a standard Node/npm installation.

## Design and architecture

- Editorial typography, generous spacing, restrained blue/green accents, and original SVG concept diagrams connect the three disciplines without pretending to show running security systems or real product screenshots.
- System fonts keep requests local. Static Astro pages avoid a hydrated framework or SPA. One small TypeScript module handles theme, mobile navigation, and progressive scroll reveals; CSS supplies ambient motion and native cross-document transitions where supported.
- Tailwind 4 uses its official Vite plugin. Shared CSS variables handle both themes; utility classes support local spacing. Theme selection runs before styles paint, honors the system preference, and persists a visitor's override. Blocked browser storage is handled safely.
- Navigation, content, and links work without JavaScript. Reduced motion disables decoration, transitions, and scroll effects. A skip link, focus styles, semantic headings, active navigation, and keyboard menu controls support accessible use.
- No analytics, backend, forms, paid services, remote fonts, external media, cookies, or client-side secrets. The only stored browser preference is the theme. Astro build-tool telemetry was disabled locally; set `ASTRO_TELEMETRY_DISABLED=1` in CI if desired.
- Public pages include canonical URLs, description/Open Graph metadata, sitemap, robots directives, and an SVG favicon. No social preview image is claimed until an owner-approved asset is added. Cloudflare security headers live in `public/_headers`.

## Routes and source

| Route | Source / purpose |
| --- | --- |
| `/` | `src/pages/index.astro`: hero, featured work, focus areas, contact CTA |
| `/about/` | `src/pages/about.astro`: student background and interests |
| `/projects/` | `src/pages/projects/index.astro`: project collection |
| `/projects/[slug]/` | Markdown-driven project detail pages |
| `/contact/` | Verified GitHub profile and optional configured contact links |
| `/lab/` | Honest future-writeups introduction |
| `/blog/` | Honest future-writing introduction |
| `/404.html` | Custom not-found page, excluded from indexing and sitemap |

`src/layouts/BaseLayout.astro` centralizes metadata and shared structure. Reusable UI is in `src/components/`, the design system in `src/styles/global.css`, and browser behavior in `src/scripts/site.ts`.

### Editing content

- Profile, navigation, and focus areas: `src/data/profile.ts`.
- Project frontmatter and body: `src/content/projects/*.md`.
- Validated collection schema: `src/content.config.ts`.
- A new Markdown project automatically gets a detail route and joins the index. Set `featured: true` to include it on Home; `order` controls sorting. `repository` and `demo` are optional valid URLs. Omitted URLs produce a non-clickable status, never a dead button.
- SOC Decision Lab remains an in-progress academic project. MILP is under consideration; the site does not claim an implemented/validated optimizer or production results.
- Research Explorer is explicitly a working label. No repository/deployment URL is invented.
- For Phase 2, add a separate typed article collection and `src/pages/blog/[slug].astro` using the existing project collection/render pattern and `BaseLayout`. Add lab entries similarly. Publish only actual articles; there are no fabricated seed posts.
- Filtering is intentionally deferred for this two-entry collection. No nonfunctional filter controls are displayed.

### Owner content checklist

- [ ] Confirm Research Explorer's final name, repository, deployment, and current release status.
- [ ] Add a public LinkedIn URL, if desired (`profile.linkedin`).
- [ ] Add a public contact email, if desired (`profile.email`).
- [ ] Supply an approved résumé PDF in `public/` and set `profile.resume`.
- [ ] Supply a portrait and its alt text, if desired. `profile.portrait` is reserved; no image is rendered today.
- [ ] Provide actual project screenshots and an approved social preview image before replacing concept diagrams or adding `og:image`.

## Verification

`npm run check` validates Astro and TypeScript. `npm test` validates generated routes, metadata, internal links/assets, safe outbound links, publication states, sitemap exclusions, and exact legacy preservation.

The 15 Playwright tests cover all nine pages, desktop/mobile widths (320, 390, 768, 1440), dark/light WCAG A/AA axe checks, theme persistence and system changes, blocked localStorage, mobile keyboard/menu/resize behavior, skip-link focus, project links, no-JavaScript fallback, reduced motion, custom 404 status, and review screenshots. Automated accessibility checks do not replace manual assistive-technology testing. Browser verification was performed on local Microsoft Edge (Chromium); Safari/Firefox and Cloudflare-hosted behavior remain deployment checks.

## Review and deployment

Work is on `feat/astro-portfolio-foundation`, based on original commit `90d2012`. Review the feature branch / draft PR before merging.

The root `index.html` remains unchanged and an exact reference copy lives in `docs/legacy-index.html`. Astro builds only `src/pages` plus `public` into `dist`, so legacy HTML is not shipped in the new static output. **With the current Cloudflare settings (empty build command, output `.`), this branch does not serve the Astro site.** Never treat a green deployment of the old root page as validation of the new site.

See [the Cloudflare migration and rollback checklist](docs/CLOUDFLARE_MIGRATION.md). Production build settings, DNS, redirects, merge, and deployment require owner approval and have not been changed by this implementation.
