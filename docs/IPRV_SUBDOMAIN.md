# IPRV standalone site

The portfolio embeds IPRV at `/iprv-app/index.html`. The same v0.4.7 release is packaged as an independent static site in `iprv-site/`, with a root `index.html`, root-relative assets, and its own favicon. The frontend talks to `https://iprv-api.onrender.com`; the API must be online for analysis and source features.

To verify the standalone output, run `npm run build:iprv-site`. This copies validated site files to `dist-iprv-site/`.

The standalone site is deployed as a **second Cloudflare Pages project** connected to this repository:

- Production branch: `main`
- Build command: `npm run build:iprv-site`
- Build output directory: `dist-iprv-site`
- Root directory: repository root
- Custom domain: `iprv.bartuemre.com`

Deployment completed on 30 October 2026. The Pages project is `bartuemre-iprv`, its fallback URL is `https://bartuemre-iprv.pages.dev/`, and the custom domain resolves to the same site. The Render service `iprv-api` was redeployed from commit `8f1615f66ef2b193a776b421290d44f5c0230900` with `IPRV_ADDITIONAL_FRONTEND_ORIGIN=https://iprv.bartuemre.com`.

Keep the existing `bartuemre-portfolio` Pages project and its apex/www domains. A second Pages project is required because custom domains on the same project serve the same root document.

The Render API configuration in `iprv-backend/render.yaml` permits both `https://bartuemre.com` and `https://iprv.bartuemre.com` as exact browser origins. The backend package includes the new network lookup endpoint used by the latest frontend.

Verified: the subdomain document and static assets return HTTP 200, the API preflight permits the new origin, and a browser analysis of documentation address `192.0.2.1` completed with the expected non-global result. The portfolio's project status now reflects the live workspace.
