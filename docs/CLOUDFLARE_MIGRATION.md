# Cloudflare Pages migration — approval required

## Recorded baseline from the owner brief

- Repository: `bartuemre/bartuemre-portfolio`.
- Pages project: `bartuemre-portfolio`.
- Production branch: `main`; original site commit: `90d2012`.
- Build command: empty. Output directory: `.`. Framework preset: None.
- Domains: `bartuemre.com`, `www.bartuemre.com`.
- Existing `www` → apex 301 rule must remain intact.

These settings are owner-provided, not verified through the Cloudflare account. No Cloudflare changes were made during implementation.

## Review before production

- [ ] Review the feature branch or draft PR and its truthful content/status labels.
- [ ] Run `npm ci`, `npm run check`, `npm run build`, `npm test`, and `npm run test:e2e`.
- [ ] Inspect desktop/mobile, both themes, keyboard menu, 404, and project detail links locally.
- [ ] Record current Pages production/preview settings, auto-deployment behavior, and the last successful deployment ID.
- [ ] Obtain explicit approval for the production migration and merge.

## Preview: keep production settings separate

The current blank command / `.` output serves the legacy root HTML. It does **not** test Astro even if its deployment succeeds.

If the Pages project supports separate preview build settings, after approval configure the feature-branch preview with `npm run build`, output `dist`, and Node `24.22.1`. Preview installation can use the checked-in npm lockfile. Verify that only the preview environment is changed. If the fields are shared with production, do not change them just to get a preview: use the local build for review and schedule the coordinated migration below. Do not assume branch previews are enabled or change their audience without approval.

## Approved migration window

1. Confirm the previous successful deployment is available for rollback. If necessary, coordinate disabling automatic production builds during the brief transition; that setting change also requires approval.
2. Merge the reviewed feature branch at the agreed time. The retained root `index.html` preserves the old landing page if an automatic deployment runs under the old settings. This is a transitional safeguard, not the desired final output; the repo root contains source files and must not remain the published directory.
3. Set the production build command to **`npm run build`**, build output to **`dist`**, root directory to the repository root, and Node to **`24.22.1`** (using the supported environment configuration, or confirm `.node-version` is honored). Keep production branch **`main`**. No static Astro adapter is needed.
4. Trigger or retry a deployment of the merged commit. Confirm the build log uses the pinned Node and generates nine pages into `dist`. Confirm that the final upload is `dist`, not the repository root.
5. Verify `/`, `/about/`, `/projects/`, both project details, `/contact/`, `/lab/`, `/blog/`, and an unknown path returning the custom 404 with HTTP 404. Test direct loads as well as navigation. Check canonical URLs, sitemap, favicon, security headers, and missing asset requests.
6. Verify dark/light persistence, first-visit system preference, keyboard navigation, mobile layout, and reduced motion on the deployed site. Verify `https://www.bartuemre.com` still returns the intended 301 to `https://bartuemre.com`.
7. Restore any approved temporary auto-deployment changes. Keep DNS, custom domains, and the existing redirect rule unchanged.

## Rollback

- For immediate service restoration, use the previously recorded successful Pages deployment rollback if available. Confirm that the old page is serving; do not rely on a UI success indicator alone.
- For a lasting code rollback, revert the migration PR through review or deploy the known working original commit `90d2012` with owner approval. Avoid rewriting shared `main` history.
- When returning to the original single-file site, restore the original empty build command and output `.`. Those settings are appropriate only for the legacy build. If rolling back to another Astro version, keep `npm run build` and `dist`.
- If rollback requires an alternate reference copy, `docs/legacy-index.html` exactly preserves the original `index.html`. Both are excluded from Astro's production output.
- Recheck both domain routes and the `www` 301 after rollback. Record the deployed commit and settings together so the next retry is reproducible.
