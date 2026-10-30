import { cp, mkdir, readFile, rm, stat } from 'node:fs/promises';
import { join } from 'node:path';

const source = new URL('../iprv-site/', import.meta.url);
const output = new URL('../dist-iprv-site/', import.meta.url);
const html = await readFile(new URL('index.html', source), 'utf8');
for (const match of html.matchAll(/(?:src|href)="(\/[^"]+)"/g)) {
  const path = match[1].slice(1).split('?')[0];
  if (path === '') continue;
  await stat(new URL(path, source));
}
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await cp(source, output, { recursive: true });
console.log(`IPRV standalone site copied to ${join(process.cwd(), 'dist-iprv-site')}`);
