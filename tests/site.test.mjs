import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';

const dist = path.resolve('dist');
const routes = ['index.html', 'about/index.html', 'projects/index.html', 'projects/soc-decision-lab/index.html', 'projects/research-explorer/index.html', 'contact/index.html', 'lab/index.html', 'blog/index.html', '404.html'];

test('all required routes have unique titles, one h1, and canonical metadata', async () => {
  const titles = new Set();
  for (const route of routes) {
    const html = await readFile(path.join(dist, route), 'utf8');
    const title = html.match(/<title>(.*?)<\/title>/)?.[1];
    assert.ok(title, `${route}: title`);
    assert.ok(!titles.has(title), `${route}: unique title`);
    titles.add(title);
    assert.equal((html.match(/<h1\b/g) ?? []).length, 1, `${route}: one h1`);
    assert.match(html, /<html lang="en"/);
    assert.match(html, /rel="canonical" href="https:\/\/bartuemre.com\//);
    assert.match(html, /name="description" content="[^"]+"/);
    assert.match(html, /property="og:title"/);
    assert.doesNotMatch(html, /lorem ipsum|href="#"|href=""/i);
  }
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
  assert.match(research, /Go project/);
  assert.match(research, /https:\/\/bartuemre\.github\.io\/literatur-tarama\//);
  const soc = await readFile(path.join(dist, 'projects/soc-decision-lab/index.html'), 'utf8');
  assert.match(soc, /an implemented or validated optimizer is not claimed/);
  assert.match(await readFile(path.join(dist, '404.html'), 'utf8'), /noindex, follow/);
  const files = await readdir(dist);
  const sitemapFiles = files.filter((file) => /sitemap.*\.xml$/.test(file));
  assert.ok(sitemapFiles.length > 0);
  const sitemap = (await Promise.all(sitemapFiles.map((file) => readFile(path.join(dist, file), 'utf8')))).join('');
  assert.doesNotMatch(sitemap, /\/404/);
  assert.match(sitemap, /https:\/\/bartuemre.com\/projects\/soc-decision-lab\//);
  assert.equal(await readFile('index.html', 'utf8'), await readFile('docs/legacy-index.html', 'utf8'));
});
