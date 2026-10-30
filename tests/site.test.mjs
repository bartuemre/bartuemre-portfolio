import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';

const dist = path.resolve('dist');
const englishRoutes = ['index.html', 'about/index.html', 'projects/index.html', 'projects/soc-decision-lab/index.html', 'projects/research-explorer/index.html', 'projects/iprv/index.html', 'contact/index.html', 'lab/index.html', 'blog/index.html', '404.html'];
const routes = [...englishRoutes, ...englishRoutes.map(route => route === '404.html' ? 'tr/404/index.html' : `tr/${route}`)];

test('all required routes have unique titles, one h1, and canonical metadata', async () => {
  const titles = new Set();
  for (const route of routes) {
    const html = await readFile(path.join(dist, route), 'utf8');
    const title = html.match(/<title>(.*?)<\/title>/)?.[1];
    assert.ok(title, `${route}: title`);
    const locale = route.startsWith('tr/') ? 'tr' : 'en';
    assert.ok(!titles.has(`${locale}:${title}`), `${route}: unique title within language`);
    titles.add(`${locale}:${title}`);
    assert.equal((html.match(/<h1\b/g) ?? []).length, 1, `${route}: one h1`);
    assert.ok(html.includes(`<html lang="${locale}"`));
    assert.match(html, /rel="canonical" href="https:\/\/bartuemre.com\//);
    assert.match(html, /name="description" content="[^"]+"/);
    assert.match(html, /property="og:title"/);
    assert.doesNotMatch(html, /lorem ipsum|href="#"|href=""/i);
  }
});

test('selected work is on Projects only and language links preserve each page', async () => {
  for (const prefix of ['', 'tr/']) {
    const home = await readFile(path.join(dist, prefix, 'index.html'), 'utf8');
    assert.doesNotMatch(home, /id="selected-work"|class="project-card/);
    const projects = await readFile(path.join(dist, prefix, 'projects/index.html'), 'utf8');
    assert.match(projects, /id="selected-work"/);
    assert.equal((projects.match(/class="project-card"/g) ?? []).length, 3);
  }
  for (const route of englishRoutes.filter(route => route !== '404.html')) {
    const pathname = '/' + route.replace(/index\.html$/, '');
    const tr = await readFile(path.join(dist, 'tr', route), 'utf8');
    const en = await readFile(path.join(dist, route), 'utf8');
    assert.ok(en.includes(`href="/tr${pathname}" lang="tr"`), `${route}: TR switch`);
    assert.ok(tr.includes(`href="${pathname}" lang="en"`), `${route}: EN switch`);
    assert.match(tr, /hreflang="tr" href="https:\/\/bartuemre.com\/tr\//);
    assert.match(tr, /href="\/tr\/projects\/"[^>]*>Projeler<\/a>/);
    assert.doesNotMatch(tr.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, ''), /Skip to content|Open navigation|Switch to dark theme|opens in a new tab/);
  }
  const detail = await readFile(path.join(dist, 'tr/projects/soc-decision-lab/index.html'), 'utf8');
  assert.match(detail, /genel amaçlı bir MILP çözücüsü değildir/);
  assert.match(detail, /başlamış hazırlık ve incelemeler korunur/);
});

test('every generated internal link and local asset resolves', async () => {
  for (const route of routes) {
    const html = await readFile(path.join(dist, route), 'utf8');
    for (const match of html.matchAll(/(?:href|src)="(\/[^"#?]*)(?:[?#][^"]*)?"/g)) {
      const target = path.join(dist, decodeURIComponent(match[1]));
      const info = await stat(target).catch(() => null);
      assert.ok(info, `${route} references missing ${match[1]}`);
      if (info.isDirectory()) assert.ok(await stat(path.join(target, 'index.html')), `${match[1]} has index.html`);
    }
    for (const match of html.matchAll(/<a\b[^>]*target="_blank"[^>]*>/g)) {
      assert.match(match[0], /rel="noopener noreferrer"/);
    }
  }
});

test('truthful publication states, indexing, and legacy preservation', async () => {
  const research = await readFile(path.join(dist, 'projects/research-explorer/index.html'), 'utf8');
  assert.match(research, /Live GitHub Pages demo/);
  assert.match(research, /https:\/\/bartuemre\.github\.io\/literatur-tarama\//);
  const soc = await readFile(path.join(dist, 'projects/soc-decision-lab/index.html'), 'utf8');
  assert.match(soc, /not a general MILP solver/);
  assert.match(soc, /risk-weighted delay in starting an alert review/);
  assert.match(await readFile(path.join(dist, '404.html'), 'utf8'), /noindex, follow/);
  const files = await readdir(dist);
  const sitemapFiles = files.filter((file) => /sitemap.*\.xml$/.test(file));
  assert.ok(sitemapFiles.length > 0);
  const sitemap = (await Promise.all(sitemapFiles.map((file) => readFile(path.join(dist, file), 'utf8')))).join('');
  assert.doesNotMatch(sitemap, /\/404/);
  assert.match(sitemap, /https:\/\/bartuemre.com\/projects\/soc-decision-lab\//);
  assert.equal(await readFile('index.html', 'utf8'), await readFile('docs/legacy-index.html', 'utf8'));
});
