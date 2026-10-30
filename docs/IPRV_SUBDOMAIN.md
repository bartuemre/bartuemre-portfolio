# IPRV standalone site

The portfolio embeds IPRV at `/iprv-app/index.html`. The same v0.4.7 release is packaged as an independent static site in `iprv-site/`, with a root `index.html`, root-relative assets, and its own favicon. The frontend talks to `https://iprv-api.onrender.com`; the API must be online for analysis and source features.

To verify the standalone output, run `npm run build:iprv-site`. This copies validated site files to `dist-iprv-site/`.

Deploy the standalone site as a **second Cloudflare Pages project** connected to this repository:

- Production branch: `main`
- Build command: `npm run build:iprv-site`
- Build output directory: `dist-iprv-site`
- Root directory: repository root
- Custom domain: `iprv.bartuemre.com`

Keep the existing `bartuemre-portfolio` Pages project and its apex/www domains. A second Pages project is required because custom domains on the same project serve the same root document.

The Render API configuration in `iprv-backend/render.yaml` permits both `https://bartuemre.com` and `https://iprv.bartuemre.com` as exact browser origins. Deploy the updated `iprv-backend/` service and set its `IPRV_ADDITIONAL_FRONTEND_ORIGIN` to the subdomain before testing cross-origin API calls. The backend package now includes the new network lookup endpoint used by the latest frontend.

After publication, verify the subdomain document and static assets, an API preflight from the new origin, the portfolio's English/Turkish project links, and a real analysis request. Update the portfolio's status label from local to live once these checks pass.
